#!/usr/bin/env python3
"""Offline paired native Choice scoring, retaining incomplete-run denominators."""
import argparse
import json
from collections import Counter
from pathlib import Path
from experiment import LABELS, metrics
from question_grouping import digest, validate_plan, load_plan

ROOT = Path(__file__).parent
REF = ROOT / "runs/2026-10-05-intent-profile-reference"


def score(run):
    manifest = json.loads((run / "manifest.json").read_text())
    for name, expected in manifest["digests"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("Input provenance mismatch")
    plan = load_plan(run, manifest)
    validate_plan(plan)
    rows = [json.loads(line) for line in (run / "responses.jsonl").read_text().splitlines()]
    receipt = json.loads((run / "receipt.json").read_text())
    if receipt["attempted_requests"] != len(rows):
        raise ValueError("Receipt count mismatch")
    if receipt["completed"] and (len(rows) != len(plan) or any(row["error"] for row in rows)):
        raise ValueError("False completion receipt")
    results, seen = {}, set()
    for index, row in enumerate(rows):
        item = plan[index]
        if any(row[key] != item[key] for key in ["candidate_id", "arm", "axes", "body_sha256"]):
            raise ValueError("Response not bound to ordered plan")
        for axis in row["axes"]:
            key = (row["candidate_id"], row["arm"], axis)
            if key in seen:
                raise ValueError("Duplicate result")
            seen.add(key)
            label = None if row["error"] else row["response"]["answers"][axis]["choice"]
            if label is not None and label not in LABELS[axis]:
                raise ValueError("Unexpected semantic label")
            results[key] = label
    anns = {a["case_id"]: a for a in json.loads((REF / "annotations.json").read_text())["annotations"]}
    mapping = {e["ablation_candidate_id"]: (e, anns[e["case_id"]]) for e in json.loads((REF / "mapping.json").read_text())["entries"]}
    ids = list(dict.fromkeys(item["candidate_id"] for item in plan))
    if set(ids) != set(mapping):
        raise ValueError("Reference coverage mismatch")
    cases = [{"candidate_id": cid, "source_candidate_id": mapping[cid][0]["source_candidate_id"],
              "reference": {axis: mapping[cid][1][axis] for axis in LABELS},
              "predictions": {arm: {axis: results.get((cid, arm, axis)) for axis in LABELS} for arm in ["joint", "separate"]}} for cid in ids]
    summaries = {arm: {axis: metrics([(c["reference"][axis], c["predictions"][arm][axis]) for c in cases], axis) for axis in LABELS} for arm in ["joint", "separate"]}
    for arm in summaries:
        for axis, m in summaries[arm].items():
            m["unscored_cases"] = m.pop("provider_or_contract_errors")
            m["not_run_cases"] = sum((c["candidate_id"], arm, axis) not in results for c in cases)
            m["agreement_count"] = sum(c["reference"][axis] == c["predictions"][arm][axis] for c in cases)
            m["agreement_denominator"] = 8
            m["planned_eligible_reference_count"] = sum(c["reference"][axis] == "eligible" for c in cases) if axis == "opportunity" else None
    paired = {}
    for axis in LABELS:
        valid = [c for c in cases if all(c["predictions"][arm][axis] is not None for arm in ["joint", "separate"])]
        paired[axis] = {"paired_scored_cases":len(valid),
            "changed_labels":[c["source_candidate_id"] for c in valid if c["predictions"]["joint"][axis] != c["predictions"]["separate"][axis]],
            "joint_only_correct":[c["source_candidate_id"] for c in valid if c["predictions"]["joint"][axis] == c["reference"][axis] and c["predictions"]["separate"][axis] != c["reference"][axis]],
            "separate_only_correct":[c["source_candidate_id"] for c in valid if c["predictions"]["separate"][axis] == c["reference"][axis] and c["predictions"]["joint"][axis] != c["reference"][axis]]}
    usage = {arm: {key: sum(((r.get("response") or {}).get("usage") or {}).get(key) or 0 for r in rows if r["arm"] == arm) for key in ["input_tokens", "output_tokens"]} for arm in summaries}
    return {"schema_version":1, "reference_kind":"independent_model_annotation", "human_adjudicated":False, "holdout":False,
        "completed":receipt["completed"], "receipt":receipt, "summaries":summaries, "paired":paired, "cases":cases, "usage":usage,
        "returned_models": sorted({r["response"]["model"] for r in rows if r.get("response")}),
        "request_errors":dict(Counter(r["error"] for r in rows if r["error"])),
        "artifact_digests": {name: digest((run/name).read_bytes()) for name in ["manifest.json","responses.jsonl","receipt.json"]},
        "limits":"Eight purposive diagnostic examples, one sample per arm and one independent model reference. Same native transport in both arms; not a RustJev batch feature, human gold, calibrated accuracy or representative prevalence. Timing/backend variation remains uncontrolled."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    value=score(args.run)
    with args.output.open("x") as f:
        json.dump(value,f,indent=2);f.write("\n")
    print(json.dumps({"summaries":value["summaries"],"paired":value["paired"],"usage":value["usage"]}))


if __name__ == "__main__":
    main()
