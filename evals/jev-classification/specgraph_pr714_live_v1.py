"""One authorized, frozen PR714 Jev -> optional Luna review run; offline replay."""

import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from mellea_jev import CategoricalResult, ResponsesChoiceProvider, TypeSafeProvider

from categorical_review_bridge_v1 import bind, categorical_plan, replay_jev_capture
from categorical_review_bridge_v1 import JEV_ENDPOINT
import prepare_specgraph_pr714_v2 as source
from pr714_transport_v1 import MAX_REQUEST_BYTES, send
from retrieval_fact_adapter_v1.dependencies import local_closure
from rich_review_report_v1 import fenced
from semantic_review_routing_v1.context import RoutingContext
from structured_semantic_review_v1.preparation import ENDPOINT, encoded, load, sha

ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT / "specgraph-pr714-live-v1.md"
PREPARATION = ROOT / "runs/2026-10-19-specgraph-pr714-live-preparation-v1"
RUN = ROOT / "runs/2026-10-19-specgraph-pr714-live-v1"
STUDY = "specmetrics.specgraph-pr714-live/v1"


def check(value, message):
    if not value:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return load(path.read_bytes())


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(encoded(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def producers():
    files = local_closure(ROOT, [Path(__file__).resolve()]) + [PROTOCOL]
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(files)}


def runtime():
    return dict(python=sys.version, distributions={name: importlib.metadata.version(name) for name in
        ("mellea-jev-adapter", "openai", "httpx2", "pydantic", "specification-core")},
        provider_sha256={name: sha(Path(inspect.getsourcefile(cls)).read_bytes())
            for name, cls in (("native", TypeSafeProvider), ("responses", ResponsesChoiceProvider))})


def bound_task(case):
    packet = source.load(source.RUN / f"{case}.packet.json")
    context = RoutingContext.model_validate_json(encoded(source.context_for(packet)))
    return bind(context, state_json=encoded(packet["task"]["state"]),
                questions_json=encoded(packet["task"]["questions"]))


def expected():
    source.verify()
    requests = []
    for case, *_ in source.CASES:
        bound = bound_task(case)
        task = bound.sdk_task()
        native = dict(model=bound.context.expected_model, state=task.state,
                      questions={name: question.to_payload() for name, question in task.questions.items()})
        # A synthetic unknown result selects review preparation only. These labels
        # are not sent to either model, stored as answers, or used as references.
        dummy = CategoricalResult(answers=dict(concern_kind="unknown", evidence_confidence="insufficient",
            ownership="unknown", tool_responsibility="unknown"), requested_model="jev-1.13.0", returned_model="jev-1.13.0")
        review = categorical_plan(bound, dummy, response_sha256="f" * 64).review_request()
        for kind, endpoint, payload in (("jev", JEV_ENDPOINT, native), ("review", ENDPOINT, review)):
            wire = encoded(payload)
            check(1 <= len(wire.encode()) <= MAX_REQUEST_BYTES, "wire size exceeds protocol")
            requests.append(dict(id=f"{case}-{kind}", case=case, kind=kind, endpoint=endpoint,
                wire_json=wire, wire_sha256=sha(wire.encode()), wire_bytes=len(wire.encode())))
    return dict(study=STUDY, source_preparation_receipt_sha256=sha((source.RUN / "preparation-receipt.json").read_bytes()),
        producer_sha256=producers(), runtime=runtime(), requests=requests,
        authorization="User: Бюджет согласовываю. Ок. Four first-stage Jev batches and at most four conditional ordinary Luna reviews.",
        limits=dict(first_stage=4, conditional_reviews=4, logical_requests=8, network_attempts=24,
            potentially_billable_posts=8, attempts_per_request=3, socket_timeout_seconds=30,
            hard_request_seconds=100, dispatch_deadline_seconds=900, max_request_bytes=MAX_REQUEST_BYTES,
            max_response_bytes=1048576, review_output_tokens=1024, native_output_token_cap=None,
            monetary_limit=None, semantic_retries=0, retries_after_possible_post=0, new_sol_calls=0),
        metric_effect="none", automatic_fact_acceptance=False, semantic_accuracy=None)


def freeze(preparation=PREPARATION):
    manifest = expected()
    preparation.mkdir(exist_ok=False)
    write(preparation / "manifest.json", manifest)
    write(preparation / "preparation-receipt.json", dict(study=STUDY, hosted_requests=0,
        manifest_sha256=sha((preparation / "manifest.json").read_bytes()), producer_sha256=producers()))
    return dict(frozen=True, hosted_requests=0, planned_first_stage=4, max_conditional_reviews=4)


def verify_preparation(preparation=PREPARATION):
    wanted = expected()
    check(read(preparation / "manifest.json") == wanted, "frozen request/runtime/producers differ")
    check(read(preparation / "preparation-receipt.json") == dict(study=STUDY, hosted_requests=0,
        manifest_sha256=sha((preparation / "manifest.json").read_bytes()), producer_sha256=producers()), "preparation receipt differs")
    return wanted


def worker(directory):
    """Internal bounded child; parent owns the hard deadline and dispatch lease."""
    request = read(directory / "request.json")
    run = directory.parent
    check(directory.name == request["id"], "request directory identity differs")
    preparation = Path(read(run / "local-execution.json")["preparation_path"])
    manifest = verify_preparation(preparation)
    check(request in manifest["requests"], "unfrozen request")
    check(read(run / "manifest.json") == manifest, "run manifest differs")
    lease = read(preparation / "dispatch-reservation.json")
    check(lease == read(run / "dispatch-reservation.json")
          and lease["manifest_sha256"] == sha((run / "manifest.json").read_bytes())
          and lease["output_identity_sha256"] == sha(str(run.resolve()).encode()), "dispatch lease differs")
    key = os.environ.get("COREINFRA_API_KEY")
    check(isinstance(key, str) and key and key.isascii() and not any(c.isspace() for c in key), "key unavailable or invalid")
    check(key.encode() not in request["wire_json"].encode(), "credential in request")
    result = None
    try:
        with (directory / "attempts.jsonl").open("x", encoding="utf-8") as ledger:
            def emit(event):
                ledger.write(encoded(dict(request_sha256=request["wire_sha256"], recorded_at=now(), **event)) + "\n")
                ledger.flush()
                os.fsync(ledger.fileno())
            result = send(request["endpoint"], request["wire_json"].encode(), key, emit=emit)
        raw = result.pop("body")
        if raw is not None and key.encode() in raw:
            result.update(status="credential_reflection")
            raw = None
        write(directory / "response.json", dict(request_sha256=request["wire_sha256"],
            raw_body_base64=base64.b64encode(raw).decode() if raw is not None else None,
            raw_body_sha256=sha(raw) if raw is not None else None))
        write(directory / "transport.json", result)
    except BaseException as error:
        # Preserve durable attempt events. Do not serialize exception messages.
        if not (directory / "worker-error.json").exists():
            write(directory / "worker-error.json", dict(error_type=type(error).__name__))
        raise SystemExit(2) from None


def dispatch(directory, timeout):
    started = time.monotonic()
    process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "worker", "--run", str(directory.resolve())],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    timed_out = False
    try:
        process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
    # stdout/stderr are intentionally not published; errors are typed/redacted.
    write(directory / "execution.json", dict(child_exit_code=process.returncode, hard_timeout=timed_out,
        wall_seconds=round(time.monotonic() - started, 6), hard_limit_seconds=timeout))


