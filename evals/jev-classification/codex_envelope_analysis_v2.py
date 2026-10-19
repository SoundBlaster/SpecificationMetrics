"""Offline consumer v2: diagnose a single interrupted in-flight request.

The producer, v1 analysis and frozen observations are unchanged. Scoring below
is copied from v1; only interrupted-prefix acceptance and diagnostic metadata
are new. This module has no live execution entry point.
"""

import argparse
from pathlib import Path

from codex_envelope_ablation_v1 import (
    ARMS, CASES, REFERENCE, RULES, RUN, STUDY, NativeProposal,
    decode, encoded, producer_digests, require, sdk_exchange, sha, verify,
)


def analyze(run):
    manifest = verify(run)
    result_receipt = decode((run / "result-receipt.json").read_bytes())
    names = ("manifest.json", "preparation-receipt.json", "attempts.jsonl", "responses.jsonl", "receipt.json")
    require(result_receipt["study"] == STUDY
            and result_receipt["experiment_producer_sha256"] == producer_digests()
            and result_receipt["files_sha256"] == {n: sha((run / n).read_bytes()) for n in names}, "capture receipt binding")
    receipt = decode((run / "receipt.json").read_bytes())
    require(receipt["manifest_sha256"] == sha((run / "manifest.json").read_bytes())
            and receipt["producer_digests"] == manifest["producer_digests"], "transport receipt binding")
    rows = [decode(line) for line in (run / "responses.jsonl").read_bytes().splitlines()]
    events = [decode(line) for line in (run / "attempts.jsonl").read_bytes().splitlines()]
    attempted = receipt["attempted_requests"]
    require(type(attempted) is int and 0 <= len(rows) <= attempted <= 12, "response prefix count")
    missing = attempted - len(rows)
    interrupted = (receipt["completed"] is False and receipt["attempt_ledger_complete"] is False
                   and isinstance(receipt["stop_reason"], str) and bool(receipt["stop_reason"]))
    require(missing == 0 or (missing == 1 and interrupted), "response prefix count")
    pending = manifest["requests"][len(rows)]["request_id"] if missing else None
    allowed = {item["request_id"] for item in manifest["requests"][:attempted]}
    require(all(event["request_id"] in allowed for event in events), "attempt outside response prefix")
    if pending:
        require(sum(event["event"] == "attempt_started" and event["request_id"] == pending
                    for event in events) <= 3, "in-flight attempt budget")
    require(sum(e["event"] == "attempt_started" for e in events) == receipt["network_attempts"] <= 36,
            "attempt ledger count")
    require(sum(e["event"] == "post_may_start" for e in events) == receipt["potentially_billable_posts"], "POST ledger count")
    references = {r["case_id"]: r["labels"] for r in decode(REFERENCE.read_bytes())["views"] if r["arm"] == "baseline"}
    decoded = []
    for item, row in zip(manifest["requests"], rows):
        require(row["request_id"] == item["request_id"] and row["wire_sha256"] == item["wire_sha256"], "response request binding")
        ledger = [e for e in events if e["request_id"] == item["request_id"]]
        require(sum(e["event"] == "attempt_started" for e in ledger) == row["network_attempts"]
                and 1 <= row["network_attempts"] <= 3, "per-request attempts")
        observation = dict(request_id=item["request_id"], case_id=item["case_id"], arm=item["arm"],
            repeat=item["repeat"], status=row["status"], answers=None,
            elapsed_seconds=sum(a["elapsed_seconds"] + a["backoff_seconds"] for a in row["attempts"]))
        if row["status"] == "json_received":
            try:
                _, result = sdk_exchange(manifest["tasks"][item["case_id"]], row["response"])
                answers = dict(result.answers)
                candidate = NativeProposal(*(answers[k] for k in ("concern_kind", "evidence_confidence", "ownership", "tool_responsibility")))
                violations = [code for spec, code in RULES if not spec.is_satisfied_by(candidate)]
                observation.update(status="decoded", answers=answers, consistency_violations=violations,
                    matching_axes=sum(v == references[item["case_id"]][k] for k, v in answers.items()),
                    complete_reference_agreement=answers == references[item["case_id"]],
                    returned_model=result.returned_model,
                    usage=(dict(input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens) if result.usage else None))
            except Exception as error:
                observation["status"] = type(error).__name__
        decoded.append(observation)
    complete = receipt["completed"] and receipt["attempt_ledger_complete"] and len(rows) == 12
    require(not receipt["completed"] or len(rows) == 12, "false cohort completeness")
    summary = {}
    for arm in ARMS:
        valid = [r for r in decoded if r["arm"] == arm and r["answers"] is not None]
        metered = [r for r in valid if r["usage"] is not None]
        summary[arm] = dict(valid_responses=len(valid), planned_responses=6, planned_axis_slots=24,
            matching_axes=sum(r["matching_axes"] for r in valid),
            complete_reference_views=sum(r["complete_reference_agreement"] for r in valid),
            consistency_review=sum(bool(r["consistency_violations"]) for r in valid),
            reported_usage_responses=len(metered),
            reported_input_tokens=sum(r["usage"]["input_tokens"] for r in metered) if metered else None,
            reported_output_tokens=sum(r["usage"]["output_tokens"] for r in metered) if metered else None,
            elapsed_attempt_backoff_seconds=sum(r["elapsed_seconds"] for r in decoded if r["arm"] == arm))
    ownership = {arm: [r["answers"]["ownership"] for r in decoded
                 if r["case_id"] == "R01" and r["arm"] == arm and r["answers"]] for arm in ARMS}
    usable = complete and all(r["status"] == "decoded" for r in decoded)
    prediction = ownership == {"minimal": ["existing_specification"] * 2, "codex_default": ["unknown"] * 2}
    identical_stable_owner = len({label for labels in ownership.values() for label in labels}) == 1
    hypothesis_status = ("not_evaluable" if not usable else "pattern_supported_small_sample" if prediction else
                         "not_supported_same_stable_owner" if identical_stable_owner else "inconclusive")
    repeatability = []
    for case in CASES:
        for arm in ARMS:
            pair = [r["answers"] for r in decoded if r["case_id"] == case and r["arm"] == arm and r["answers"]]
            repeatability.append(dict(case_id=case, arm=arm, observed=len(pair),
                                     same_labels=(pair[0] == pair[1]) if len(pair) == 2 else None))
    return dict(consumer="specmetrics.codex-envelope-analysis/v2",
        in_flight_request_without_response=pending, study=STUDY, status="complete_descriptive_comparison" if usable else "incomplete_not_evaluable",
        arms=summary, observations=decoded, r01_ownership=ownership, repeatability=repeatability,
        hypothesis_status=hypothesis_status, narrow_hypothesis_supported=prediction if usable else None,
        semantic_accuracy=None, exact_cli_cause_established=False, automatic_fact_acceptance=False,
        metric_effect="none", new_sol_calls=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=RUN)
    print(encoded(analyze(parser.parse_args().directory)))
