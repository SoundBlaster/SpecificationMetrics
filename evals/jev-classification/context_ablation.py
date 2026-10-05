#!/usr/bin/env python3
"""Source-grounded diagnostic context ablation; no new holdout or registry writes."""

import argparse
import ast
import copy
import json
from pathlib import Path
import subprocess
import textwrap

from experiment import digest, metrics, write
from validate_cases import _assert_no_label_leak

ROOT = Path(__file__).parent
IDS = ["sg-017", "sg-018", "sg-019", "sg-020", "sg-031", "sg-032", "sg-033", "sg-034"]
ARMS = ["code", "code_task", "code_task_facts"]


def source_document(repo, revision, path, kind):
    raw = subprocess.check_output(["git", "-C", str(repo), "show", f"{revision}:{path}"]).decode()
    lines = raw.splitlines(keepends=True)
    if kind == "bootstrap":
        spans = [(0, 8)]
        start = next(i for i, line in enumerate(lines) if line.startswith("- Bootstrap allocation additionally"))
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("- "))
        spans.append((start, end))
    else:
        start = next(i for i, line in enumerate(lines) if line.startswith("## Summary"))
        # Scope and original business behavior, without implementation/refactor advice.
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## Implementation"))
        spans = [(start, end)]
        if kind == "repair":
            start = next(i for i, line in enumerate(lines) if line.startswith("The deterministic repair preview can:"))
            end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## Authority Boundary"))
            spans.append((start, end))
    return [{"evidence_kind": "tool_documentation" if kind == "bootstrap" else "proposal_description",
             "revision": revision, "path": path, "start_line": a + 1, "end_line": b,
             "file_sha256": digest(raw.encode()), "excerpt_sha256": digest("".join(lines[a:b]).encode()),
             "url": f"https://github.com/0al-spec/SpecGraph/blob/{revision}/{path}#L{a+1}-L{b}",
             "text": "".join(lines[a:b])} for a, b in spans]


def structural_facts(file_source, selected_code, symbol):
    """Narrow import resolution, avoiding positive claims on shadowed bindings."""
    module = ast.parse(file_source)
    site = ast.parse(textwrap.dedent(selected_code))
    local_parameters = {n.arg for n in ast.walk(site) if isinstance(n, ast.arg)}
    imports, rebound = {}, set()
    target = next((n for n in module.body if
                   isinstance(n, (ast.Assign, ast.AnnAssign)) and
                   symbol in {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}), None)
    for node in module.body:
        if node is target:
            break
        if isinstance(node, ast.ImportFrom):
            for name in node.names:
                local_name = name.asname or name.name
                if node.module == "specification_core" and name.name in {"FirstMatch", "PredicateSpec"}:
                    imports[local_name] = name.name
                    rebound.discard(local_name)
                else:
                    imports.pop(local_name, None)
                    rebound.add(local_name)
        elif isinstance(node, ast.Import):
            for name in node.names:
                local_name = name.asname or name.name.split(".", 1)[0]
                imports.pop(local_name, None)
                rebound.add(local_name)
        else:
            # Conservatively include nested bindings; unsupported scope is unknown.
            rebound.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
            rebound.update(n.value.id for n in ast.walk(node) if isinstance(n, ast.Attribute)
                           and isinstance(n.ctx, (ast.Store, ast.Del)) and isinstance(n.value, ast.Name))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                rebound.add(node.name)
    def resolve(func):
        if isinstance(func, ast.Name) and func.id in imports and func.id not in rebound and func.id not in local_parameters:
            return func.id, "specification_core." + imports[func.id]
        if (isinstance(func, ast.Attribute) and func.attr == "with_fallback" and
                isinstance(func.value, ast.Name) and imports.get(func.value.id) == "FirstMatch" and
                func.value.id not in rebound and func.value.id not in local_parameters):
            return func.value.id, "specification_core.FirstMatch.with_fallback"
        return None
    calls = [{"local_name": resolve(n.func)[0], "resolved_import": resolve(n.func)[1],
              "excerpt_line": n.lineno} for n in ast.walk(site) if isinstance(n, ast.Call) and resolve(n.func)]
    root = site.body[0] if len(site.body) == 1 else None
    value = root.value if isinstance(root, (ast.Assign, ast.AnnAssign)) else None
    direct = isinstance(value, ast.Call) and resolve(value.func) is not None
    return {"selected_ast_kind": type(root).__name__ if root else "multiple_statements",
            "specification_core_constructor_calls": calls,
            "direct_library_construction": True if direct else None,
            "limits": "Narrow static import resolution, not runtime identity or whole-project ownership. No visible constructor is not proof that the rule has no existing specification."}


