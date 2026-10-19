"""Final bounded priority check; reuse frozen SDK/transport helpers, no CLI inference."""
import argparse
from pathlib import Path

import codex_envelope_ablation_v1 as prior

ROOT = prior.ROOT
RUN = ROOT / "runs/2026-10-19-final-instruction-placement-v1"
STUDY = "specmetrics.final-instruction-placement/v1"
ARMS = ("developer_rules", "user_rules")
PROTOCOL = ROOT / "final-instruction-placement-v1.md"


def sources():
    return {str(p.relative_to(ROOT)): prior.sha(p.read_bytes())
            for p in prior.local_closure(ROOT, [Path(__file__).resolve()])}


def expected():
    old = prior.verify(prior.RUN)
    template = (prior.FIXTURE / "instructions.md").read_text()
    requests = []
    for item in old["requests"]:
        role = "developer" if item["arm"] == "minimal" else "user"
        arm = "developer_rules" if role == "developer" else "user_rules"
        wire = prior.decode(item["wire_json"])
        common = wire["instructions"]
        if item["arm"] == "codex_default":
            prior.require(common.startswith(template + "\n\n"), "template prefix changed")
            common = common[len(template) + 2:]
        state = wire["input"]
        wire["instructions"] = template
        wire["input"] = [dict(role=role, content=common), dict(role="user", content=state)]
        raw = prior.encoded(wire)
        prior.require(len(raw.encode()) <= 65536, "wire bound")
        requests.append(dict(request_id=f'{item["case_id"]}-r{item["repeat"]}-{arm}',
            case_id=item["case_id"], repeat=item["repeat"], arm=arm, endpoint=prior.ENDPOINT,
            wire_json=raw, wire_sha256=prior.sha(raw.encode())))
    inputs = prior.input_digests() | {
        str(PROTOCOL.relative_to(ROOT)): prior.sha(PROTOCOL.read_bytes()),
        str((prior.RUN / "manifest.json").relative_to(ROOT)): prior.sha((prior.RUN / "manifest.json").read_bytes())}
    return dict(protocol=prior.PROTOCOL, semantic_status="unscored", study=STUDY,
        producer_digests=prior.transport_run.producer_digests(), experiment_producer_sha256=sources(),
        inputs_sha256=inputs, tasks=old["tasks"], requests=requests, retry_policy=old["retry_policy"],
        planned_requests=12, max_network_attempts=36, new_sol_calls=0, semantic_retries=0,
        authorization="User: Сделай проверки ещё, но потом глубже копать не хочу уже.",
        stopping_rule="Finish this bounded check and report; no further research or inference cohorts.",
        automatic_fact_acceptance=False, metric_effect="none")


def freeze(run):
    manifest = expected()
    run.mkdir(exist_ok=False)
    (run / "manifest.json").write_text(prior.encoded(manifest) + "\n")
    (run / "preparation-receipt.json").write_text(prior.encoded(dict(study=STUDY,
        manifest_sha256=prior.sha((run / "manifest.json").read_bytes()), hosted_requests=0,
        sdk=prior.sdk_environment())) + "\n")
    return verify(run)


def verify(run, *, live=False):
    manifest = prior.decode((run / "manifest.json").read_bytes())
    prior.require(manifest == expected(), "placement preparation changed")
    receipt = prior.decode((run / "preparation-receipt.json").read_bytes())
    prior.require(receipt["study"] == STUDY and receipt["hosted_requests"] == 0
        and receipt["manifest_sha256"] == prior.sha((run / "manifest.json").read_bytes()), "preparation receipt")
    if live:
        prior.require(receipt["sdk"] == prior.sdk_environment(), "live SDK changed")
    prior.transport_run.load(run)
    return manifest


def execute(run, *, live=False, sender=None):
    verify(run, live=live)
    try:
        return prior.transport_run.execute(run, live=live, **({"sender": sender} if sender else {}))
    finally:
        if live and (run / "receipt.json").is_file() and not (run / "result-receipt.json").exists():
            names = ("manifest.json", "preparation-receipt.json", "attempts.jsonl", "responses.jsonl", "receipt.json")
            with (run / "result-receipt.json").open("x") as stream:
                stream.write(prior.encoded(dict(study=STUDY, experiment_producer_sha256=sources(),
                    files_sha256={n: prior.sha((run / n).read_bytes()) for n in names if (run / n).is_file()})) + "\n")


