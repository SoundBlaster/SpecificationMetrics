#!/usr/bin/env python3
"""Opt-in metamorphic test of JSON state key order, with exact wire receipts."""
import argparse
import http.client
import json
import os
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from question_grouping import canonical, digest, parse_response, unique_object, reject_constant

ROOT = Path(__file__).parent


def load_wire(item):
    raw = item["wire_json"].encode()
    if digest(raw) != item["wire_sha256"]:
        raise ValueError("Wire digest mismatch")
    body = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    if json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode() != raw:
        raise ValueError("Unexpected JSON formatting")
    return raw, body


def validate(plan):
    if len(plan) != 16:
        raise ValueError("Expected exactly 16 requests")
    seen, cases = set(), {}
    for item in plan:
        raw, body = load_wire(item)
        key = (item["candidate_id"], item["arm"])
        if key in seen or item["arm"] not in {"insertion", "canonical"}:
            raise ValueError("Duplicate or unknown arm")
        seen.add(key)
        if list(body) != ["model", "questions", "state"] or body["model"] != "jev-1.13.0":
            raise ValueError("Root order or model mismatch")
        if set(body["questions"]) != {"opportunity", "concern_kind"}:
            raise ValueError("Expected fixed joint questions")
        if body["state"]["candidate_id"] != item["candidate_id"] or len(canonical(body["state"])) > 24 * 1024:
            raise ValueError("Invalid bounded candidate state")
        question_wire = json.dumps(body["questions"], ensure_ascii=False, separators=(",", ":")).encode()
        if question_wire != canonical(body["questions"]):
            raise ValueError("Question key order is not fixed")
        state_wire = json.dumps(body["state"], ensure_ascii=False, separators=(",", ":")).encode()
        if item["arm"] == "canonical" and state_wire != canonical(body["state"]):
            raise ValueError("Canonical state arm is not sorted")
        case = cases.setdefault(item["candidate_id"], {})
        case[item["arm"]] = (body, raw, state_wire)
    if len(cases) != 8:
        raise ValueError("Expected eight paired cases")
    for case in cases.values():
        if set(case) != {"canonical", "insertion"}:
            raise ValueError("Incomplete pair")
        a, b = case["insertion"], case["canonical"]
        if a[0] != b[0] or len(a[1]) != len(b[1]) or a[2] == b[2]:
            raise ValueError("Pairs differ semantically, in byte length, or not at all")


def load(run):
    manifest = json.loads((run / "manifest.json").read_text())
    for name, expected in manifest["digests"].items():
        p = (ROOT / name).resolve()
        if ROOT.resolve() not in p.parents or digest(p.read_bytes()) != expected:
            raise ValueError("Input provenance mismatch")
    plan = json.loads((run / "plan.json").read_text())
    validate(plan)
    study = json.loads((ROOT / "runs/2026-10-05-intent-profile-ablation/study.json").read_text())
    originals = {c["candidate_id"]: json.loads(c["contexts"]["code_plus_architecture_profile"]["state"]) for c in study["cases"]}
    for item in plan:
        if item["arm"] == "insertion":
            _, body = load_wire(item)
            expected = json.dumps(originals[item["candidate_id"]], ensure_ascii=False, separators=(",", ":"))
            if json.dumps(body["state"], ensure_ascii=False, separators=(",", ":")) != expected:
                raise ValueError("Insertion arm differs from historical source-state order")
    return manifest, plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--live", action="store_true", help="Authorize up to sixteen potentially billable requests")
    args = p.parse_args()
    manifest, plan = load(args.run)
    if not args.live:
        print("Validated 16 exact-wire requests and 8 semantic-invariance pairs; no inference")
        return
    key = os.environ.get("COREINFRA_API_KEY")
    if not key:
        raise ValueError("Missing COREINFRA_API_KEY")
    if manifest["endpoint"] != "https://hub.coreinfra.ai/typesafe/api/v1/systemone":
        raise ValueError("Unexpected endpoint")
    if any((args.run / name).exists() for name in ["responses.jsonl", "receipt.json"]):
        raise ValueError("Refusing to repeat or overwrite live artifacts")
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    preflights, conn = [], None
    for _ in range(3):
        conn = http.client.HTTPSConnection("hub.coreinfra.ai", timeout=30, context=ssl.create_default_context())
        t = time.monotonic()
        try:
            conn.connect()  # TLS only: no HTTP request, credential or inference is sent.
            preflights.append({"error": None, "elapsed_seconds":round(time.monotonic()-t,6)})
            break
        except Exception as error:
            preflights.append({"error":type(error).__name__,"elapsed_seconds":round(time.monotonic()-t,6)})
            conn.close()
            conn = None
            print("Unauthenticated TLS preflight failed: " + type(error).__name__, flush=True)
    saved, tokens, stop = 0, 0, None if conn else "TLS preflight unavailable"
    with (args.run / "responses.jsonl").open("x") as out:
        for item in plan if conn else []:
            raw, body = load_wire(item)
            row = {key:item[key] for key in ["candidate_id","arm","wire_sha256"]}
            row.update(response=None, error=None)
            t = time.monotonic()
            try:
                conn.request("POST", "/typesafe/api/v1/systemone", body=raw, headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","Accept-Encoding":"identity","User-Agent":"specmetrics-state-key-order/1"})
                response = conn.getresponse()
                received = response.read(1024*1024+1)
                if response.status != 200:
                    row["error"] = "HTTP " + str(response.status)
                elif len(received) > 1024*1024:
                    row["error"] = "Oversized response"
                else:
                    row["response"] = parse_response(received, body["questions"])
                    row["request_id"] = response.getheader("x-request-id")
                    usage = row["response"].get("usage") or {}
                    tokens += (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
            except Exception as error:
                row["error"] = type(error).__name__
            row["elapsed_seconds"] = round(time.monotonic()-t,6)
            row["received_at"] = datetime.now(timezone.utc).isoformat()
            out.write(json.dumps(row,ensure_ascii=False)+"\n");out.flush()
            saved += 1
            labels = {axis:a["choice"] for axis,a in (row["response"] or {}).get("answers",{}).items()}
            print(f"{saved}/16 {item['candidate_id']} {item['arm']} {row['error'] or labels}",flush=True)
            if row["error"] or tokens >= manifest["max_observed_tokens"]:
                stop = row["error"] or "observed token guard"
                break
    if conn:
        conn.close()
    receipt = {"started_at":started,"finished_at":datetime.now(timezone.utc).isoformat(),"elapsed_seconds":round(time.monotonic()-clock,3),
               "planned_requests":16,"attempted_requests":saved,"completed":saved==16 and stop is None,"observed_tokens":tokens,
               "inference_retries":0,"tls_preflights":preflights,"stop_reason":stop}
    (args.run / "receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt),flush=True)


if __name__ == "__main__":
    main()