def build(repo):
    corpus = json.loads((ROOT / "corpus/cases.json").read_text())
    reference = json.loads((ROOT / "corpus/experiment-v1.json").read_text())
    cases = []
    for cid in IDS:
        original = next(c for c in corpus if c["description"] == cid)
        ref = next(c for c in reference["cases"] if c["source_candidate_id"] == cid)
        state = json.loads(original["vars"]["candidate_json"])
        state["candidate_id"] = ref["candidate_id"]
        source = original["metadata"]["source"]["site"]
        if cid == "sg-033":
            path, kind = "docs/subject_publication.md", "bootstrap"
        elif cid in {"sg-019", "sg-020", "sg-034"}:
            path, kind = "docs/proposals/0152_candidate_repair_loop.md", "repair"
        else:
            path, kind = "docs/proposals/0154_idea_to_spec_promotion_gate.md", "promotion"
        task = source_document(repo, source["revision"], path, kind)
        file_bytes = subprocess.check_output(["git", "-C", str(repo), "show",
                                              f"{source['revision']}:{source['path']}"])
        if digest(file_bytes) != source["file_sha256"]:
            raise ValueError("source file digest mismatch")
        facts = structural_facts(file_bytes.decode(), source["code"], source["symbol"])
        facts["source"] = {k: source[k] for k in ("revision", "path", "symbol", "start_line", "end_line", "file_sha256", "excerpt_sha256", "url")}
        contexts = {}
        for arm in ARMS:
            value = copy.deepcopy(state)
            if arm != "code":
                value["task_evidence"] = task
            if arm == "code_task_facts":
                value["implementation_facts"] = facts
            _assert_no_label_leak(value)
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode()) > 24 * 1024:
                raise ValueError("context exceeds 24 KiB")
            contexts[arm] = {"state": encoded, "sha256": digest(encoded.encode())}
        cases.append({"candidate_id": ref["candidate_id"], "source_candidate_id": cid,
                      "family_id": ref["family_id"], "opportunity": ref["opportunity"],
                      "concern_kind": ref["concern_kind"], "contexts": contexts,
                      "static_constructor_gate": facts["direct_library_construction"] is True})
    prompt_source = ROOT / "runs/2026-10-05-independent-reference/development.json"
    prompt_config = json.loads(prompt_source.read_text())["prompt_configs"]["baseline-v1"]
    return {"schema_version": 1, "input_facts_version": 2, "study_kind": "diagnostic_context_ablation",
            "reference_kind": reference["reference_kind"], "human_adjudicated": False,
            "prompt_config": prompt_config, "prompt_source_sha256": digest(prompt_source.read_bytes()),
            "holdout": False, "arms": ARMS, "repeats": 2, "cases": cases,
            "protocol": {
                "prompt": "baseline-v1 unchanged from the recorded prompt experiment",
                "selection": "Known workspace/ownership/repair disagreements plus paired implementations and three mechanical controls; purposive, not representative.",
                "hypothesis": "Task context reduces false exclusions; structural ownership facts reduce already-owned false positives without increasing mechanical false positives.",
                "success": "Both repeats improve total opportunity agreement over fresh code-only baseline, reduce the targeted errors and do not add mechanical false positives.",
                "refutation": "Target errors persist, only one repeat improves, or mechanical false positives increase: hypothesis not supported in this diagnostic sample.",
                "limits": "No new confirmation holdout; references were made with code-only context. Task evidence may change meaning, so disagreement requires adjudication rather than automatic gold correction."}}