def analyze(run):
    manifest = verify(run)
    seal = prior.decode((run / "result-receipt.json").read_bytes())
    names = ("manifest.json", "preparation-receipt.json", "attempts.jsonl", "responses.jsonl", "receipt.json")
    prior.require(seal["study"] == STUDY and seal["experiment_producer_sha256"] == sources()
        and seal["files_sha256"] == {n: prior.sha((run / n).read_bytes()) for n in names}, "capture binding")
    receipt = prior.decode((run / "receipt.json").read_bytes())
    prior.require(receipt["manifest_sha256"] == prior.sha((run / "manifest.json").read_bytes()), "transport binding")
    rows = [prior.decode(line) for line in (run / "responses.jsonl").read_bytes().splitlines()]
    events = [prior.decode(line) for line in (run / "attempts.jsonl").read_bytes().splitlines()]
    prior.require(len(rows) == receipt["attempted_requests"] <= 12, "response prefix")
    prior.require(sum(e["event"] == "attempt_started" for e in events) == receipt["network_attempts"] <= 36,
                  "attempt count")
    prior.require(sum(e["event"] == "post_may_start" for e in events) == receipt["potentially_billable_posts"], "POST count")
    refs = {v["case_id"]: v["labels"] for v in prior.decode(prior.REFERENCE.read_bytes())["views"] if v["arm"] == "baseline"}
    observations = []
    for item, row in zip(manifest["requests"], rows):
        prior.require(row["request_id"] == item["request_id"] and row["wire_sha256"] == item["wire_sha256"], "request binding")
        record = dict(request_id=item["request_id"], case_id=item["case_id"], arm=item["arm"],
                      repeat=item["repeat"], status=row["status"], answers=None)
        if row["status"] == "json_received":
            try:
                _, answer = prior.sdk_exchange(manifest["tasks"][item["case_id"]], row["response"])
                labels = dict(answer.answers)
                candidate = prior.NativeProposal(*(labels[k] for k in ("concern_kind", "evidence_confidence", "ownership", "tool_responsibility")))
                record.update(status="decoded", answers=labels,
                    matching_axes=sum(v == refs[item["case_id"]][k] for k, v in labels.items()),
                    consistency_violations=[code for spec, code in prior.RULES if not spec.is_satisfied_by(candidate)],
                    usage=(dict(input_tokens=answer.usage.input_tokens, output_tokens=answer.usage.output_tokens) if answer.usage else None))
            except Exception as error:
                record["status"] = type(error).__name__
        observations.append(record)
    complete = receipt["completed"] and receipt["attempt_ledger_complete"] and len(rows) == 12
    usable = complete and all(r["status"] == "decoded" for r in observations)
    summary, owners, repeatability = {}, {}, []
    for arm in ARMS:
        valid = [r for r in observations if r["arm"] == arm and r["answers"]]
        metered = [r for r in valid if r["usage"]]
        summary[arm] = dict(valid_responses=len(valid), planned_responses=6,
            matching_axes=sum(r["matching_axes"] for r in valid), planned_axis_slots=24,
            complete_reference_views=sum(r["matching_axes"] == 4 for r in valid),
            consistency_review=sum(bool(r["consistency_violations"]) for r in valid),
            reported_input_tokens=sum(r["usage"]["input_tokens"] for r in metered) if metered else None,
            reported_output_tokens=sum(r["usage"]["output_tokens"] for r in metered) if metered else None)
        owners[arm] = [r["answers"]["ownership"] for r in valid if r["case_id"] == "R01"]
        for case in prior.CASES:
            pair = [r["answers"] for r in valid if r["case_id"] == case]
            repeatability.append(dict(case_id=case, arm=arm, observed=len(pair),
                same_labels=(pair[0] == pair[1]) if len(pair) == 2 else None))
    prediction = owners == {"developer_rules": ["existing_specification"] * 2, "user_rules": ["unknown"] * 2}
    return dict(study=STUDY, status="complete_descriptive_comparison" if usable else "incomplete_not_evaluable",
        arms=summary, observations=observations, r01_ownership=owners, repeatability=repeatability,
        narrow_priority_prediction_supported=prediction if usable else None, semantic_accuracy=None,
        exact_cli_cause_established=False, automatic_fact_acceptance=False, metric_effect="none",
        new_sol_calls=0, research_status="closed_per_user_request", further_inference_authorized=False)


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
        (args.directory / "comparison.json").write_text(prior.encoded(result) + "\n")
    print(prior.encoded({k: v for k, v in result.items() if k not in {"requests", "tasks", "observations", "experiment_producer_sha256", "inputs_sha256"}}))


if __name__ == "__main__":
    main()