def capture(directory):
    execution = read(directory / "execution.json") if (directory / "execution.json").exists() else dict(
        child_exit_code=None, hard_timeout=None, wall_seconds=None, hard_limit_seconds=None,
        diagnostic="dispatch_incomplete")
    request = read(directory / "request.json")
    events = [load(line) for line in (directory / "attempts.jsonl").read_bytes().splitlines()] if (directory / "attempts.jsonl").exists() else []
    check(all(e["request_sha256"] == request["wire_sha256"] for e in events), "attempt identity differs")
    starts = sum(e["event"] == "attempt_started" for e in events)
    posts = sum(e["event"] == "post_may_start" for e in events)
    check(starts <= 3 and posts <= 1, "per-request budget exceeded")
    receipt = read(directory / "transport.json") if (directory / "transport.json").exists() else None
    raw, http_status = None, None
    if receipt is not None:
        check(receipt["network_attempts"] == starts and receipt["potentially_billable_posts"] == posts,
              "transport counter differs")
        finished = [e for e in events if e["event"] == "attempt_finished"]
        check(len(finished) == starts and [e["attempt"] for e in finished] == list(range(1, starts+1))
              and all(not e["retry_scheduled"] or not e["post_may_have_been_sent"] for e in finished),
              "completed attempt lifecycle differs")
        http_status = receipt["http_status"]
    if execution["child_exit_code"] == 0 and not execution["hard_timeout"] and receipt is not None:
        row = read(directory / "response.json")
        check(row["request_sha256"] == request["wire_sha256"], "response binding differs")
        if row["raw_body_base64"] is not None:
            raw = base64.b64decode(row["raw_body_base64"], validate=True)
            check(sha(raw) == row["raw_body_sha256"] and len(raw) <= 1048576, "body binding differs")
    return dict(request_id=request["id"], wire_sha256=request["wire_sha256"], network_attempts=starts,
        potentially_billable_posts=posts, http_status=http_status, execution=execution, transport=receipt,
        ambiguous_posts=receipt["ambiguous_posts"] if receipt else None), raw


