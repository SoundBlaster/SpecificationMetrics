#!/usr/bin/env python3
"""Bounded Python construction evidence, then offline replay of semantic answers.

This diagnostic does not change the Rust classifier, registry or production metric.
The positive result assumes ordinary static Python bindings and the imported
library contract; it is not a runtime identity or whole-project ownership proof.
"""
import argparse
import ast
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from experiment import metrics, digest as source_digest
from question_grouping import digest
from score_rubric_alignment import score
from scanner_build import verified_build, verify_unchanged

ROOT = Path(__file__).parent
CONSTRUCTORS = {"FirstMatch", "PredicateSpec", "AsyncFirstMatch", "AsyncPredicateSpec"}


def construction_evidence(raw, site):
    """Verify source binding before recognizing a whole selected construction."""
    if source_digest(raw) != site["file_sha256"]:
        raise ValueError("Source file digest mismatch")
    text = raw.decode("utf-8")
    start, end = site["start_line"], site["end_line"]
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(text.splitlines()):
        raise ValueError("Invalid source span")
    excerpt = "".join(text.splitlines(keepends=True)[start - 1:end])
    if excerpt != site["code"] or source_digest(excerpt.encode()) != site["excerpt_sha256"]:
        raise ValueError("Source excerpt mismatch")
    module = ast.parse(text)
    provenance = {k: site[k] for k in ("revision", "path", "symbol", "start_line", "end_line", "file_sha256", "excerpt_sha256")}
    result = {"status": "unknown", "source": provenance, "resolved_constructor": None}
    target = next((n for n in module.body if n.lineno == start and n.end_lineno == end), None)
    if not isinstance(target, (ast.Assign, ast.AnnAssign)):
        return result
    targets = target.targets if isinstance(target, ast.Assign) else [target.target]
    if len(targets) != 1 or not isinstance(targets[0], ast.Name) or targets[0].id != site["symbol"]:
        return result
    value = target.value
    if not isinstance(value, ast.Call):
        return result
    aliases = {}
    for node in module.body:
        if node is target:
            break
        if isinstance(node, ast.ImportFrom):
            if any(n.name == "*" for n in node.names):
                aliases.clear()
            for n in node.names:
                local = n.asname or n.name
                aliases.pop(local, None)
                if node.level == 0 and node.module == "specification_core" and n.name in CONSTRUCTORS:
                    aliases[local] = n.name
            continue
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                aliases.pop(n.id, None)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                aliases.pop(n.name, None)
            elif isinstance(n, ast.alias):
                aliases.pop(n.asname or n.name.split(".")[0], None)
            elif isinstance(n, ast.ExceptHandler):
                aliases.pop(n.name, None)
            elif type(n).__name__ in {"MatchAs", "MatchStar", "MatchMapping"}:
                aliases.pop(getattr(n, "name", None), None)
                aliases.pop(getattr(n, "rest", None), None)
            elif isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del)) and isinstance(n.value, ast.Name):
                aliases.pop(n.value.id, None)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"exec", "eval", "globals", "locals", "vars", "setattr", "delattr"}:
                # Unsupported dynamic namespace mutation is not negative proof.
                aliases.clear()
    function = value.func
    local = function.id if isinstance(function, ast.Name) else None
    suffix = ""
    if isinstance(function, ast.Attribute) and function.attr == "with_fallback" and isinstance(function.value, ast.Name):
        local = function.value.id
        if aliases.get(local) not in {"FirstMatch", "AsyncFirstMatch"}:
            return result
        suffix = ".with_fallback"
    if local not in aliases:
        return result
    result.update(status="direct_specification_construction", resolved_constructor="specification_core." + aliases[local] + suffix)
    return result


def route(evidence, semantic_provider):
    """Return opportunity only: the gate does not infer the concern-kind axis."""
    if evidence["status"] == "direct_specification_construction":
        return {"opportunity": "excluded", "origin": "static_construction", "evidence": evidence}
    if evidence["status"] != "unknown":
        raise ValueError("Unknown construction evidence status")
    return {"opportunity": semantic_provider(), "origin": "recorded_semantic_answer", "evidence": evidence}


