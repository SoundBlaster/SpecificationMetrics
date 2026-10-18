"""One frozen, opt-in rich Luna review with a durable dispatch lease and report."""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform

from coreinfra_transport import RetryPolicy, post
from replay_semantic_review_routing_v1 import RECEIPT_SHA256, read_pinned_run, replay
from retrieval_fact_adapter_v1.dependencies import local_closure
from rich_review_report_v1 import render
from semantic_review_routing_v1.context import RoutingContext
from structured_semantic_review_v1 import inspect
from structured_semantic_review_v1.preparation import ENDPOINT, MODEL, encoded, load, prepare, request_body, sha

ROOT = Path(__file__).resolve().parent
STUDY = 'specmetrics.rich-review-live-pilot/v1'
RUN_ID = '2026-10-18-structured-luna-review-live-v1'
PREPARATION = ROOT / 'runs/2026-10-18-structured-luna-review-preparation-v1'
RUN = ROOT / 'runs' / RUN_ID
POLICY = RetryPolicy(max_attempts=1)
PROTOCOL = ROOT / 'rich-review-live-pilot-v1.md'


def now():
    return datetime.now(timezone.utc).isoformat()


def check(value, message):
    if not value:
        raise ValueError(message)


def write(path, value):
    with path.open('x', encoding='utf-8') as output:
        output.write(encoded(value) + '\n')
        output.flush()
        os.fsync(output.fileno())


def producers():
    files = local_closure(ROOT, [Path(__file__).resolve()]) + [PROTOCOL]
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(files)}


def selected():
    rows = [c for c in replay()['cases'] if c['provider'] == 'jev-coreinfra' and c['route']['route'] == 'ordinary_review']
    check([(c['case_id'], c['arm']) for c in rows] == [('R04', 'baseline')], 'selected cohort differs')
    row = rows[0]
    result = row['route']
    context = RoutingContext.model_validate_json(encoded(dict(expected=result['binding'],
        expected_provider=result['expected_provider'], expected_model=result['expected_model'],
        assessment=result['original_assessment'])))
    requests, _ = read_pinned_run()
    source = requests[row['request_id']]
    wire = load(source['wire_json'])
    prepared = prepare(context, state_json=wire['state'], questions_json=encoded(wire['questions']))
    return row, source, prepared


def expected():
    row, source, prepared = selected()
    wire = encoded(request_body(prepared))
    check(1 <= len(wire.encode()) <= 65536, 'review wire exceeds fixed transport bound')
    return dict(study=STUDY, run_id=RUN_ID, endpoint=ENDPOINT, model=MODEL,
        task_sha256=prepared.task_sha256(), decision_binding_sha256=prepared.original.expected.fingerprint(),
        source_request_id=row['request_id'], source_request_sha256=source['wire_sha256'],
        native_result_receipt_sha256=RECEIPT_SHA256, original_route=row['route'],
        request_json=wire, request_sha256=sha(wire.encode()), request_bytes=len(wire.encode()),
        producer_sha256=producers(), retry_policy=POLICY.receipt(),
        planned_requests=1, max_network_attempts=1, max_potentially_billable_posts=1,
        automatic_retries=0, max_output_tokens=1024, socket_timeout_seconds=30,
        hard_end_to_end_deadline=False, max_response_bytes=1048576,
        authorization='User: Ок, делай отчет и живой review. One selected view; no retry, context expansion or extra model call.',
        metric_effect='none', automatic_fact_acceptance=False, new_sol_calls=0,
        rationale='Review the sole known-role/insufficient-support conflict selected by the frozen Jev routing cohort.')


def lease(manifest):
    return dict(study=STUDY, run_id=RUN_ID, manifest_sha256=sha((encoded(manifest) + '\n').encode()),
                request_sha256=manifest['request_sha256'], reserved_logical_reviews=1)


def freeze(output):
    manifest = expected()
    output.mkdir(exist_ok=False)
    write(output / 'manifest.json', manifest)
    write(output / 'preparation-receipt.json', dict(study=STUDY,
        manifest_sha256=sha((output / 'manifest.json').read_bytes()), producer_sha256=producers(), hosted_requests=0))
    return verify_preparation(output)


def verify_preparation(preparation):
    manifest = expected()
    names = {p.name for p in preparation.iterdir()}
    check(names in ({'manifest.json', 'preparation-receipt.json'},
                   {'manifest.json', 'preparation-receipt.json', 'dispatch-reservation.json'}), 'preparation inventory differs')
    check((preparation / 'manifest.json').read_text() == encoded(manifest) + '\n', 'frozen request/producers differ')
    check(load((preparation / 'preparation-receipt.json').read_bytes()) == dict(study=STUDY,
        manifest_sha256=sha((preparation / 'manifest.json').read_bytes()), producer_sha256=producers(), hosted_requests=0),
        'preparation receipt differs')
    if 'dispatch-reservation.json' in names:
        check(load((preparation / 'dispatch-reservation.json').read_bytes()) == lease(manifest), 'dispatch lease differs')
    return manifest


