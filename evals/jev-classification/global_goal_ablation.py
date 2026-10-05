#!/usr/bin/env python3
"""Compare Jev with and without the versioned SpecificationCore intent profile."""

import argparse
import copy
import json
from pathlib import Path

from experiment import digest, metrics, write

ROOT = Path(__file__).parent
EXPECTED_IDS = ["sg-017", "sg-018", "sg-019", "sg-020", "sg-031", "sg-032", "sg-033", "sg-034"]
ARMS = ["code", "code_plus_architecture_profile"]
PROFILE_PATH = ROOT / "specificationcore-intent-profile-v2.json"


def build(source_study_path):
    source_study = json.loads(source_study_path.read_text())
    if source_study.get("study_kind") != "diagnostic_context_ablation" or source_study.get("holdout") is not False:
        raise ValueError("source must be the frozen diagnostic context-ablation study")
    if source_study.get("arms") != ["code", "code_task", "code_task_facts"]:
        raise ValueError("unexpected source-study arms")
    if [case["source_candidate_id"] for case in source_study["cases"]] != EXPECTED_IDS:
        raise ValueError("unexpected case selection or order")
    profile_bytes = PROFILE_PATH.read_bytes()
    profile = json.loads(profile_bytes)
    prompt_source_path = ROOT / "runs/2026-10-05-independent-reference/development.json"
    prompt_source_bytes = prompt_source_path.read_bytes()
    prompt_config = json.loads(prompt_source_bytes)["prompt_configs"]["baseline-v1"]
    cases = []
    for case in source_study["cases"]:
        state = json.loads(case["contexts"]["code"]["state"])
        variants = {"code": copy.deepcopy(state), "code_plus_architecture_profile": copy.deepcopy(state)}
        variants["code_plus_architecture_profile"]["architecture_profile"] = profile
        contexts = {}
        for arm, value in variants.items():
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode()) > 24 * 1024:
                raise ValueError("context exceeds 24 KiB")
            contexts[arm] = {"state": encoded, "sha256": digest(encoded.encode())}
        cases.append({key: case[key] for key in ("candidate_id", "source_candidate_id", "family_id", "opportunity", "concern_kind")} |
                     {"contexts": contexts})
    return {
        "schema_version": 1,
        "study_kind": "diagnostic_specificationcore_goal_profile_ablation",
        "reference_kind": "pre_profile_independent_model_annotation",
        "human_adjudicated": False,
        "holdout": False,
        "arms": ARMS,
        "repeats": 2,
        "prompt_config": prompt_config,
        "prompt_source_sha256": digest(prompt_source_bytes),
        "source_study_sha256": digest(source_study_path.read_bytes()),
        "architecture_profile": {"id": profile["id"], "version": profile["version"],
                                  "sha256": digest(profile_bytes), "path": str(PROFILE_PATH.relative_to(ROOT))},
        "cases": cases,
        "protocol": {
            "independent_variable": "The profile arm adds only the frozen architecture_profile object; its code state otherwise begins as the byte-equivalent code-only state.",
            "prompt": "baseline-v1 copied unchanged from the recorded prompt experiment.",
            "selection": "The same eight purposive diagnostic cases used by the context-ablation study; not representative and not a new holdout.",
            "hypothesis": "The explicit project intent changes Jev's opportunity assessment for stable product policies that the pre-profile prompt may under-recognize, while leaving mechanical controls and already-owned specifications excluded.",
            "directional_criteria": {
                "eligible_policy_cases": "For at least one pre-profile eligible policy, move from a non-eligible baseline decision to eligible in the profile arm in both repeats; report all case-level changes.",
                "already_owned_cases": "Keep sg-018 and sg-020 excluded in both repeats; profile context is not ownership proof.",
                "mechanics_cases": "Keep sg-031, sg-032, and sg-034 excluded in both repeats.",
                "diagnostic_agreement": "Report agreement with inherited pre-profile labels only as sensitivity; do not interpret it as accuracy or as the profile's gold-standard quality."
            },
            "refutation": "Any mechanical control moves to eligible, an already-owned rule moves to eligible, a pre-profile eligible policy moves to excluded, or no eligible-policy case moves from a non-eligible baseline decision to eligible in both repeats: directional hypothesis not supported.",
            "limits": "The inherited annotations predate the profile and therefore encode the older question. This is a paired sensitivity experiment, not confirmatory evidence that Jev now correctly reflects the project architecture goal. Two repeats measure local consistency, not sample size."
        }
    }


def _prediction(row):
    response = row["response"]
    output = response.get("output", {}) if isinstance(response, dict) else {}
    if not isinstance(output, dict) or response.get("error") or row.get("error"):
        return {"opportunity": None, "concern_kind": None}
    values = {"opportunity": output.get("opportunity", {}).get("choice"),
              "concern_kind": output.get("concern_kind", {}).get("choice")}
    if values["opportunity"] not in {"eligible", "excluded", "needs_review"}:
        values["opportunity"] = None
    if values["concern_kind"] not in {"policy", "mechanics", "variant_behavior", "unknown"}:
        values["concern_kind"] = None
    return values