def build(repo, scanner, run):
    scanner_provenance = verified_build(ROOT.parent.parent, scanner)
    raw_score = score(run)
    corpus = {c["description"]: c["metadata"]["source"]["site"] for c in json.loads((ROOT/"corpus/cases.json").read_text())}
    cases = []
    with tempfile.TemporaryDirectory(prefix="specmetrics-ownership-") as temporary:
        for case in raw_score["cases"]:
            site = corpus[case["source_candidate_id"]]
            raw = subprocess.check_output(["git", "-C", str(repo), "show", site["revision"] + ":" + site["path"]])
            evidence = construction_evidence(raw, site)
            # Actual Rust scanner on an isolated, full historical source file.
            root = Path(temporary)/case["source_candidate_id"]
            source = root/site["path"]
            source.parent.mkdir(parents=True)
            source.write_bytes(raw)
            report = root/"scan.json"
            subprocess.run([str(scanner), "scan", str(root), "--output", str(report)], check=True, capture_output=True)
            scanned = json.loads(report.read_text())
            candidates = [c for c in scanned["candidates"] if site["start_line"] <= c["line"] <= site["end_line"]]
            constructions = [s for s in scanned["specifications"] if site["start_line"] <= s["line"] <= site["end_line"]]
            predictions = copy.deepcopy(case["predictions"])
            routes = {}
            for repeat, arms in predictions.items():
                routes[repeat] = {}
                for arm, prediction in arms.items():
                    routed = route(evidence, lambda p=prediction: p["opportunity"])
                    prediction["opportunity"] = routed["opportunity"]
                    routes[repeat][arm] = routed["origin"]
            cases.append({**case, "evidence": evidence, "rust_scan": {"candidates": candidates, "specifications": constructions, "parse_issues": scanned["parse_issues"]}, "routed_predictions": predictions, "routes": routes})
    summaries = {}
    for repeat in ["1", "2"]:
        summaries[repeat] = {}
        for arm in ["baseline", "aligned"]:
            pairs = [(c["reference"]["opportunity"], c["routed_predictions"][repeat][arm]["opportunity"]) for c in cases]
            summary = metrics(pairs, "opportunity")
            summary["agreement_count"] = sum(a == b for a, b in pairs)
            summary["agreement_denominator"] = len(cases)
            summaries[repeat][arm] = summary
    verify_unchanged(ROOT.parent.parent, scanner, scanner_provenance)
    return {"schema_version": 1, "study_kind": "source_bound_static_gate_recorded_replay", "new_inference_requests": 0,
            "recorded_run_completed": raw_score["completed"], "reference_kind": raw_score["reference_kind"],
            "human_adjudicated": False, "holdout": False, "cases": cases, "routed_opportunity_summaries": summaries,
            "raw_opportunity_summaries": {r: {a: v["opportunity"] for a, v in arms.items()} for r, arms in raw_score["summaries"].items()},
            "input_artifact_digests": {**raw_score["artifact_digests"], "corpus/cases.json": digest((ROOT/"corpus/cases.json").read_bytes())},
            "scanner_provenance": scanner_provenance,
            "implementation_digests": {**raw_score["analysis_implementation_digests"], "ownership_gate.py": digest(Path(__file__).read_bytes()), "scanner_build.py": digest((ROOT/"scanner_build.py").read_bytes())},
            "limits": "Development-only eight-case replay against model annotations. Static construction assumes ordinary Python bindings and trusted library semantics. Unknown is not unowned. Rust factory names are syntactic, not import-resolved proof. Recorded semantic answers were already paid for; routing is offline, not a new end-to-end live evaluation. Concern-kind answers remain recorded model answers. No registry or production metric changes."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--scanner", type=Path, required=True)
    parser.add_argument("--run", type=Path, default=ROOT/"runs/2026-10-10-rubric-alignment")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.source_repo, args.scanner.resolve(), args.run)
    with args.output.open("x") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    print(json.dumps({"new_inference_requests": 0, "static_positive_ids": [c["source_candidate_id"] for c in report["cases"] if c["evidence"]["status"] != "unknown"], "agreement": {r: {a: m["agreement_count"] for a, m in arms.items()} for r, arms in report["routed_opportunity_summaries"].items()}}))


if __name__ == "__main__":
    main()