def first_plan(case, directory, request):
    check(read(directory / "request.json") == request, "captured request differs from frozen item")
    observed, raw = capture(directory)
    plan = replay_jev_capture(bound_task(case), raw, http_status=observed["http_status"] or 200)
    return observed, plan


def run(preparation=PREPARATION, output=RUN, *, live=False, dispatcher=dispatch):
    manifest = verify_preparation(preparation)
    if not live:
        return dict(validated=True, hosted_requests=0, inference=False)
    key = os.environ.get("COREINFRA_API_KEY")
    check(isinstance(key, str) and key and key.isascii() and not any(c.isspace() for c in key), "key unavailable or invalid")
    check(not (preparation / "dispatch-reservation.json").exists(), "preparation already spent")
    output.mkdir(mode=0o700, exist_ok=False)
    write(output / "manifest.json", manifest)
    # This machine-local path is needed only by the child, never published.
    write(output / "local-execution.json", dict(preparation_path=str(preparation.resolve())))
    lease = dict(study=STUDY, manifest_sha256=sha((preparation / "manifest.json").read_bytes()), run_id=uuid.uuid4().hex,
                 started_at_utc=now(),
                 output_identity_sha256=sha(str(output.resolve()).encode()),
                 max_logical_requests=8, max_network_attempts=24, max_possible_posts=8)
    write(preparation / "dispatch-reservation.json", lease)
    write(output / "dispatch-reservation.json", lease)
    started, attempted, stop = time.monotonic(), 0, None

    def invoke(item):
        nonlocal attempted, stop
        remaining = 900 - (time.monotonic() - started)
        if remaining <= 0:
            stop = "dispatch_deadline"
            return None
        check(attempted < 8, "logical request budget exhausted")
        directory = output / item["id"]
        directory.mkdir(mode=0o700)
        write(directory / "request.json", item)
        attempted += 1
        dispatcher(directory, min(100, remaining))
        observation, _ = capture(directory)
        if observation["http_status"] in (400, 401, 402, 403, 429):
            stop = "provider_rejected_request"
        return directory

    try:
        for case, *_ in source.CASES:
            if stop:
                break
            item = next(r for r in manifest["requests"] if r["id"] == f"{case}-jev")
            directory = invoke(item)
            if directory is None or stop:
                break
            _, plan = first_plan(case, directory, item)
            if plan.review is not None:
                review = next(r for r in manifest["requests"] if r["id"] == f"{case}-review")
                check(encoded(plan.review_request()) == review["wire_json"], "conditional review differs from frozen template")
                invoke(review)
    except BaseException as error:
        stop = type(error).__name__
        raise
    finally:
        write(output / "run-receipt.json", dict(study=STUDY, started_at_utc=lease.get("started_at_utc"),
            finished_at_utc=now(), logical_requests=attempted, dispatch_wall_seconds=round(time.monotonic()-started, 6),
            stop_reason=stop, manifest_sha256=sha((output / "manifest.json").read_bytes()),
            producer_sha256=producers(), metric_effect="none", automatic_fact_acceptance=False))
    return dict(logical_requests=attempted, stop_reason=stop)


def analyze(preparation=PREPARATION, output=RUN):
    manifest = verify_preparation(preparation)
    check(read(output / "manifest.json") == manifest, "captured manifest differs")
    check(read(output / "dispatch-reservation.json") == read(preparation / "dispatch-reservation.json"), "run lease differs")
    receipt = read(output / "run-receipt.json")
    check(receipt["producer_sha256"] == producers()
          and receipt["manifest_sha256"] == sha((output / "manifest.json").read_bytes()), "run receipt differs")
    cases, observations = [], []
    for case, *_ in source.CASES:
        primary = output / f"{case}-jev"
        if not primary.exists():
            cases.append(dict(case=case, status="analysis_incomplete", route="not_run", first_stage=None, review=None))
            continue
        item = next(r for r in manifest["requests"] if r["id"] == f"{case}-jev")
        observation, plan = first_plan(case, primary, item)
        observations.append(observation)
        original = plan.report()
        status, reviewed = original["original_route"]["status"], None
        review_dir = output / f"{case}-review"
        if plan.review is not None:
            if review_dir.exists():
                request = next(r for r in manifest["requests"] if r["id"] == f"{case}-review")
                check(read(review_dir / "request.json") == request
                      and encoded(plan.review_request()) == request["wire_json"], "captured review differs from frozen selection")
                obs, raw = capture(review_dir)
                observations.append(obs)
                reviewed = plan.inspect_review(raw, captured_request_sha256=obs["wire_sha256"],
                    execution_status="completed" if raw is not None else "transport_failed")
            else:
                reviewed = plan.inspect_review()
            status = reviewed["status"]
        else:
            check(not review_dir.exists(), "unselected review was dispatched")
        cases.append(dict(case=case, status=status, route=original["original_route"]["route"],
                          first_stage=original, review=reviewed))
    check(len(observations) == receipt["logical_requests"] <= 8, "logical request count differs")
    attempts = sum(o["network_attempts"] for o in observations)
    posts = sum(o["potentially_billable_posts"] for o in observations)
    check(attempts <= 24 and posts <= 8, "aggregate budget exceeded")
    return dict(study=STUDY, source_revision=source.prior.REVISION, cases=cases, observations=observations,
        run_receipt=receipt, logical_requests=len(observations), network_attempts=attempts, potentially_billable_posts=posts,
        selected_reviews=sum(c["route"] == "ordinary_review" for c in cases),
        semantic_accuracy=None, monetary_cost=None, automatic_fact_acceptance=False, metric_effect="none", new_sol_calls=0)


