"""Matched API ablation of a public Codex envelope; preparation/replay are offline."""

import argparse
import copy
import importlib.metadata
import inspect
import json
from pathlib import Path

import httpx2
from mellea_jev import CategoricalTask, ChoiceQuestion, ResponsesChoiceProvider

import coreinfra_retry_run as transport_run
from coreinfra_retry_run import decode, sha
from coreinfra_transport import PROTOCOL, RetryPolicy
from retrieval_fact_adapter_v1 import RULES
from retrieval_fact_adapter_v1.context import NativeProposal
from retrieval_fact_adapter_v1.dependencies import local_closure


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "runs/2026-10-18-ordinary-luna-preparation-v1/manifest.json"
REFERENCE = ROOT / "runs/2026-10-18-sol61-medium-repeatability-v1/top-line.json"
FIXTURE = ROOT / "fixtures/codex-envelope-0.156.1"
RUN = ROOT / "runs/2026-10-19-codex-envelope-ablation-v1"
STUDY = "specmetrics.codex-envelope-ablation/v1"
ENDPOINT = "https://hub.coreinfra.ai/openai/api/v1/responses"
MODEL = "gpt-6-luna"
CASES = ("R01", "R02", "R03")
ARMS = ("minimal", "codex_default")
SETTINGS = dict(model=MODEL, reasoning_effort="medium", max_output_tokens=1024,
                timeout=30.0, max_response_bytes=1048576)
OFFLINE_KEY = "offline-fixture-not-a-credential"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def require(value, message):
    if not value:
        raise ValueError(message)


def task_from(value):
    return CategoricalTask(state=value["state"], questions={name: ChoiceQuestion(**question)
                           for name, question in value["questions"].items()})


def sdk_environment():
    return dict(distributions={name: importlib.metadata.version(name)
                for name in ("mellea-jev-adapter", "openai", "httpx2", "pydantic")},
                responses_provider_sha256=sha(Path(inspect.getsourcefile(ResponsesChoiceProvider)).read_bytes()))


def sdk_exchange(task, body=None):
    """Public SDK render/decode over a mock transport, never the live API.

    The SDK replay wire is the minimal wire. It is not evidence of the actual
    treatment request: actual live bytes are separately frozen in the manifest.
    """
    if body is None:
        answers = {name: "insufficient" if name == "evidence_confidence" else "unknown"
                   for name in task["questions"]}
        body = dict(status="completed", model=MODEL, output=[dict(type="message", role="assistant",
                    status="completed", content=[dict(type="output_text", text=encoded(dict(answers=answers)))])])
    calls = []

    def handle(request):
        require(str(request.url) == ENDPOINT and request.method == "POST", "unexpected SDK operation")
        calls.append(request.content)
        return httpx2.Response(200, content=encoded(body).encode(), headers={"content-type": "application/json"})

    with ResponsesChoiceProvider(api_key=OFFLINE_KEY, endpoint_url=ENDPOINT,
            transport=httpx2.MockTransport(handle), **SETTINGS) as client:
        result = client.classify(task_from(task))
    require(len(calls) == 1, "SDK replay repeated")
    require(result.requested_model == MODEL and result.returned_model == MODEL, "response model differs")
    return decode(calls[0]), result


def input_paths():
    return [SOURCE, SOURCE.with_name("preparation-receipt.json"), REFERENCE,
            REFERENCE.with_name("receipt.json"), FIXTURE / "instructions.md",
            FIXTURE / "LICENSE", FIXTURE / "NOTICE", FIXTURE / "provenance.json",
            ROOT / "requirements-evaluation.lock", ROOT / "codex-envelope-ablation-v1.md"]


def input_digests():
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in input_paths()}


def producer_digests():
    return {str(p.relative_to(ROOT)): sha(p.read_bytes())
            for p in local_closure(ROOT, [Path(__file__).resolve()])}


