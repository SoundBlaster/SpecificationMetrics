"""Read-only replay of one captured Codex observation; no inference path."""

import json
from pathlib import Path

from verify_codex_one_packet_v1 import ROOT, RUNS, load, require, sha


BUNDLE = RUNS / "2026-10-19-codex-one-packet-live-v1"


def verify(bundle=BUNDLE):
    receipt = load(bundle / "receipt.json")
    require(receipt["contract"] == "specmetrics.codex-one-packet-live-receipt/v1", "receipt contract")
    expected = {
        "authorization.json", "authorized-prepared.json", "backend.toml", "prepared.json", "argv.json", "runtime.json",
        "request.stdin", "response.schema.json", "events.jsonl", "stderr.txt", "answer.json",
        "report.json", "comparison.json"
    }
    require(set(receipt["files_sha256"]) == expected, "capture inventory")
    for name, digest in receipt["files_sha256"].items():
        require(sha(bundle / name) == digest, f"capture hash changed: {name}")
    for path, digest in receipt["historical_inputs_sha256"].items():
        require(sha(ROOT / path) == digest, f"reference hash changed: {path}")
    require(receipt["inference_process_invocations"] == 1 and receipt["adapter_retries"] == 0
            and receipt["semantic_retries"] == 0 and receipt["new_sol_calls"] == 0, "receipt budget")
    require(receipt["credential_contents_in_artifacts"] is False
            and receipt["auth_symlink_removed_after_run"] is True, "credential handling record")
    auth = load(bundle / "authorization.json")
    require(auth["preparation_commit"] == receipt["producer_commit"], "producer commit")
    require(auth["prepared_sha256"] == sha(bundle / "authorized-prepared.json"), "authorization preparation")
    require(auth["config_sha256"] == sha(bundle / "backend.toml"), "authorization configuration")
    frozen = RUNS / "2026-10-19-codex-one-packet-preparation-v1"
    require(auth["packet_sha256"] == sha(frozen / "packet.json"), "authorization packet")
    require(auth["planned_inference_processes"] == 1 and auth["adapter_retries"] == 0
            and auth["semantic_retries"] == 0 and auth["new_sol_calls"] == 0, "authorization budget")
    prepared = load(bundle / "prepared.json")
    require(prepared == load(bundle / "authorized-prepared.json"), "runtime preparation changed")
    template = load(frozen / "prepared.template.json")
    for key in ["packet", "prompt", "response_schema", "arguments"]:
        require(prepared[key] == template[key], f"frozen preparation differs: {key}")
    for key, value in template["config"].items():
        if key not in {"executable", "authentication_home"}:
            require(prepared["config"][key] == value, f"unapproved setting: {key}")
    require((bundle / "request.stdin").read_text() == prepared["prompt"], "stdin binding")
    require(load(bundle / "response.schema.json") == prepared["response_schema"], "schema binding")
    require(load(bundle / "argv.json") == prepared["arguments"], "argv binding")
    report = load(bundle / "report.json")
    for key in ["packet_digest", "config_digest", "prompt_digest"]:
        require(report[key] == prepared[key], f"report binding: {key}")
    require(report["status"] == "proposal" and report["diagnostic"] is None, "transport result")
    require(report["inference_process_invocations"] == 1
            and report["semantic_validation_status"] == "not_run"
            and report["metric_effect"] == "none", "result authority")
    answers = load(bundle / "answer.json")["answers"]
    require(report["answers"] == answers, "raw answer binding")
    require(set(answers) == set(prepared["packet"]["task"]["questions"]), "four answers required")
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
    # The observed capture contains no reasoning/tool items. This verifies this
    # frozen observation, not a replacement for the adapter's general stream FSM.
    require([event["type"] for event in events] == [
        "thread.started", "turn.started", "item.completed", "turn.completed"
    ], "observed lifecycle changed")
    require(events[2]["item"]["type"] == "agent_message", "observed non-message activity")
    require(json.loads(events[2]["item"]["text"]) == {"answers": answers}, "event answer binding")
    require(events[3]["usage"] == report["usage"], "usage binding")
    require((bundle / "stderr.txt").read_bytes() == b"", "observed stderr changed")
    reference = load(RUNS / "2026-10-18-sol61-medium-repeatability-v1/top-line.json")
    sol = next(v for v in reference["views"] if v["case_id"] == "R01" and v["arm"] == "baseline")
    previous = RUNS / "2026-10-18-ordinary-luna-live-v1/responses.jsonl"
    api = next(v for v in map(json.loads, previous.read_text().splitlines())
               if v.get("case_id") == "R01" and v.get("arm") == "baseline")
    comparison = load(bundle / "comparison.json")
    expected_axes = [{"axis": axis, "codex_label": label, "sol_label": sol["labels"][axis],
                      "historical_api_label": api["result"]["answers"][axis],
                      "agrees_with_sol": label == sol["labels"][axis]}
                     for axis, label in sorted(answers.items())]
    require(comparison["axes"] == expected_axes, "derived comparison changed")
    require(comparison["agreement_with_sol"] == {
        "matching_axes": 3, "total_axes": 4, "complete_view_agreement": False
    }, "disagreement must remain visible")
    require(answers["ownership"] == "unknown" and sol["labels"]["ownership"] == "existing_specification",
            "observed ownership disagreement changed")
    require(comparison["semantic_accuracy_estimate"] is None and comparison["automatic_fact_acceptance"] is False
            and comparison["metric_effect"] == "none", "comparison authority")
    require(comparison["codex"]["usage"] == report["usage"]
            and comparison["codex"]["elapsed_ms"] == report["elapsed_ms"], "Codex observation changed")
    require(comparison["historical_api"]["usage"] == api["result"]["usage"]
            and comparison["historical_api"]["elapsed_seconds"] == api["elapsed_seconds"], "API observation changed")
    for key in ["returned_model", "native_probabilities", "monetary_cost", "hosted_request_count"]:
        require(report[key] is None, f"unreported metadata fabricated: {key}")
    return {"status": "verified_offline", "new_inference_processes": 0,
            "matching_axes": 3, "complete_view_agreement": False}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