def score(study, run):
    if run.get("study_sha256") != digest((json.dumps(study, ensure_ascii=False, indent=2) + "\n").encode()):
        raise ValueError("study digest mismatch")
    if run.get("prompt_sha256") != digest(json.dumps(study["prompt_config"], ensure_ascii=False, separators=(",", ":")).encode()):
        raise ValueError("prompt digest mismatch")
    if run.get("architecture_profile_sha256") != study["architecture_profile"]["sha256"]:
        raise ValueError("profile digest mismatch")
    lookup = {case["candidate_id"]: case for case in study["cases"]}
    rows = {}
    for row in run.get("rows", []):
        key = (row["repeat"], row["arm"], row["candidate_id"])
        if key in rows or row["candidate_id"] not in lookup or row["arm"] not in study["arms"]:
            raise ValueError("duplicate or unexpected row")
        context = lookup[row["candidate_id"]]["contexts"][row["arm"]]
        if row.get("context_sha256") != context["sha256"]:
            raise ValueError("context receipt mismatch")
        rows[key] = _prediction(row)
    expected = {(repeat, arm, candidate_id) for repeat in range(study["repeats"])
                for arm in study["arms"] for candidate_id in lookup}
    if set(rows) != expected or not run.get("completed"):
        raise ValueError("incomplete run")

    summaries = {}
    for arm in study["arms"]:
        summaries[arm] = {}
        for repeat in range(study["repeats"]):
            summary = {axis: metrics([(case[axis], rows[repeat, arm, cid][axis])
                                      for cid, case in lookup.items()], axis)
                       for axis in ("opportunity", "concern_kind")}
            summary["pre_profile_reference_agreement"] = sum(
                rows[repeat, arm, cid]["opportunity"] == case["opportunity"]
                for cid, case in lookup.items()) / len(lookup)
            summary["inherited_eligible_policy_now_excluded"] = [cid for cid, case in lookup.items()
                if case["opportunity"] == "eligible" and case["concern_kind"] == "policy"
                and rows[repeat, arm, cid]["opportunity"] == "excluded"]
            summary["already_owned_not_excluded"] = [cid for cid, case in lookup.items()
                if case["source_candidate_id"] in {"sg-018", "sg-020"}
                and rows[repeat, arm, cid]["opportunity"] != "excluded"]
            summary["eligible_policy_promoted_from_baseline"] = [cid for cid, case in lookup.items()
                if case["opportunity"] == "eligible" and case["concern_kind"] == "policy"
                and rows[repeat, "code", cid]["opportunity"] in {"excluded", "needs_review"}
                and rows[repeat, arm, cid]["opportunity"] == "eligible"]
            summary["mechanics_eligible"] = [cid for cid, case in lookup.items()
                if case["concern_kind"] == "mechanics" and rows[repeat, arm, cid]["opportunity"] == "eligible"]
            summary["mechanical_controls_not_excluded"] = [cid for cid, case in lookup.items()
                if case["concern_kind"] == "mechanics" and rows[repeat, arm, cid]["opportunity"] != "excluded"]
            summaries[arm][str(repeat)] = summary
        summaries[arm]["repeat_disagreements"] = [cid for cid in lookup
            if rows[0, arm, cid] != rows[1, arm, cid]]
    cases = [{"candidate_id": cid, "source_candidate_id": case["source_candidate_id"],
              "reference": {axis: case[axis] for axis in ("opportunity", "concern_kind")},
              "outputs": {arm: [rows[repeat, arm, cid] for repeat in range(study["repeats"])] for arm in study["arms"]},
              "profile_effect_by_repeat": [
                  {axis: {"baseline": rows[repeat, "code", cid][axis],
                          "profile": rows[repeat, "code_plus_architecture_profile", cid][axis]}
                   for axis in ("opportunity", "concern_kind")}
                  for repeat in range(study["repeats"])]} for cid, case in lookup.items()]
    directional = {
        "eligible_policy_promoted_in_both_repeats": bool(
            set(summaries["code_plus_architecture_profile"]["0"]["eligible_policy_promoted_from_baseline"])
            & set(summaries["code_plus_architecture_profile"]["1"]["eligible_policy_promoted_from_baseline"])),
        "already_owned_cases_remain_excluded": all(not summaries["code_plus_architecture_profile"][str(r)]["already_owned_not_excluded"]
                                                    for r in range(study["repeats"])),
        "mechanics_remain_excluded": all(not summaries["code_plus_architecture_profile"][str(r)]["mechanical_controls_not_excluded"]
                                          for r in range(study["repeats"])),
        "inherited_reference_disagreement_cases": sorted({cid
            for repeat in range(study["repeats"])
            for cid in summaries["code_plus_architecture_profile"][str(repeat)]["inherited_eligible_policy_now_excluded"]})
    }
    return {"study_kind": study["study_kind"], "reference_kind": study["reference_kind"],
            "human_adjudicated": False, "holdout": False, "interpretation": "diagnostic_sensitivity_only",
            "architecture_profile": study["architecture_profile"], "summaries": summaries,
            "directional_criteria": directional, "cases": cases,
            "limits": study["protocol"]["limits"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source-study", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    rescore = commands.add_parser("score")
    rescore.add_argument("--study", type=Path, required=True)
    rescore.add_argument("--run", type=Path, required=True)
    rescore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to replace a study/report")
    result = build(args.source_study) if args.command == "prepare" else score(
        json.loads(args.study.read_text()), json.loads(args.run.read_text()))
    write(args.output, result)
    print("Saved " + str(args.output))


if __name__ == "__main__":
    main()