def expected():
    source = decode(SOURCE.read_bytes())
    require(decode(SOURCE.with_name("preparation-receipt.json").read_bytes())["manifest_sha256"]
            == sha(SOURCE.read_bytes()), "historical source receipt")
    require(source["sol_top_line_sha256"] == sha(REFERENCE.read_bytes())
            and source["sol_receipt_sha256"] == sha(REFERENCE.with_name("receipt.json").read_bytes()), "reference binding")
    template = (FIXTURE / "instructions.md").read_text()
    provenance = decode((FIXTURE / "provenance.json").read_bytes())
    require(sha(template.encode()) == provenance["files"]["instructions.md"]["sha256"], "template provenance")
    tasks, base = {}, {}
    for case in CASES:
        row = next(r for r in source["requests"] if r["case_id"] == case and r["arm"] == "baseline")
        tasks[case] = row["task"]
        base[case], _ = sdk_exchange(row["task"])
        old = decode(row["request_json"])
        old["reasoning"] = {"effort": "medium"}
        require(base[case] == old, "SDK changed more than the approved effort setting")
    requests = []
    # Each case has AB and BA order, and the second repeat reverses case order.
    for repeat in (1, 2):
        for case in CASES if repeat == 1 else reversed(CASES):
            order = ARMS if (CASES.index(case) + repeat) % 2 else tuple(reversed(ARMS))
            for arm in order:
                wire = copy.deepcopy(base[case])
                if arm == "codex_default":
                    wire["instructions"] = template + "\n\n" + wire["instructions"]
                raw = encoded(wire)
                require(len(raw.encode()) <= 65536, "request exceeds transport bound")
                requests.append(dict(request_id=f"{case}-r{repeat}-{arm}", case_id=case, arm=arm,
                    repeat=repeat, endpoint=ENDPOINT, wire_json=raw, wire_sha256=sha(raw.encode())))
    return dict(protocol=PROTOCOL, semantic_status="unscored", study=STUDY,
        producer_digests=transport_run.producer_digests(), experiment_producer_sha256=producer_digests(),
        inputs_sha256=input_digests(), tasks=tasks, requests=requests,
        retry_policy=decode(encoded(RetryPolicy().receipt())), planned_requests=12, max_network_attempts=36,
        semantic_retries=0, new_sol_calls=0, automatic_fact_acceptance=False, metric_effect="none",
        authorization="User: Ок, делай; controlled envelope ablation after reviewed proposal.",
        hypothesis="R01 ownership is existing_specification in both minimal repeats and unknown in both envelope repeats.",
        scope="Screening of the public default template under one API; not exact CLI reconstruction or semantic accuracy.")


def freeze(run):
    manifest = expected()
    # The transport expects only RetryPolicy constructor fields, not its protocol label.
    manifest["retry_policy"].pop("protocol")
    run.mkdir(exist_ok=False)
    (run / "manifest.json").write_text(encoded(manifest) + "\n")
    (run / "preparation-receipt.json").write_text(encoded(dict(study=STUDY, hosted_requests=0,
        manifest_sha256=sha((run / "manifest.json").read_bytes()), sdk=sdk_environment())) + "\n")
    return verify(run)


def verify(run, *, for_live=False):
    manifest = decode((run / "manifest.json").read_bytes())
    wanted = expected()
    wanted["retry_policy"].pop("protocol")
    require(manifest == wanted, "frozen experiment differs")
    preparation = decode((run / "preparation-receipt.json").read_bytes())
    require(preparation["manifest_sha256"] == sha((run / "manifest.json").read_bytes())
            and preparation["hosted_requests"] == 0 and preparation["study"] == STUDY, "preparation binding")
    if for_live:
        require(preparation["sdk"] == sdk_environment(), "live SDK changed")
    transport_run.load(run)
    return manifest


def execute(run, *, live=False, sender=None):
    verify(run, for_live=live)
    try:
        return transport_run.execute(run, live=live, **({"sender": sender} if sender else {}))
    finally:
        if live and (run / "receipt.json").exists() and not (run / "result-receipt.json").exists():
            names = ("manifest.json", "preparation-receipt.json", "attempts.jsonl", "responses.jsonl", "receipt.json")
            with (run / "result-receipt.json").open("x") as stream:
                stream.write(encoded(dict(study=STUDY, capture_sdk=sdk_environment(),
                    experiment_producer_sha256=producer_digests(),
                    files_sha256={n: sha((run / n).read_bytes()) for n in names if (run / n).is_file()})) + "\n")


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
    require(len(rows) <= 12 and len(rows) == receipt["attempted_requests"], "response prefix count")
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
    return dict(study=STUDY, status="complete_descriptive_comparison" if usable else "incomplete_not_evaluable",
        arms=summary, observations=decoded, r01_ownership=ownership, repeatability=repeatability,
        hypothesis_status=hypothesis_status, narrow_hypothesis_supported=prediction if usable else None,
        semantic_accuracy=None, exact_cli_cause_established=False, automatic_fact_acceptance=False,
        metric_effect="none", new_sol_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify", "run", "analyze"))
    parser.add_argument("--directory", type=Path, default=RUN)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        result = freeze(args.directory)
    elif args.action == "verify":
        result = verify(args.directory)
    elif args.action == "run":
        result = execute(args.directory, live=args.live)
    else:
        result = analyze(args.directory)
        path = args.directory / "comparison.json"
        path.write_text(encoded(result) + "\n")
    print(encoded({k: v for k, v in result.items() if k not in {"requests", "tasks", "observations"}}))


if __name__ == "__main__":
    main()
