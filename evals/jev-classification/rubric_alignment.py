#!/usr/bin/env python3
"""Frozen paired rubric comparison; hosted inference requires --live."""
import argparse
import http.client
import json
import os
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from question_grouping import canonical, digest, parse_response
from state_key_order import load_wire

ROOT = Path(__file__).parent
ENDPOINT = "https://hub.coreinfra.ai/typesafe/api/v1/systemone"


def load(run):
    manifest = json.loads((run / "manifest.json").read_text())
    for name, expected in manifest["digests"].items():
        p = (ROOT / name).resolve()
        if ROOT.resolve() not in p.parents or digest(p.read_bytes()) != expected:
            raise ValueError("Frozen input digest mismatch")
    if manifest["planned_requests"] != 32 or manifest["endpoint"] != ENDPOINT:
        raise ValueError("Unexpected request budget or endpoint")
    plan = json.loads((run / "plan.json").read_text())
    rubric = json.loads((run / "rubric.json").read_text())
    packet = json.loads((run / "reference-packet.json").read_text())
    mapping = json.loads((run / "reference-mapping.json").read_text())
    old = json.loads((ROOT / "runs/2026-10-09-repeat-controls/round-1/plan.json").read_text())
    baseline = {p["candidate_id"]:load_wire(p)[1] for p in old if p["arm"] == "canonical"}
    if len(plan) != 32 or len(baseline) != 8:
        raise ValueError("Expected 32 paired requests on eight cases")
    seen = set()
    for item in plan:
        raw, body = load_wire(item)
        cid, arm, repeat = item["candidate_id"], item["arm"], item["repeat"]
        key = (cid, arm, repeat)
        if key in seen or cid not in baseline or arm not in {"baseline","aligned"} or repeat not in {1,2}:
            raise ValueError("Duplicate or unplanned request")
        seen.add(key)
        expected = dict(baseline[cid])
        if arm == "aligned":
            expected["questions"] = rubric["questions"]
        if body != expected or raw != canonical(body):
            raise ValueError("Only rubric wording may change; canonical wire required")
    if seen != {(cid,arm,repeat) for cid in baseline for arm in ["baseline","aligned"] for repeat in [1,2]}:
        raise ValueError("Incomplete paired plan")
    if len(mapping) != 8 or len({m["case_id"] for m in mapping}) != 8 or {m["candidate_id"] for m in mapping} != set(baseline):
        raise ValueError("Invalid reference mapping")
    by_case = {c["case_id"]:c for c in packet["cases"]}
    if len(packet["cases"]) != 8 or set(by_case) != {m["case_id"] for m in mapping} or packet["questions"] != rubric["questions"]:
        raise ValueError("Reference task differs from Jev task")
    for m in mapping:
        if by_case[m["case_id"]]["state"] != baseline[m["candidate_id"]]["state"]:
            raise ValueError("Reference context differs from Jev context")
    return manifest, plan


def execute(run, manifest, plan):
    if any((run/name).exists() for name in ["responses.jsonl","receipt.json"]):
        raise ValueError("Refusing to repeat or overwrite inference artifacts")
    key = os.environ.get("COREINFRA_API_KEY")
    if not key:
        raise ValueError("Missing COREINFRA_API_KEY")
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    preflights, conn = [], None
    for _ in range(3):
        conn = http.client.HTTPSConnection("hub.coreinfra.ai",timeout=30,context=ssl.create_default_context())
        t = time.monotonic()
        try:
            conn.connect()  # No HTTP, credential or inference in the preflight.
            preflights.append({"error":None,"elapsed_seconds":round(time.monotonic()-t,6)})
            break
        except Exception as error:
            preflights.append({"error":type(error).__name__,"elapsed_seconds":round(time.monotonic()-t,6)})
            conn.close()
            conn = None
    saved, tokens, stop = 0, 0, None if conn else "TLS preflight unavailable"
    with (run / "responses.jsonl").open("x") as out:
        for item in plan if conn else []:
            raw, body = load_wire(item)
            row = {k:item[k] for k in ["candidate_id","arm","repeat","wire_sha256"]}
            row.update(response=None,error=None)
            t = time.monotonic()
            try:
                conn.request("POST","/typesafe/api/v1/systemone",body=raw,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","Accept-Encoding":"identity","User-Agent":"specmetrics-rubric-alignment/1"})
                response = conn.getresponse()
                received = response.read(1024*1024+1)
                if response.status != 200:
                    row["error"] = "HTTP " + str(response.status)
                elif len(received) > 1024*1024:
                    row["error"] = "Oversized response"
                else:
                    row["response"] = parse_response(received,body["questions"])
                    usage = row["response"].get("usage") or {}
                    tokens += sum(usage.get(k,0) for k in ["input_tokens","output_tokens"])
            except Exception as error:
                row["error"] = type(error).__name__
            row["elapsed_seconds"] = round(time.monotonic()-t,6)
            row["received_at"] = datetime.now(timezone.utc).isoformat()
            out.write(json.dumps(row,ensure_ascii=False)+"\n")
            out.flush()
            saved += 1
            labels = {axis:a["choice"] for axis,a in (row["response"] or {}).get("answers",{}).items()}
            print(f"{saved}/32 {item['arm']} repeat={item['repeat']} {row['error'] or labels}",flush=True)
            if row["error"] or tokens >= manifest["max_observed_tokens"]:
                stop = row["error"] or "observed token guard"
                break
    if conn:
        conn.close()
    receipt = {"started_at":started,"finished_at":datetime.now(timezone.utc).isoformat(),"elapsed_seconds":round(time.monotonic()-clock,3),"planned_requests":32,"attempted_requests":saved,"completed":saved==32 and stop is None,"observed_tokens":tokens,"inference_retries":0,"tls_preflights":preflights,"stop_reason":stop}
    (run / "receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt),flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--live",action="store_true",help="Authorize at most32 potentially billable requests")
    args = p.parse_args()
    manifest, plan = load(args.run)
    if not args.live:
        print("Validated32 requests: fixed contexts, matched reference rubric; no inference")
        return
    for name, expected in manifest["producer_implementation_digests"].items():
        if digest((ROOT/name).read_bytes()) != expected:
            raise ValueError("Producer implementation differs from frozen protocol")
    execute(args.run,manifest,plan)


if __name__ == "__main__":
    main()