def stage(preparation, run):
    manifest = verify_preparation(preparation)
    check(not (preparation / 'dispatch-reservation.json').exists(), 'preparation is already dispatched')
    run.mkdir(exist_ok=False)
    write(run / 'manifest.json', manifest)
    write(run / 'preparation-binding.json', dict(study=STUDY,
        preparation_receipt_sha256=sha((preparation / 'preparation-receipt.json').read_bytes()),
        logical_review_limit=1, network_attempt_limit=1))
    return dict(staged=True, inference=False, planned_requests=1)


def check_run(preparation, run):
    manifest = verify_preparation(preparation)
    check((run / 'manifest.json').read_bytes() == (preparation / 'manifest.json').read_bytes(), 'run manifest differs')
    check(load((run / 'preparation-binding.json').read_bytes()) == dict(study=STUDY,
        preparation_receipt_sha256=sha((preparation / 'preparation-receipt.json').read_bytes()),
        logical_review_limit=1, network_attempt_limit=1), 'run preparation binding differs')
    return manifest


def execute(preparation, run, *, live=False, sender=post):
    manifest = check_run(preparation, run)
    if not live:
        return dict(validated=True, inference=False, planned_requests=1)
    check({p.name for p in run.iterdir()} == {'manifest.json', 'preparation-binding.json'}, 'refuse to repeat a run')
    key = os.environ.get('COREINFRA_API_KEY')
    check(isinstance(key, str) and key and key.isascii() and not any(c.isspace() for c in key), 'CoreInfra key unavailable or invalid')
    wire = manifest['request_json'].encode()
    check(key.encode() not in wire, 'credential found in frozen payload')
    # Exclusive lease prevents another run directory from spending this preparation again.
    write(preparation / 'dispatch-reservation.json', lease(manifest))
    receipt = dict(study=STUDY, manifest_sha256=sha((run / 'manifest.json').read_bytes()),
        dispatch_reservation_sha256=sha((preparation / 'dispatch-reservation.json').read_bytes()),
        producer_sha256=producers(), started_at=now(), finished_at=None,
        attempted_requests=1, network_attempts=0, potentially_billable_posts=0, ambiguous_posts=0,
        duplicate_execution_possible=False, attempt_ledger_complete=True,
        http_body_received=False, http_elapsed_seconds=None, stop_reason=None,
        execution_runtime=dict(python=platform.python_version(),
            distributions={n: importlib.metadata.version(n) for n in ('specification-core', 'pydantic', 'pydantic-core')}))
    row = dict(request_sha256=manifest['request_sha256'], status='not_run', http_status=None,
               raw_body_base64=None, raw_body_sha256=None)
    try:
        with (run / 'attempts.jsonl').open('x', encoding='utf-8') as ledger:
            def emit(event):
                ledger.write(encoded(event) + '\n')
                ledger.flush()
                os.fsync(ledger.fileno())
                if event['event'] == 'attempt_started':
                    receipt['network_attempts'] += 1
                if event['event'] == 'post_may_start':
                    receipt['potentially_billable_posts'] += 1

            check(producers() == manifest['producer_sha256'], 'producer changed before dispatch')
            result = sender(ENDPOINT, wire, key, live=True, policy=POLICY, emit=emit)
            check(producers() == manifest['producer_sha256'], 'producer changed during dispatch')
        receipt.update(ambiguous_posts=result['ambiguous_posts'],
                       duplicate_execution_possible=result['duplicate_execution_possible'],
                       http_elapsed_seconds=sum(a['elapsed_seconds'] for a in result['attempts']))
        row.update(status=result['status'], http_status=result['http_status'])
        if result['status'] == 'http_response' and result['http_status'] != 200:
            row['status'] = 'http_error'
        raw = result['body']
        if result['status'] == 'http_response' and result['http_status'] == 200:
            check(type(raw) is bytes, 'captured response is not bytes')
            if key.encode() in raw:
                row['status'] = 'credential_reflection'
            else:
                row.update(raw_body_base64=base64.b64encode(raw).decode(), raw_body_sha256=sha(raw))
                receipt['http_body_received'] = True
        if not receipt['http_body_received']:
            receipt['stop_reason'] = row['status']
        check(receipt['network_attempts'] == result['network_attempts'] <= 1
              and receipt['potentially_billable_posts'] == result['potentially_billable_posts'] <= 1,
              'transport counters differ from the durable ledger')
    except BaseException as error:
        receipt.update(stop_reason=type(error).__name__, attempt_ledger_complete=False,
                       ambiguous_posts=None, duplicate_execution_possible=None)
        row['status'] = 'interrupted'
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        receipt['finished_at'] = now()
        write(run / 'response.json', row)
        write(run / 'transport-receipt.json', receipt)
    return receipt


