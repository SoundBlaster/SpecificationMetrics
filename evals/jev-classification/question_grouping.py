#!/usr/bin/env python3
"""Bounded opt-in native HTTP comparison; this is not a RustJev batch API."""
import argparse
import hashlib
import json
import math
import os
import ssl
import subprocess
import tempfile
import ipaddress
import socket
import http.client
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def validate_plan(plan):
    if len(plan) != 24:
        raise ValueError("Expected exactly 24 planned requests")
    seen, cases = set(), {}
    for item in plan:
        body = item["body"]
        axes = sorted(body["questions"])
        key = (item["candidate_id"], item["arm"], tuple(axes))
        if key in seen or digest(canonical(body)) != item["body_sha256"]:
            raise ValueError("Duplicate request or digest mismatch")
        seen.add(key)
        if axes != item["axes"] or body["model"] != "jev-1.13.0":
            raise ValueError("Question or model mismatch")
        if item["arm"] not in {"joint", "separate"} or len(axes) != (2 if item["arm"] == "joint" else 1):
            raise ValueError("Invalid arm")
        if not set(axes) <= {"opportunity", "concern_kind"} or len(canonical(body["state"])) > 24 * 1024:
            raise ValueError("Invalid bounded state")
        if body["state"]["candidate_id"] != item["candidate_id"]:
            raise ValueError("Candidate identity mismatch")
        case = cases.setdefault(item["candidate_id"], {"state": body["state"], "questions": {}, "arms": Counter()})
        if case["state"] != body["state"]:
            raise ValueError("Context differs between arms")
        for axis, question in body["questions"].items():
            if question != case["questions"].setdefault(axis, question):
                raise ValueError("Prompt or rubric differs between arms")
            case["arms"][(item["arm"], axis)] += 1
    if len(cases) != 8 or any(case["arms"] != Counter({(arm, axis): 1 for arm in ["joint", "separate"] for axis in ["opportunity", "concern_kind"]}) for case in cases.values()):
        raise ValueError("Incomplete paired plan")


def load_plan(run, manifest):
    path = Path(__file__).parent / manifest["plan_path"] if "plan_path" in manifest else run / "plan.json"
    if Path(__file__).parent.resolve() not in path.resolve().parents:
        raise ValueError("Plan path is outside the evaluation directory")
    return json.loads(path.read_text())


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate response key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Non-finite JSON constant")


