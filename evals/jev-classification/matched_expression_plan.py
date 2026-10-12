#!/usr/bin/env python3
"""Freeze and validate matched native wires. Offline by default; no scoring."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from coreinfra_retry_run import decode, execute, producer_digests
from coreinfra_transport import PROTOCOL, RetryPolicy
from decision_choice_contract import parse_response
from question_grouping import canonical, digest
from validate_expression_reference import validate as validate_reference

ROOT = Path(__file__).parent
REFERENCE = ROOT / "runs/2026-10-12-expression-reference"
PRODUCERS = ("matched_expression_plan.py", "decision_choice_contract.py", "validate_expression_reference.py")
PROVIDERS = (
    ("jev-coreinfra", "jev-1.13.0", "https://hub.coreinfra.ai/typesafe/api/v1/systemone"),
    ("luna-decision-coreinfra", "gpt-6-luna", "https://hub.coreinfra.ai/openai/api/v1/decisions"),
)


def build(reference=REFERENCE):
    packet = decode((reference / "reference-packet.json").read_bytes())
    annotations_raw = (reference / "independent-annotations.json").read_bytes()
    review_raw = (reference / "reference-review.json").read_bytes()
    annotations = decode(annotations_raw)
    validate_reference(packet, annotations)
    plan = decode((reference / "comparison-plan.json").read_bytes())
    if (plan["packet_sha256"] != digest(canonical(packet))
            or plan["reference_sha256"] != digest(annotations_raw)
            or plan["reference_review_sha256"] != digest(review_raw)
            or plan["reference_status"] != "independent_model_reference_reviewed_not_human_gold"):
        raise ValueError("Comparison reference binding changed")
    if (len(packet["cases"]) != 8 or plan["repeats"] != 2
            or plan["planned_logical_requests"] != 32 or plan["max_network_attempts"] != 96
            or plan["max_attempts_per_request"] != 3 or plan["retry_protocol"] != PROTOCOL):
        raise ValueError("Unexpected comparison budget")
    if [(p["id"], p["requested_model"], p["endpoint"]) for p in plan["providers"]] != list(PROVIDERS):
        raise ValueError("Provider contracts differ from reviewed comparison plan")
    questions = packet["questions"]
    if set(questions) != {"opportunity", "concern_kind"} or any(q["type"] != "choice" for q in questions.values()):
        raise ValueError("Expected two Choice questions")
    requests = []
    for repeat in range(2):
        for index, case in enumerate(packet["cases"]):
            state = canonical(case["state"])
            if digest(state) != case["state_sha256"] or len(state) > 16 * 1024:
                raise ValueError("Stale or oversized state")
            # Both providers receive the SAME canonical JSON text, not an object
            # in one API and a differently serialized string in the other.
            for provider, model, endpoint in PROVIDERS[::1 if (repeat + index) % 2 == 0 else -1]:
                if provider == "jev-coreinfra":
                    body = {"model": model, "state": state.decode(), "questions": questions}
                else:
                    body = {"model": model, "input": state.decode(), "questions": [
                        {"type": "choice", "name": axis, "instructions": q["instructions"],
                         "choices": [{"value": label, "description": description}
                                     for label, description in sorted(q["criteria"].items())]}
                        for axis, q in sorted(questions.items())]}
                wire = canonical(body)
                if len(wire) > 64 * 1024:
                    raise ValueError("Oversized request")
                requests.append({"request_id": f"r{repeat + 1}-{case['case_id']}-{provider}",
                                 "case_id": case["case_id"], "repeat": repeat + 1, "provider": provider,
                                 "state_sha256": digest(state), "questions_sha256": digest(canonical(questions)),
                                 "endpoint": endpoint, "wire_json": wire.decode(), "wire_sha256": digest(wire)})
    return {"protocol": PROTOCOL, "semantic_status": "unscored", "producer_digests": producer_digests(),
            "analysis_producer_digests": {n: digest((ROOT / n).read_bytes()) for n in PRODUCERS},
            "packet_sha256": digest(canonical(packet)), "reference_sha256": digest(annotations_raw),
            "reference_review_sha256": digest(review_raw),
            "comparison_plan_sha256": digest((reference / "comparison-plan.json").read_bytes()),
            "retry_policy": asdict(RetryPolicy()), "max_network_attempts": 96,
            "requests": requests, "metric_effect": "none",
            "encoding": "Identical canonical state text; identical question instructions and label descriptions, sorted axes/options. Native envelopes differ. No annotations, judgments, case IDs or reference instructions asking for citations enter provider inputs."}


def validate(run):
    saved = decode((run / "manifest.json").read_bytes())
    if canonical(saved) != canonical(build()):
        raise ValueError("Frozen manifest differs from current inputs or producers")
    return execute(run, live=False)


def inspect_results(run):
    """Keep transport failures, native contract failures and labels separate."""
    validate(run)
    manifest = decode((run / "manifest.json").read_bytes())
    packet = decode((REFERENCE / "reference-packet.json").read_bytes())
    expected = {r["request_id"]: r for r in manifest["requests"]}
    rows = []
    seen = set()
    for raw in (run / "responses.jsonl").read_bytes().splitlines():
        row = decode(raw)
        rid = row["request_id"]
        if rid not in expected or rid in seen:
            raise ValueError("Unexpected or duplicate result identity")
        request = expected[rid]
        if row["wire_sha256"] != request["wire_sha256"]:
            raise ValueError("Result is not bound to frozen request")
        seen.add(rid)
        result = {"request_id": rid, "provider": request["provider"], "case_id": request["case_id"],
                  "repeat": request["repeat"], "transport_status": row["status"],
                  "native_status": "not_evaluated", "prediction": None}
        if row["status"] == "json_received":
            try:
                result["prediction"] = parse_response(canonical(row["response"]),
                    provider=request["provider"], model=decode(request["wire_json"])["model"],
                    questions=packet["questions"])
                result["native_status"] = "valid"
            except (ValueError, TypeError, KeyError):
                result["native_status"] = "invalid"
        rows.append(result)
    return {"planned_requests": len(expected), "received_rows": len(rows),
            "unattempted_request_ids": [rid for rid in expected if rid not in seen],
            "native_valid": sum(r["native_status"] == "valid" for r in rows),
            "native_invalid": sum(r["native_status"] == "invalid" for r in rows),
            "rows": rows, "semantic_status": "unscored", "metric_effect": "none"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--live", action="store_true", help="Explicitly execute 32 requests / at most 96 attempts")
    parser.add_argument("--inspect-results", action="store_true", help="Offline native decoding; no semantic score")
    args = parser.parse_args()
    if sum([args.prepare, args.live, args.inspect_results]) > 1:
        parser.error("Preparation, live execution and offline result inspection are separate steps")
    if args.prepare:
        manifest = build()
        args.run.mkdir(parents=True, exist_ok=False)
        (args.run / "manifest.json").write_bytes(json.dumps(manifest, ensure_ascii=False, indent=2).encode() + b"\n")
    result = validate(args.run)
    if args.live:
        result = execute(args.run, live=True)
    elif args.inspect_results:
        result = inspect_results(args.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