def analyze(preparation, run):
    manifest = check_run(preparation, run)
    check(load((preparation / 'dispatch-reservation.json').read_bytes()) == lease(manifest), 'dispatch lease missing')
    receipt = load((run / 'transport-receipt.json').read_bytes())
    check(receipt['producer_sha256'] == producers()
          and receipt['manifest_sha256'] == sha((run / 'manifest.json').read_bytes())
          and receipt['dispatch_reservation_sha256'] == sha((preparation / 'dispatch-reservation.json').read_bytes()),
          'transport receipt binding differs')
    events = [load(line) for line in (run / 'attempts.jsonl').read_text().splitlines()]
    check(all(e['wire_sha256'] == manifest['request_sha256'] and e['attempt'] == 1 for e in events), 'ledger identity differs')
    starts = sum(e['event'] == 'attempt_started' for e in events)
    posts = sum(e['event'] == 'post_may_start' for e in events)
    check(starts == receipt['network_attempts'] <= 1 and posts == receipt['potentially_billable_posts'] <= 1,
          'ledger counters differ')
    if receipt['attempt_ledger_complete']:
        check([e['event'] for e in events] in (['attempt_started', 'attempt_finished'],
              ['attempt_started', 'post_may_start', 'attempt_finished']), 'ledger lifecycle differs')
    row = load((run / 'response.json').read_bytes())
    check(row['request_sha256'] == manifest['request_sha256'], 'captured request identity differs')
    check(receipt['http_body_received'] == (row['raw_body_base64'] is not None), 'body receipt differs')
    raw = None
    if row['raw_body_base64'] is not None:
        raw = base64.b64decode(row['raw_body_base64'], validate=True)
        check(sha(raw) == row['raw_body_sha256'], 'captured response digest differs')
        check(row['status'] == 'http_response' and row['http_status'] == 200
              and receipt['http_body_received'], 'response lifecycle differs')
    prepared = selected()[2]
    inspection = inspect(prepared, raw, captured_request_sha256=manifest['request_sha256'],
                         execution_status='completed' if raw is not None else 'transport_failed')
    return dict(study=STUDY, run_id=RUN_ID, observation_scope='one_historical_development_view_not_accuracy',
        transport=receipt, inspection=inspection, source_native_receipt_sha256=RECEIPT_SHA256,
        transport_receipt_sha256=sha((run / 'transport-receipt.json').read_bytes()),
        raw_capture_sha256=sha((run / 'response.json').read_bytes()),
        http_status=row['http_status'], semantic_accuracy=None, new_sol_calls=0,
        metric_effect='none', automatic_fact_acceptance=False)


def save_report(preparation, run):
    report = analyze(preparation, run)
    write(run / 'report.json', report)
    with (run / 'report.md').open('x', encoding='utf-8') as output:
        output.write(render(report))
    write(run / 'result-receipt.json', dict(study=STUDY, producer_sha256=producers(),
        file_sha256={str(p.relative_to(run)): sha(p.read_bytes()) for p in sorted(run.rglob('*')) if p.is_file()},
        report_status=report['inspection']['status']))
    return dict(status=report['inspection']['status'], review_status=report['inspection']['review_status'],
                report=str(run / 'report.md'), additional_hosted_requests=0)


def verify_result(preparation, run):
    receipt = load((run / 'result-receipt.json').read_bytes())
    check(receipt['study'] == STUDY and receipt['producer_sha256'] == producers(), 'result producers differ')
    check(receipt['file_sha256'] == {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*')
          if p.is_file() and p != run / 'result-receipt.json'}, 'result inventory differs')
    report = analyze(preparation, run)
    check(receipt['report_status'] == report['inspection']['status'], 'result status differs')
    check((run / 'report.json').read_text() == encoded(report) + '\n'
          and (run / 'report.md').read_text() == render(report), 'report replay differs')
    return dict(verified=True, status=report['inspection']['status'], additional_hosted_requests=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, default=PREPARATION)
    parser.add_argument('--run', type=Path, default=RUN)
    action = parser.add_mutually_exclusive_group(required=True)
    for name in ('freeze', 'stage', 'live', 'report', 'verify'):
        action.add_argument('--' + name, action='store_true')
    args = parser.parse_args()
    if args.freeze:
        freeze(args.preparation)
        result = dict(frozen=True, inference=False)
    elif args.stage:
        result = stage(args.preparation, args.run)
    elif args.live:
        receipt = execute(args.preparation, args.run, live=True)
        result = {key: receipt[key] for key in ('started_at', 'finished_at', 'network_attempts',
            'potentially_billable_posts', 'ambiguous_posts', 'http_body_received', 'stop_reason')}
    elif args.report:
        result = save_report(args.preparation, args.run)
    else:
        result = verify_result(args.preparation, args.run)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
