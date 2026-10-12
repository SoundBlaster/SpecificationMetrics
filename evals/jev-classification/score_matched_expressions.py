#!/usr/bin/env python3
"""Offline raw-provider scoring against the frozen model reference; no inference."""
import argparse
from collections import Counter
import json
from pathlib import Path

from coreinfra_retry_run import decode
from matched_expression_plan import REFERENCE, inspect_results
from question_grouping import digest

AXES = ("opportunity", "concern_kind")
PROVIDERS = ("jev-coreinfra", "luna-decision-coreinfra")


def summarize(native, annotations):
    reference = {r["case_id"]: r for r in annotations["annotations"]}
    if len(reference) != 8 or native["planned_requests"] != 32:
        raise ValueError("Expected eight cases and 32 planned requests")
    rows = {}
    for row in native["rows"]:
        key = (row["provider"], row["repeat"], row["case_id"])
        if key in rows or key[0] not in PROVIDERS or key[1] not in (1, 2) or key[2] not in reference:
            raise ValueError("Unexpected or duplicate comparison row")
        rows[key] = row
    reports = []
    for provider in PROVIDERS:
        repeats = []
        for repeat in (1, 2):
            valid = {cid: rows[(provider, repeat, cid)]["prediction"]["answers"] for cid in reference
                     if (provider, repeat, cid) in rows and rows[(provider, repeat, cid)]["native_status"] == "valid"}
            axes = {}
            for axis in AXES:
                confusion = Counter((reference[cid][axis], answers[axis]["choice"]) for cid, answers in valid.items())
                axes[axis] = {"matched": sum(n for (a, b), n in confusion.items() if a == b),
                              "planned": 8, "native_valid": len(valid),
                              "confusion": [{"reference": a, "prediction": b, "count": n}
                                            for (a, b), n in sorted(confusion.items())]}
            eligible = [cid for cid, ref in reference.items() if ref["opportunity"] == "eligible"]
            excluded = [cid for cid, ref in reference.items() if ref["opportunity"] == "excluded"]
            recalled = sum(cid in valid and valid[cid]["opportunity"]["choice"] == "eligible" for cid in eligible)
            false_positives = [cid for cid in excluded if cid in valid and valid[cid]["opportunity"]["choice"] == "eligible"]
            missed_eligible = [cid for cid in eligible if cid not in valid or valid[cid]["opportunity"]["choice"] != "eligible"]
            strata = {}
            for concern in ("policy", "mechanics"):
                ids = [cid for cid in excluded if reference[cid]["concern_kind"] == concern]
                strata[concern] = {"planned": len(ids), "native_valid": sum(cid in valid for cid in ids),
                                   "false_positive_ids": [cid for cid in false_positives if cid in ids]}
            passed = (len(valid) == 8 and all(axes[a]["matched"] >= 7 for a in AXES)
                      and not false_positives and bool(eligible) and recalled == len(eligible))
            repeats.append({"repeat": repeat, "native_valid": len(valid), "planned": 8, "axes": axes,
                            "eligible_recall": {"recovered": recalled, "planned": len(eligible)},
                            "missed_or_unavailable_eligible_ids": missed_eligible,
                            "excluded_control_strata": strata, "false_positive_ids": false_positives,
                            "preregistered_repeat_criteria_passed": passed})
        disagreements = []
        confidence_deltas, probability_deltas = [], []
        paired = 0
        for cid in reference:
            pair = [rows.get((provider, repeat, cid)) for repeat in (1, 2)]
            if not all(r is not None and r["native_status"] == "valid" for r in pair):
                continue
            for axis in AXES:
                paired += 1
                a, b = [r["prediction"]["answers"][axis] for r in pair]
                if a["choice"] != b["choice"]:
                    disagreements.append({"case_id": cid, "axis": axis, "repeat_1": a["choice"], "repeat_2": b["choice"]})
                confidence_deltas.append(abs(a["confidence"] - b["confidence"]))
                probability_deltas.extend(abs(a["probabilities"][label] - b["probabilities"][label]) for label in a["probabilities"])
        reports.append({"provider": provider, "repeats": repeats,
                        "repeat_consistency": {"paired_axis_answers": paired, "planned_axis_pairs": 16,
                                               "label_disagreements": disagreements,
                                               "max_native_confidence_delta": max(confidence_deltas, default=None),
                                               "max_option_probability_delta": max(probability_deltas, default=None),
                                               "passed": paired == 16 and not disagreements},
                        "preregistered_provider_criteria_passed": all(r["preregistered_repeat_criteria_passed"] for r in repeats) and paired == 16 and not disagreements})
    return {"schema_version": 1, "study_kind": "matched_expression_raw_provider_score",
            "reference_authority": annotations["authority"], "planned_requests": 32,
            "received_rows": native["received_rows"], "native_valid": native["native_valid"],
            "native_invalid": native["native_invalid"],
            "missing_result_request_ids": native["missing_result_request_ids"],
            "unattempted_request_ids": native["unattempted_request_ids"],
            "attempt_status_unknown_request_ids": native["attempt_status_unknown_request_ids"],
            "attempted_without_result_request_ids": native["attempted_without_result_request_ids"],
            "providers": reports, "formal_ownership_gate": "not_applied_raw_predictions_only",
            "metric_effect": "none", "inference_performed_by_scorer": False,
            "limits": "Eight development expressions, model reference not human gold. Repeats are not independent samples. No context-causality, calibration, generalization or production-readiness claim."}


def score(run):
    native = inspect_results(run)
    reference_path = REFERENCE / "independent-annotations.json"
    result = summarize(native, decode(reference_path.read_bytes()))
    result["evidence_sha256"] = {name: digest((run / name).read_bytes()) if (run / name).exists() else None
                                 for name in ("manifest.json", "responses.jsonl", "attempts.jsonl", "receipt.json")}
    result["reference_sha256"] = digest(reference_path.read_bytes())
    result["scorer_sha256"] = digest(Path(__file__).read_bytes())
    result["native_decoder_sha256"] = digest((Path(__file__).parent / "decision_choice_contract.py").read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.run)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write("\n")
    print(json.dumps({"native_valid": result["native_valid"], "planned": 32,
                      "providers": [{"provider": r["provider"], "passed": r["preregistered_provider_criteria_passed"]} for r in result["providers"]]}, indent=2))


if __name__ == "__main__":
    main()