def score(study, run):
    if run["study_sha256"] != digest((json.dumps(study, ensure_ascii=False, indent=2) + "\n").encode()):
        raise ValueError("study digest mismatch")
    if run["prompt_sha256"] != digest(json.dumps(study["prompt_config"], ensure_ascii=False, separators=(",", ":")).encode()):
        raise ValueError("prompt digest mismatch")
    expected_model = study["prompt_config"]["model"]
    if run.get("requested_model") != expected_model:
        raise ValueError("run requested model mismatch")
    lookup = {c["candidate_id"]: c for c in study["cases"]}
    rows = {}
    for row in run["rows"]:
        key = (row["repeat"], row["arm"], row["candidate_id"])
        if key in rows or row["candidate_id"] not in lookup or row["arm"] not in study["arms"]:
            raise ValueError("duplicate/unexpected row")
        if row["context_sha256"] != lookup[row["candidate_id"]]["contexts"][row["arm"]]["sha256"]:
            raise ValueError("context receipt mismatch")
        response = row.get("response")
        if not row.get("error") and not (isinstance(response, dict) and response.get("error")):
            response_metadata = response.get("metadata") if isinstance(response, dict) else None
            metadata = response_metadata.get("typesafe") if isinstance(response_metadata, dict) else None
            if not isinstance(metadata, dict) or metadata.get("requestedModel") != expected_model or metadata.get("returnedModel") != expected_model:
                raise ValueError("response requested/returned model mismatch")
        if not isinstance(response, dict):
            response = {}
        output = response.get("output", {})
        if not isinstance(output, dict):
            output = {}
        rows[key] = {}
        for axis in ("opportunity", "concern_kind"):
            answer = output.get(axis, {})
            rows[key][axis] = (answer.get("choice") if isinstance(answer, dict) else None) if not response.get("error") and not row.get("error") else None
        if rows[key]["opportunity"] not in {"eligible", "excluded", "needs_review"}:
            rows[key]["opportunity"] = None
        if rows[key]["concern_kind"] not in {"policy", "mechanics", "variant_behavior", "unknown"}:
            rows[key]["concern_kind"] = None
    expected = {(r, arm, cid) for r in range(study["repeats"]) for arm in study["arms"] for cid in lookup}
    if set(rows) != expected or not run.get("completed"):
        raise ValueError("incomplete run")
    summaries = {}
    for arm in study["arms"]:
        summaries[arm] = {}
        for r in range(study["repeats"]):
            summaries[arm][str(r)] = {axis: metrics([(c[axis], rows[r, arm, cid][axis]) for cid, c in lookup.items()], axis)
                                      for axis in ("opportunity", "concern_kind")}
            m = summaries[arm][str(r)]
            m["opportunity_agreement"] = sum(rows[r, arm, cid]["opportunity"] == c["opportunity"] for cid, c in lookup.items()) / len(lookup)
            m["mechanical_false_positives"] = sum(c["concern_kind"] == "mechanics" and rows[r, arm, cid]["opportunity"] == "eligible" for cid, c in lookup.items())
            m["already_owned_false_positives"] = sum(c["opportunity"] == "excluded" and c["concern_kind"] == "policy" and rows[r, arm, cid]["opportunity"] == "eligible" for cid, c in lookup.items())
        summaries[arm]["repeat_disagreements"] = sum(rows[0, arm, cid] != rows[1, arm, cid] for cid in lookup)
    decisions = [{"candidate_id": cid, "source_candidate_id": c["source_candidate_id"],
                  "reference_opportunity": c["opportunity"], "static_constructor_gate": c["static_constructor_gate"],
                  "outputs": {arm: [rows[r, arm, cid] for r in range(study["repeats"])] for arm in study["arms"]}}
                 for cid, c in lookup.items()]
    diagnostic_gate = {str(r): metrics([(c["opportunity"], "excluded" if c["static_constructor_gate"] else rows[r, "code_task_facts", cid]["opportunity"])
                                       for cid, c in lookup.items()], "opportunity") for r in range(study["repeats"])}
    hypothesis = {}
    for arm in study["arms"][1:]:
        hypothesis[arm] = all(
            summaries[arm][str(r)]["opportunity_agreement"] > summaries["code"][str(r)]["opportunity_agreement"] and
            summaries[arm][str(r)]["opportunity"]["false_exclusions"] < summaries["code"][str(r)]["opportunity"]["false_exclusions"] and
            summaries[arm][str(r)]["already_owned_false_positives"] < summaries["code"][str(r)]["already_owned_false_positives"] and
            summaries[arm][str(r)]["mechanical_false_positives"] <= summaries["code"][str(r)]["mechanical_false_positives"] and
            summaries[arm][str(r)]["opportunity"]["provider_or_contract_errors"] == 0
            for r in range(study["repeats"]))
    return {"study_kind": study["study_kind"], "reference_kind": study["reference_kind"],
            "human_adjudicated": False, "holdout": False, "summaries": summaries, "decisions": decisions,
            "hypothesis_supported": hypothesis,
            "diagnostic_static_filter": {"scope": "Only recognized direct library constructions, no negative inference from absence. Evaluation view, no registry or S/U writes.", "opportunity": diagnostic_gate},
            "limits": "Purposive diagnostic cases, code-only model references; repeats measure consistency, not independent sample size."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--study", type=Path, required=True)
    s.add_argument("--run", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to replace a study/report")
    if args.command == "prepare":
        value = build(args.repo)
    else:
        value = score(json.loads(args.study.read_text()), json.loads(args.run.read_text()))
    write(args.output, value)
    print("Saved " + str(args.output))


if __name__ == "__main__":
    main()
