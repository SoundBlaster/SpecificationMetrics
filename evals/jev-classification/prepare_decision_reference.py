#!/usr/bin/env python3
"""Prepare bounded source-bound expression annotation packets, without inference."""
import argparse
import ast
import json
from pathlib import Path
import subprocess

from question_grouping import canonical, digest


ROOT = Path(__file__).parent
TARGETS = ROOT / "runs/2026-10-10-decision-targets/report.json"
PROFILE = ROOT / "runs/2026-10-10-rubric-alignment/reference-packet.json"
MAX_CONTEXT_BYTES = 8 * 1024
MAX_STATE_BYTES = 16 * 1024


def declaration_range(tree, name):
    matches = []
    for node in tree.body:
        names = [getattr(node, "name", None)]
        if isinstance(node, ast.Import):
            names += ["import:" + alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom):
            names += ["import:" + (node.module or "")]
        if name in names:
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            matches.append((start, node.end_lineno))
    if len(matches) != 1:
        raise ValueError("Supporting declaration must resolve uniquely: " + name)
    return matches[0]


def fragment(raw, start, end, purpose):
    lines = raw.splitlines(keepends=True)
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ValueError("Invalid context line range")
    code = b"".join(lines[start - 1:end])
    begin = sum(len(line) for line in lines[:start - 1])
    return {"start_line": start, "end_line": end, "start_byte": begin,
            "end_byte": begin + len(code), "sha256": digest(code),
            "purpose": purpose, "code": code.decode("utf-8")}


def build(selectors, rubric, read_source):
    report_raw = TARGETS.read_bytes()
    report = json.loads(report_raw)
    entries = {c["source_candidate_id"]: c for c in report["cases"]}
    if selectors["schema_version"] != 1 or set(selectors["cases"]) != set(entries):
        raise ValueError("Context selectors must cover exactly the frozen eight targets")
    profile = json.loads(PROFILE.read_text())["cases"][0]["state"]["architecture_profile"]
    packet = {"schema_version": 1, "study_kind": "decision_expression_reference",
              "instructions": "Judge only the exact target expression under this profile and rubric. Supporting fragments are evidence, not additional candidates. Do not infer omitted dependencies. Return both axes and cite supplied fragment/target evidence. No prior labels or provider predictions are supplied.",
              "questions": rubric["questions"], "cases": []}
    mapping, inventory = [], []
    for number, cid in enumerate(sorted(entries), 1):
        entry = entries[cid]
        source, target = entry["source"], entry["target"]
        raw = read_source(source["revision"], source["path"])
        if "sha256:" + digest(raw) != source["file_sha256"]:
            raise ValueError("Pinned source digest mismatch")
        expression = target["expression"]
        span = expression["span"]
        if expression["truncated"] or raw[span["start_byte"]:span["end_byte"]].decode() != expression["code"]:
            raise ValueError("Target expression differs from exact source bytes")
        tree = ast.parse(raw.decode("utf-8"))
        fragments = []
        for selection in selectors["cases"][cid]:
            if "symbol" in selection:
                start, end = declaration_range(tree, selection["symbol"])
            else:
                start, end = selection["start_line"], selection["end_line"]
            fragments.append(fragment(raw, start, end, selection["purpose"]))
        if not any(f["start_byte"] <= span["start_byte"] < span["end_byte"] <= f["end_byte"] for f in fragments):
            raise ValueError("Supporting context must include the selected expression at its source location")
        size = sum(len(f["code"].encode()) for f in fragments)
        if size > MAX_CONTEXT_BYTES:
            raise ValueError("Context budget exceeded; select smaller explicit regions")
        case_id = f"expression-{number:02d}"
        state = {"architecture_profile": profile,
                 "target": {"language": "Python", "code": expression["code"],
                            "syntax_kind": expression["syntax_kind"], "scope": "exact expression only"},
                 "bounded_context": {"fragments": [{"fragment_id": f"context-{i:02d}", "code": f["code"]} for i, f in enumerate(fragments, 1)],
                                     "truncated": False,
                                     "limitations": "Selected same-file declarations and data/use regions only. Unlisted callers, cross-file declarations and runtime bindings are not proved. A factory assembly is one selected expression, not a claim of one indivisible rule."}}
        wire = canonical(state)
        if len(wire) > MAX_STATE_BYTES:
            raise ValueError("State budget exceeded")
        packet["cases"].append({"case_id": case_id, "state": state, "state_sha256": digest(wire)})
        mapping.append({"case_id": case_id, "source_candidate_id": cid,
                        "target_id": target["target_id"], "source": source,
                        "expression_span": span, "expression_sha256": digest(expression["code"].encode()),
                        "fragments": fragments, "state_sha256": digest(wire),
                        "construction_evidence": entry["construction_evidence"]})
        inventory.append({"case_id": case_id, "context_code_bytes": size, "state_bytes": len(wire),
                          "fragment_count": len(fragments)})
    return packet, {"schema_version": 1, "target_report_sha256": digest(report_raw),
                    "implementation_digests": {name: digest((ROOT / name).read_bytes()) for name in ["prepare_decision_reference.py", "question_grouping.py"]},
                    "profile_source_sha256": digest(PROFILE.read_bytes()),
                    "selector_sha256": digest(canonical(selectors)),
                    "rubric_sha256": digest(canonical(rubric)),
                    "packet_sha256": digest(canonical(packet)), "cases": mapping,
                    "inventory": inventory, "new_inference_requests": 0,
                    "prior_labels_transferred": False, "reference_status": "awaiting_independent_annotation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Rebuild in memory and verify saved artifacts without writing")
    args = parser.parse_args()
    selectors = json.loads((args.run / "context-selectors.json").read_text())
    rubric = json.loads((args.run / "rubric.json").read_text())
    def read_source(revision, path):
        return subprocess.check_output(["git", "-C", str(args.source_repo), "show", revision + ":" + path])
    packet, mapping = build(selectors, rubric, read_source)
    for name, value in [("reference-packet.json", packet), ("source-mapping.json", mapping)]:
        if args.check:
            if json.loads((args.run / name).read_text()) != value:
                raise ValueError("Saved preparation artifact differs: " + name)
        else:
            with (args.run / name).open("x") as out:
                json.dump(value, out, indent=2)
                out.write("\n")
    print(json.dumps(mapping["inventory"]))


if __name__ == "__main__":
    main()