def parse_response(raw, questions):
    body = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    if body.get("model") != "jev-1.13.0" or set(body.get("answers", {})) != set(questions):
        raise ValueError("Unexpected model or answer identities")
    for axis, question in questions.items():
        a = body["answers"][axis]
        probs = a.get("probabilities", {})
        if a.get("type") != "choice" or set(probs) != set(question["criteria"]) or a.get("choice") not in probs:
            raise ValueError("Invalid Choice answer")
        if any(type(v) not in {int, float} or not math.isfinite(v) or not 0 <= v <= 1 for v in probs.values()):
            raise ValueError("Invalid probability")
        confidence = a.get("confidence")
        if type(confidence) not in {int, float} or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid confidence")
        if abs(math.fsum(probs.values()) - 1) > 1e-6 or probs[a["choice"]] != max(probs.values()):
            raise ValueError("Invalid normalization or selected maximum")
    # Whitelist evidence; arbitrary provider fields and error bodies are not retained.
    return {"model": body["model"], "answers": {axis: {key: body["answers"][axis][key] for key in ["type", "choice", "probabilities", "confidence"]} for axis in questions},
            "usage": body.get("usage")}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--resolve-ip", help="Pin a current DNS address while retaining Host/SNI/certificate verification")
    p.add_argument("--transport", choices=["urllib", "curl", "persistent"], default="urllib")
    p.add_argument("--live", action="store_true", help="Authorize exactly the bounded plan; potentially billable")
    args = p.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text())
    plan = load_plan(args.run, manifest)
    for name, expected in manifest["digests"].items():
        if digest((Path(__file__).parent / name).read_bytes()) != expected:
            raise ValueError("Manifest input digest mismatch")
    validate_plan(plan)
    if manifest.get("resolve_ip") != args.resolve_ip:
        raise ValueError("Pinned address does not match frozen manifest")
    if manifest.get("transport", "urllib") != args.transport:
        raise ValueError("Transport does not match frozen manifest")
    if not args.live:
        print("Validated 24 calls on 8 paired cases; no inference")
        return
    key = os.environ.get("COREINFRA_API_KEY")
    if not key:
        raise ValueError("Missing COREINFRA_API_KEY")
    endpoint = "https://hub.coreinfra.ai/typesafe/api/v1/systemone"
    if manifest["endpoint"] != endpoint:
        raise ValueError("Unexpected endpoint")
    if any((args.run / name).exists() for name in ["responses.jsonl", "receipt.json"]):
        raise ValueError("Refusing to repeat or overwrite a hosted run")
    if args.resolve_ip:
        ipaddress.ip_address(args.resolve_ip)
        addresses = {a[4][0] for a in socket.getaddrinfo("hub.coreinfra.ai", 443, type=socket.SOCK_STREAM)}
        if args.transport != "curl" or args.resolve_ip not in addresses:
            raise ValueError("Pinned address is not a current endpoint DNS address")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    persistent = http.client.HTTPSConnection("hub.coreinfra.ai", timeout=30, context=ssl.create_default_context()) if args.transport == "persistent" else None
    started = datetime.now(timezone.utc).isoformat()
    clock, tokens, saved = time.monotonic(), 0, 0
    stop = None
    with (args.run / "responses.jsonl").open("x") as out:
        for item in plan:
            t = time.monotonic()
            row = {key: item[key] for key in ["candidate_id", "arm", "axes", "body_sha256"]}
            row.update(response=None, error=None)
            req = urllib.request.Request(endpoint, canonical(item["body"]), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept-Encoding": "identity", "User-Agent": "specmetrics-question-grouping/1"}, method="POST")
            try:
                if persistent is not None:
                    persistent.request("POST", "/typesafe/api/v1/systemone", body=canonical(item["body"]), headers={"Authorization":"Bearer " + key,"Content-Type":"application/json","Accept-Encoding":"identity","User-Agent":"specmetrics-question-grouping/1"})
                    response = persistent.getresponse()
                    raw = response.read(1024 * 1024 + 1)
                    if response.status != 200:
                        row["error"] = "HTTP " + str(response.status)
                    elif len(raw) > 1024 * 1024:
                        raise ValueError("Oversized response")
                    else:
                        row["response"] = parse_response(raw, item["body"]["questions"])
                        row["request_id"] = response.getheader("x-request-id")
                elif args.transport == "curl":
                    if any(c in key for c in "\\\"\r\n"):
                        raise ValueError("Invalid credential characters")
                    with tempfile.TemporaryDirectory(prefix="specmetrics-grouping-") as temp:
                        request_file = Path(temp) / "request.json"
                        response_file = Path(temp) / "response.json"
                        request_file.write_bytes(canonical(item["body"]))
                        request_file.chmod(0o600)
                        config = 'header = "Authorization: Bearer ' + key + '"\n'
                        route = ["--resolve", "hub.coreinfra.ai:443:" + args.resolve_ip] if args.resolve_ip else []
                        call = subprocess.run(["curl", *route, "--silent", "--show-error", "--noproxy", "*", "--proto", "=https",
                            "--connect-timeout", "10", "--max-time", "30", "--max-filesize", "1048576",
                            "--config", "-", "--header", "Content-Type: application/json", "--header", "Accept-Encoding: identity",
                            "--user-agent", "specmetrics-question-grouping/1", "--data-binary", "@" + str(request_file),
                            "--output", str(response_file), "--write-out", "%{http_code}", endpoint],
                            input=config, capture_output=True, text=True, timeout=35)
                        if call.returncode:
                            row["error"] = "curl exit " + str(call.returncode)
                        elif call.stdout != "200":
                            row["error"] = "HTTP " + call.stdout
                        else:
                            with response_file.open("rb") as f:
                                raw = f.read(1024 * 1024 + 1)
                            if len(raw) > 1024 * 1024:
                                raise ValueError("Oversized response")
                            row["response"] = parse_response(raw, item["body"]["questions"])
                else:
                    with opener.open(req, timeout=30) as response:
                        raw = response.read(1024 * 1024 + 1)
                        if len(raw) > 1024 * 1024:
                            raise ValueError("Oversized response")
                        row["response"] = parse_response(raw, item["body"]["questions"])
                        row["request_id"] = response.headers.get("x-request-id")
                usage = (row["response"] or {}).get("usage") or {}
                tokens += (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
            except urllib.error.HTTPError as error:
                row["error"] = "HTTP " + str(error.code)
                error.close()
            except Exception as error:
                row["error"] = type(error).__name__
            row["elapsed_seconds"] = round(time.monotonic() - t, 6)
            row["received_at"] = datetime.now(timezone.utc).isoformat()
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            saved += 1
            labels = {axis: a["choice"] for axis, a in (row["response"] or {}).get("answers", {}).items()}
            print(f"{saved}/24 {item['candidate_id']} {item['arm']} {row['error'] or labels}", flush=True)
            if row["error"] or tokens >= manifest["max_observed_tokens"]:
                stop = row["error"] or "observed token guard"
                break
    if persistent is not None:
        persistent.close()
    receipt = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": round(time.monotonic()-clock, 3),
               "planned_requests":24, "attempted_requests":saved, "completed":saved == 24 and stop is None,
               "automatic_retries":0, "observed_tokens":tokens, "stop_reason":stop}
    (args.run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
