#!/usr/bin/env python3
"""Offline reference agreement and metamorphic-invariance scoring."""
import argparse
import json
from pathlib import Path
from experiment import LABELS, metrics
from question_grouping import digest, parse_response
from state_key_order import load, load_wire

ROOT = Path(__file__).parent
REF = ROOT / "runs/2026-10-05-intent-profile-reference"


def score(run):
    manifest, plan = load(run)
    rows = [json.loads(line) for line in (run / "responses.jsonl").read_text().splitlines()]
    receipt = json.loads((run / "receipt.json").read_text())
    if (receipt["planned_requests"] != len(plan) or type(receipt["completed"]) is not bool
            or len(rows) > len(plan) or receipt["attempted_requests"] != len(rows)):
        raise ValueError("Invalid receipt count")
    if receipt["completed"] and (len(rows) != len(plan) or any(r["error"] for r in rows)
                                 or receipt["stop_reason"] is not None):
        raise ValueError("False completion receipt")
    indexed = {}
    for item, row in zip(plan, rows):
        if any(item[k] != row[k] for k in ["candidate_id", "arm", "wire_sha256"]):
            raise ValueError("Response is not bound to exact planned bytes")
        _, body = load_wire(item)
        if row["error"] is None:
            parse_response(json.dumps(row["response"]).encode(), body["questions"])
        indexed[item["candidate_id"], item["arm"]] = row
    annotations = {a["case_id"]:a for a in json.loads((REF / "annotations.json").read_text())["annotations"]}
    mapping = {e["ablation_candidate_id"]:(e,annotations[e["case_id"]]) for e in json.loads((REF / "mapping.json").read_text())["entries"]}
    ids = list(dict.fromkeys(i["candidate_id"] for i in plan))
    if set(ids) != set(mapping):
        raise ValueError("Reference coverage mismatch")
    cases = []
    for cid in ids:
        predictions = {}
        for arm in ["insertion", "canonical"]:
            row = indexed.get((cid, arm)) or {}
            predictions[arm] = {axis: ((row.get("response") or {}).get("answers",{}).get(axis,{}) or {}).get("choice") if not row.get("error") else None for axis in LABELS}
        cases.append({"candidate_id":cid,"source_candidate_id":mapping[cid][0]["source_candidate_id"],
                      "reference":{axis:mapping[cid][1][axis] for axis in LABELS},"predictions":predictions})
    summaries = {arm:{axis:metrics([(c["reference"][axis],c["predictions"][arm][axis]) for c in cases],axis) for axis in LABELS} for arm in ["insertion","canonical"]}
    for arm in summaries:
        for axis, m in summaries[arm].items():
            m["unscored_cases"] = m.pop("provider_or_contract_errors")
            m["not_run_cases"] = sum((c["candidate_id"],arm) not in indexed for c in cases)
            m["agreement_count"] = sum(c["reference"][axis] == c["predictions"][arm][axis] for c in cases)
            m["agreement_denominator"] = 8
    paired, differences = {}, []
    for axis in LABELS:
        valid = [c for c in cases if all(c["predictions"][arm][axis] is not None for arm in summaries)]
        paired[axis] = {"paired_scored_cases":len(valid),"changed_labels":[c["source_candidate_id"] for c in valid if c["predictions"]["insertion"][axis] != c["predictions"]["canonical"][axis]]}
        for c in valid:
            a = indexed[c["candidate_id"],"insertion"]["response"]["answers"][axis]
            b = indexed[c["candidate_id"],"canonical"]["response"]["answers"][axis]
            differences.append({"source_candidate_id":c["source_candidate_id"],"axis":axis,
                                "max_probability_delta":max(abs(a["probabilities"][label]-b["probabilities"][label]) for label in a["probabilities"]),
                                "confidence_delta":abs(a["confidence"]-b["confidence"])})
    usage = {arm:{key:sum(((row.get("response") or {}).get("usage") or {}).get(key) or 0 for row in rows if row["arm"] == arm and row["error"] is None) for key in ["input_tokens","output_tokens"]} for arm in summaries}
    return {"schema_version":1,"study_kind":manifest["study_kind"],"completed":receipt["completed"],"reference_kind":"independent_model_annotation","human_adjudicated":False,"holdout":False,
            "receipt":receipt,"summaries":summaries,"paired":paired,"cases":cases,"numeric_differences":differences,"usage":usage,
            "label_invariance":None if not receipt["completed"] else not any(p["changed_labels"] for p in paired.values()),
            "max_probability_delta":max((d["max_probability_delta"] for d in differences),default=None),
            "max_confidence_delta":max((d["confidence_delta"] for d in differences),default=None),
            "artifact_digests":{name:digest((run/name).read_bytes()) for name in ["manifest.json","responses.jsonl","receipt.json"]},
            "limits":"Eight purposive cases, one sample per arm and one model reference. Wire-order sensitivity is separate from correctness; it does not establish human gold, project-wide accuracy, statistical significance or immutable model behavior."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    args=p.parse_args();value=score(args.run)
    with args.output.open("x") as f:
        json.dump(value,f,indent=2);f.write("\n")
    print(json.dumps({"completed":value["completed"],"paired":value["paired"],"usage":value["usage"]}))


if __name__ == "__main__":
    main()
