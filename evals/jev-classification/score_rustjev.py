#!/usr/bin/env python3
"""Offline scoring of a bounded RustJev run against the frozen model reference."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from experiment import LABELS, metrics

ROOT = Path(__file__).parent
REFERENCE = ROOT / "runs/2026-10-05-intent-profile-reference"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def index_rows(rows, planned):
    indexed = {}
    for row in rows:
        key = (row["candidate_id"], row["axis"])
        if key not in planned or key in indexed:
            raise ValueError("Unexpected or duplicate response")
        label = row["accepted_label"]
        if label is not None:
            if label not in LABELS[key[1]] or row["decision"] != "Accepted(" + json.dumps(label) + ")":
                raise ValueError("Invalid accepted label or terminal outcome")
        elif row["decision"].startswith("Accepted("):
            raise ValueError("Accepted result lost its label")
        indexed[key] = row
    return indexed


def score(run):
    manifest = json.loads((run / "manifest.json").read_text())
    for name, expected in manifest["digests"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Provenance digest mismatch: " + name)
    plan = json.loads((run / "requests.json").read_text())
    planned = {(item["candidate_id"], item["axis"]) for item in plan}
    if len(planned) != len(plan) or len(plan) != manifest["requests"]:
        raise ValueError("Invalid request plan")
    rows = [json.loads(line) for line in (run / "responses.jsonl").read_text().splitlines()]
    indexed = index_rows(rows, planned)
    receipt = json.loads((run / "receipt.json").read_text())
    if receipt["saved_responses"] != len(rows) or (receipt["completed"] and set(indexed) != planned):
        raise ValueError("Receipt response count mismatch")
    annotations = {a["case_id"]: a for a in json.loads((REFERENCE / "annotations.json").read_text())["annotations"]}
    mapping = json.loads((REFERENCE / "mapping.json").read_text())["entries"]
    reference = {e["ablation_candidate_id"]: (e, annotations[e["case_id"]]) for e in mapping}
    ids = list(dict.fromkeys(item["candidate_id"] for item in plan))
    if set(ids) != set(reference):
        raise ValueError("Run does not cover exactly the frozen reference")
    cases = []
    for cid in ids:
        source, truth = reference[cid]
        cases.append({"candidate_id": cid, "source_candidate_id": source["source_candidate_id"],
                      "family_id": source["family_id"], "reference": {axis: truth[axis] for axis in LABELS},
                      "predictions": {axis: indexed.get((cid, axis), {}).get("accepted_label") for axis in LABELS},
                      "decisions": {axis: indexed.get((cid, axis), {}).get("decision", "not_run") for axis in LABELS}})
    summaries = {}
    for axis in LABELS:
        pairs = [(case["reference"][axis], case["predictions"][axis]) for case in cases]
        m = metrics(pairs, axis)
        m["unscored_cases"] = m.pop("provider_or_contract_errors")
        m["agreement_count"] = sum(truth == pred for truth, pred in pairs)
        m["agreement_denominator"] = len(pairs)
        m["terminal_outcomes"] = dict(Counter(case["decisions"][axis].split("(")[0] for case in cases))
        summaries[axis] = m
    historical = json.loads((REFERENCE / "comparison.json").read_text())["summaries"]["code_plus_architecture_profile"]["0"]
    historical_run = json.loads((ROOT / "runs/2026-10-05-intent-profile-ablation/run-1/run.json").read_text())
    historical_rows = {row["candidate_id"]: row["response"]["output"] for row in historical_run["rows"]
                       if row["repeat"] == 0 and row["arm"] == "code_plus_architecture_profile"}
    usage = {key: sum((r.get("metadata") or {}).get("usage", {}).get(key) or 0 for r in rows if (r.get("metadata") or {}).get("usage"))
             for key in ("input_tokens", "output_tokens")}
    report = {"schema_version": 1, "reference_kind": "independent_model_annotation", "human_adjudicated": False,
              "holdout": False, "completed": receipt["completed"], "summaries": summaries, "cases": cases,
              "usage": usage, "elapsed_seconds": receipt["elapsed_seconds"],
              "returned_models": sorted({r["metadata"]["returned_model"] for r in rows if r.get("metadata")}),
              "historical_profile_agreement": {axis: historical[axis]["exact_agreement"] for axis in LABELS},
              "historical_label_changes": [case["source_candidate_id"] for case in cases if
                    any(case["predictions"][axis] is not None and
                        case["predictions"][axis] != historical_rows[case["candidate_id"]][axis]["choice"] for axis in LABELS)],
              "limits": manifest["comparison_limits"] + " Eight purposive diagnostic cases with one model reference, not human-approved gold. No representative prevalence, calibration or generalization claim.",
              "artifact_digests": {name: sha(run / name) for name in ["manifest.json", "responses.jsonl", "receipt.json"]}}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score(args.run)
    with args.output.open("x") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps({"summaries": report["summaries"], "usage": report["usage"]}))


if __name__ == "__main__":
    main()
