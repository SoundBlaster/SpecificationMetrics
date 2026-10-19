"""Verify the frozen qualification preparation without invoking Codex or a provider."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "evals/jev-classification/runs/2026-10-19-codex-one-packet-preparation-v1"
RUNS = ROOT / "evals/jev-classification/runs"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(binary, bundle=BUNDLE):
    plan = load(bundle / "plan.json")
    require(plan["contract"] == "specmetrics.codex-one-packet-qualification-plan/v1", "plan contract")
    for path, digest in plan["historical_inputs_sha256"].items():
        require(sha(ROOT / path) == digest, f"historical binding changed: {path}")
    for name, digest in plan["local_files_sha256"].items():
        require(sha(bundle / name) == digest, f"local binding changed: {name}")
    require(set(plan["local_files_sha256"]) == {
        "packet.json", "source_file.py.txt", "backend-config.template.toml", "prepared.template.json"
    }, "incomplete local inventory")
    historical = RUNS / "2026-10-18-ordinary-luna-preparation-v1"
    manifest = load(historical / "manifest.json")
    receipt = load(historical / "preparation-receipt.json")
    require(receipt["manifest_sha256"] == sha(historical / "manifest.json"), "historical receipt")
    rows = [row for row in manifest["requests"] if row["case_id"] == "R01" and row["arm"] == "baseline"]
    require(len(rows) == 1, "ambiguous historical case")
    require(plan["case_id"] == "R01" and plan["arm"] == "baseline", "wrong case")
    require(plan["source_request_id"] == rows[0]["request_id"], "wrong request")
    packet = load(bundle / "packet.json")
    require(packet["task"] == rows[0]["task"], "task changed or prior answers added")
    brief = RUNS / "2026-10-18-paired-blind-reference-v1/annotation-brief.txt"
    guidance = brief.read_text(encoding="utf-8").split("\n\n")[1]
    require(packet["semantic_instructions"] == guidance, "semantic guidance changed")
    rubric = load(RUNS / "2026-10-18-paired-blind-reference-v1/annotation-rubric.json")
    require(packet["rubric_version"] == rubric["output_contract"], "rubric version")
    require(set(packet["task"]["questions"]) == set(rubric["questions"]), "question set")
    for axis, question in packet["task"]["questions"].items():
        require(question["criteria"] == rubric["questions"][axis]["criteria"], f"criteria: {axis}")
        require(guidance in question["instructions"], f"unaligned instruction: {axis}")
    source = packet["task"]["state"]["target"]["source"]
    require(plan["source"] == source and packet["source_revision"] == source["revision"], "source provenance")
    require(sha(bundle / "source_file.py.txt") == source["file_sha256"].removeprefix("sha256:"), "full source")
    lines = (bundle / "source_file.py.txt").read_text(encoding="utf-8").splitlines(keepends=True)
    excerpt = "".join(lines[source["start_line"] - 1:source["end_line"]])
    require(excerpt == source["code"], "source span")
    require(hashlib.sha256(excerpt.encode()).hexdigest() == source["excerpt_sha256"].removeprefix("sha256:"), "excerpt digest")
    reference = RUNS / "2026-10-18-sol61-medium-repeatability-v1"
    require(manifest["sol_top_line_sha256"] == sha(reference / "top-line.json"), "Sol comparator")
    require(manifest["sol_receipt_sha256"] == sha(reference / "receipt.json"), "Sol receipt")
    require(plan["authorization"] == {
        "inference_authorized": False, "preparation_inference_processes": 0, "preparation_hosted_requests": 0
    }, "preparation cannot authorize inference")
    require(plan["budget"] == {
        "planned_inference_processes": 1, "questions": 4, "adapter_retries": 0,
        "semantic_retries": 0, "new_sol_calls": 0, "timeout_seconds": 120,
        "max_output_bytes": 1048576, "max_output_tokens": None,
        "provider_http_requests": None, "monetary_cost_limit": None
    }, "budget changed")
    prepared = load(bundle / "prepared.template.json")
    require(prepared["config"]["model"] == "gpt-6-luna", "model changed")
    require(prepared["config"]["reasoning_effort"] == "medium", "effort changed")
    require(prepared["config"]["timeout_seconds"] == plan["budget"]["timeout_seconds"], "timeout mismatch")
    require(prepared["config"]["max_output_bytes"] == plan["budget"]["max_output_bytes"], "capture mismatch")
    # Only the offline repository preparer is called. Its template executable and
    # authentication paths deliberately need not exist; there is no live branch.
    with tempfile.TemporaryDirectory(prefix="codex-packet-verify-") as temporary:
        output = Path(temporary) / "prepared.json"
        subprocess.run([
            str(Path(binary).resolve()), "prepare-classification", "--packet", str(bundle / "packet.json"),
            "--config", str(bundle / "backend-config.template.toml"), "--output", str(output)
        ], check=True, timeout=30, capture_output=True)
        require(load(output) == prepared, "prepared prompt/schema/argv drift; review a new preparation version")
    return {"status": "verified_offline", "case": "R01/baseline", "hosted_requests": 0, "new_sol_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path, help="Built specification-metrics executable")
    args = parser.parse_args()
    print(json.dumps(verify(args.binary), sort_keys=True))
