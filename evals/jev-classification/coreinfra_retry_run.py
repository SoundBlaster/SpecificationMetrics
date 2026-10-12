#!/usr/bin/env python3
"""Run a NEW frozen exact-wire CoreInfra transport diagnostic; no semantic scoring."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

from coreinfra_transport import PROTOCOL, RetryPolicy, endpoint_path, post
from question_grouping import unique_object, reject_constant


ROOT = Path(__file__).parent
PRODUCERS = ("coreinfra_transport.py", "coreinfra_retry_run.py", "question_grouping.py")
OUTPUTS = ("attempts.jsonl", "responses.jsonl", "receipt.json")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Non-finite JSON number")
        return number
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant, parse_float=finite_float)


def producer_digests():
    return {name: sha((ROOT / name).read_bytes()) for name in PRODUCERS}


def load(run):
    manifest_bytes = (run / "manifest.json").read_bytes()
    manifest = decode(manifest_bytes)
    if manifest.get("protocol") != PROTOCOL or manifest.get("semantic_status") != "unscored":
        raise ValueError("Expected a new transport-only protocol")
    policy = RetryPolicy(**manifest["retry_policy"])
    if manifest["producer_digests"] != producer_digests():
        raise ValueError("Producer implementation differs from frozen protocol")
    plan = manifest["requests"]
    if not isinstance(plan, list) or not 1 <= len(plan) <= 32:
        raise ValueError("Expected one to 32 logical requests")
    budget = manifest["max_network_attempts"]
    if type(budget) is not int or budget != len(plan) * policy.max_attempts:
        raise ValueError("Reserve the worst-case attempt budget, including retries")
    seen = set()
    for item in plan:
        rid = item["request_id"]
        if not isinstance(rid, str) or not rid or len(rid) > 128 or rid in seen:
            raise ValueError("Expected distinct bounded request IDs")
        seen.add(rid)
        endpoint_path(item["endpoint"])
        wire = item["wire_json"].encode("utf-8")
        if not 1 <= len(wire) <= 64 * 1024 or sha(wire) != item["wire_sha256"]:
            raise ValueError("Request byte bound or digest mismatch")
        body = decode(wire)
        if not isinstance(body, dict) or not isinstance(body.get("model"), str) or not body["model"]:
            raise ValueError("Every native request must select an explicit model")
    return manifest, policy, sha(manifest_bytes)


def execute(run, *, live=False, sender=post):
    manifest, policy, manifest_digest = load(run)
    if not live:
        return {"validated": True, "planned_requests": len(manifest["requests"]),
                "max_network_attempts": manifest["max_network_attempts"], "inference": False}
    key = os.environ.get("COREINFRA_API_KEY")
    if not key:
        raise ValueError("Missing COREINFRA_API_KEY")
    if any((run / name).exists() for name in OUTPUTS):
        raise ValueError("Refusing to repeat or overwrite a hosted run")
    # Exclusive creation also prevents a second process from starting this run.
    with (run / "attempts.jsonl").open("x", encoding="utf-8") as ledger:
        receipt = {"protocol": PROTOCOL, "manifest_sha256": manifest_digest,
                   "producer_digests": manifest["producer_digests"],
                   "retry_policy": asdict(policy), "started_at": datetime.now(timezone.utc).isoformat(),
                   "planned_requests": len(manifest["requests"]),
                   "max_network_attempts": manifest["max_network_attempts"],
                   "attempted_requests": 0, "received_json_responses": 0,
                   "network_attempts": 0, "potentially_billable_posts": 0,
                   "ambiguous_posts": 0, "duplicate_execution_possible": False,
                   "attempt_ledger_complete": True,
                   "completed": False, "stop_reason": None, "semantic_status": "unscored"}
        def emit(event):
            ledger.write(json.dumps({"request_id": item["request_id"], **event}) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            # Count durable events even if the process later fails in logging/IO.
            if event["event"] == "attempt_started":
                receipt["network_attempts"] += 1
            if event["event"] == "post_may_start":
                receipt["potentially_billable_posts"] += 1
        try:
            with (run / "responses.jsonl").open("x", encoding="utf-8") as out:
                for item in manifest["requests"]:
                    if producer_digests() != manifest["producer_digests"]:
                        raise ValueError("Producer changed during run")
                    if receipt["network_attempts"] + policy.max_attempts > manifest["max_network_attempts"]:
                        raise ValueError("Network attempt budget exhausted")
                    receipt["attempted_requests"] += 1
                    result = sender(item["endpoint"], item["wire_json"].encode("utf-8"), key,
                                    live=True, policy=policy, emit=emit)
                    receipt["ambiguous_posts"] += result["ambiguous_posts"]
                    receipt["duplicate_execution_possible"] |= result["duplicate_execution_possible"]
                    raw = result.pop("body")
                    row = {"request_id": item["request_id"], **result, "response": None}
                    if result["status"] == "http_response":
                        if result["http_status"] != 200:
                            row["status"] = "http_error"  # Do not retain arbitrary error bodies.
                        else:
                            try:
                                row["response"] = decode(raw)
                                if not isinstance(row["response"], dict):
                                    raise ValueError("Expected native JSON object")
                                row["status"] = "json_received"  # NOT native/semantic acceptance.
                                receipt["received_json_responses"] += 1
                            except (ValueError, UnicodeError):
                                row["response"] = None
                                row["status"] = "response_decode_error"
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    os.fsync(out.fileno())
                    if row["status"] != "json_received":
                        receipt["stop_reason"] = row["status"]
                        break
                if producer_digests() != manifest["producer_digests"]:
                    raise ValueError("Producer changed during run")
                receipt["completed"] = receipt["received_json_responses"] == receipt["planned_requests"]
        except BaseException as error:
            receipt["stop_reason"] = type(error).__name__  # Never error text/credentials.
            receipt["attempt_ledger_complete"] = False
            # After an interrupted attempt, exact inference/billing is unknown.
            receipt["ambiguous_posts"] = None
            receipt["duplicate_execution_possible"] = None
            raise
        finally:
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            with (run / "receipt.json").open("x", encoding="utf-8") as out:
                json.dump(receipt, out, indent=2)
                out.write("\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="Authorize the frozen worst-case billable attempt budget")
    args = parser.parse_args()
    print(json.dumps(execute(args.run, live=args.live), indent=2))


if __name__ == "__main__":
    main()