def render(report):
    lines = ["# SpecGraph PR714 · informational live route pilot", "", "Historical revision: `" + report["source_revision"] + "`.",
        "No independent reference or accuracy estimate. No accepted facts, S/U or code changes.", "",
        "| Case | Jev role / support | Route | Review role / support | Final status |", "| --- | --- | --- | --- | --- |"]
    for case in report["cases"]:
        first = case["first_stage"]
        labels = first["categorical"].get("answers", {}) if first else {}
        reviewed = case["review"]["review"] if case["review"] else None
        after = reviewed["labels"] if reviewed else {}
        lines.append(f'| {case["case"]} | {labels.get("concern_kind", "unavailable")} / {labels.get("evidence_confidence", "unavailable")} | {case["route"]} | {after.get("concern_kind", "not_run")} / {after.get("evidence_confidence", "not_run")} | {case["status"]} |')
    lines += ["", f'Logical requests: {report["logical_requests"]}; network attempts: {report["network_attempts"]}; possible POSTs: {report["potentially_billable_posts"]}.',
              "Monetary cost: unknown unless request-attributable billing is supplied. Detailed labels, native probabilities, reported usage, local timing, evidence/routing checks and receipts are in report.json.", ""]
    for case in report["cases"]:
        review = case["review"]
        if review:
            lines += [f'## {case["case"]} review', "", "Findings: " + encoded(review["findings"]),
                "", "Missing evidence: " + encoded(review["preserved_missing_evidence"]), ""]
            if review["review"]:
                lines += ["Model rationale (unverified):", "", fenced(review["review"]["rationale"]), ""]
    return "\n".join(lines)


def save_report(preparation=PREPARATION, output=RUN):
    report = analyze(preparation, output)
    write(output / "report.json", report)
    with (output / "report.md").open("x", encoding="utf-8") as stream:
        stream.write(render(report))
    # Exclude the one local execution path, not any captured provider evidence.
    files = {str(p.relative_to(output)): sha(p.read_bytes()) for p in sorted(output.rglob("*"))
             if p.is_file() and p != output / "local-execution.json"}
    write(output / "result-receipt.json", dict(study=STUDY, producer_sha256=producers(), files_sha256=files))
    return dict(logical_requests=report["logical_requests"], selected_reviews=report["selected_reviews"],
                statuses={c["case"]: c["status"] for c in report["cases"]})


def verify_result(preparation=PREPARATION, output=RUN):
    receipt = read(output / "result-receipt.json")
    check(receipt["study"] == STUDY and receipt["producer_sha256"] == producers(), "result producers differ")
    check(receipt["files_sha256"] == {str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob("*")
        if p.is_file() and p not in (output / "local-execution.json", output / "result-receipt.json")}, "result inventory differs")
    report = analyze(preparation, output)
    check(read(output / "report.json") == report and (output / "report.md").read_text() == render(report), "report replay differs")
    return dict(verified=True, hosted_requests=0, logical_requests=report["logical_requests"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "worker", "report", "verify"))
    parser.add_argument("--preparation", type=Path, default=PREPARATION)
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.action == "worker":
        check(args.run.is_dir(), "missing request directory")
        worker(args.run)
    else:
        result = (freeze(args.preparation) if args.action == "freeze" else
            run(args.preparation, args.run, live=args.live) if args.action == "run" else
            save_report(args.preparation, args.run) if args.action == "report" else verify_result(args.preparation, args.run))
        print(encoded(result))
