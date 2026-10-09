#!/usr/bin/env python3
"""Offline same-byte repeat and representation comparison; never calls a provider."""
import argparse
import json
from pathlib import Path
from question_grouping import digest
from score_state_key_order import score as score_round
from state_key_order import load

ROOT = Path(__file__).parent
ANALYSIS_SOURCES = (
    "score_repeat_controls.py", "score_state_key_order.py", "state_key_order.py",
    "question_grouping.py", "experiment.py",
)


def verify_analysis(parent):
    analysis = json.loads((parent / "analysis-v2.json").read_text())
    actual = {name: digest((ROOT / name).read_bytes()) for name in ANALYSIS_SOURCES}
    if (analysis["analysis_revision"] != 2
            or analysis["implementation_digests"] != actual
            or analysis["protocol_sha256"] != digest((parent / "protocol.json").read_bytes())):
        raise ValueError("Analysis implementation or protocol provenance mismatch")
    return analysis


def compare(a, b):
    return {
        "label_changed": a["choice"] != b["choice"],
        "max_probability_delta": max(abs(a["probabilities"][k] - b["probabilities"][k]) for k in a["probabilities"]),
        "confidence_delta": abs(a["confidence"] - b["confidence"]),
    }


def score(parent):
    analysis = verify_analysis(parent)
    protocol = json.loads((parent / "protocol.json").read_text())
    if protocol["rounds"] != 2 or protocol["max_requests"] != 32 or len(protocol["runs"]) != 2:
        raise ValueError("Unexpected repeat protocol")
    plans, reports, rows = [], [], []
    for i, entry in enumerate(protocol["runs"], 1):
        run = parent / f"round-{i}"
        if Path(entry["path"]).name != run.name or digest((run / "manifest.json").read_bytes()) != entry["manifest_sha256"]:
            raise ValueError("Round manifest provenance mismatch")
        _, plan = load(run)
        plans.append({(p["candidate_id"], p["arm"]):p["wire_sha256"] for p in plan})
        if (run / "receipt.json").exists():
            reports.append(score_round(run))
            rows.append({(r["candidate_id"],r["arm"]):r for r in [json.loads(line) for line in (run / "responses.jsonl").read_text().splitlines()] if r["error"] is None})
        else:
            if (run / "responses.jsonl").exists():
                raise ValueError("Unfinalized round: responses have no receipt")
            reports.append(None)
            rows.append({})
    if plans[0] != plans[1]:
        raise ValueError("Same-byte control requests differ between rounds")
    same_byte = []
    for key in plans[0]:
        if key not in rows[0] or key not in rows[1]:
            continue
        for axis in ["opportunity", "concern_kind"]:
            a, b = [r[key]["response"]["answers"][axis] for r in rows]
            same_byte.append({"candidate_id":key[0], "arm":key[1], "axis":axis, **compare(a,b)})
    cross_arm = []
    for i, rr in enumerate(rows, 1):
        for cid in dict.fromkeys(key[0] for key in plans[0]):
            if any((cid, arm) not in rr for arm in ["insertion", "canonical"]):
                continue
            for axis in ["opportunity", "concern_kind"]:
                a, b = [rr[cid,arm]["response"]["answers"][axis] for arm in ["insertion", "canonical"]]
                cross_arm.append({"round":i, "candidate_id":cid, "axis":axis, **compare(a,b)})
    summary = {}
    for name, comparisons in [("same_byte",same_byte), ("cross_arm",cross_arm)]:
        summary[name] = {}
        for axis in ["opportunity", "concern_kind"]:
            selected = [c for c in comparisons if c["axis"] == axis]
            summary[name][axis] = {
                "scored_comparisons":len(selected), "planned_comparisons":16,
                "label_changes":sum(c["label_changed"] for c in selected),
                "max_probability_delta":max((c["max_probability_delta"] for c in selected), default=None),
                "max_confidence_delta":max((c["confidence_delta"] for c in selected), default=None),
            }
    return {
        "schema_version":2, "analysis_revision":2, "completed":all(r is not None and r["completed"] for r in reports),
        "planned_requests":32,
        "attempted_requests":sum(r["receipt"]["attempted_requests"] for r in reports if r),
        "observed_tokens":sum(r["receipt"]["observed_tokens"] for r in reports if r),
        "rounds":reports, "comparisons":summary,
        "same_byte_details":same_byte,"cross_arm_details":cross_arm,
        "protocol_sha256":digest((parent / "protocol.json").read_bytes()),
        "analysis_implementation_sha256":analysis["implementation_digests"]["score_repeat_controls.py"],
        "analysis_implementation_digests":analysis["implementation_digests"],
        "analysis_manifest_sha256":digest((parent / "analysis-v2.json").read_bytes()),
        "limits":"Two repeats per arm; no human gold, holdout or statistical significance. Upstream cache and immutable backend checkpoint are not observable. Previous runs are not pooled with these controls.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    report = score(args.run)
    with args.output.open("x") as out:
        json.dump(report,out,indent=2)
        out.write("\n")
    print(json.dumps({k:report[k] for k in ["completed","attempted_requests","observed_tokens","comparisons"]}))


if __name__ == "__main__":
    main()
