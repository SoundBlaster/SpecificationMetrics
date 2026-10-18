"""Bounded ordinary-Luna pilot through Jev4Mellea 0.8.0; no native emulation."""
import argparse
import base64
from datetime import datetime, timezone
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time

import httpx2
from mellea_jev import CategoricalTask, ChoiceQuestion, ResponsesChoiceProvider
from mellea_jev.providers.responses import ResponsesProviderError
from specification_core import TraceRecorder

from coreinfra_retry_run import decode, sha
import instruction_parity_v1 as parity
from paired_blind_reference_v1 import AXES, require
from retrieval_fact_adapter_v1 import RULES
from retrieval_fact_adapter_v1.context import NativeProposal
from retrieval_fact_adapter_v1.dependencies import local_closure
from retrieval_index_v1.source import encoded

ROOT = Path(__file__).resolve().parent
STUDY = 'specmetrics.ordinary-luna-categorical/v1'
PROVIDER = 'luna-responses-coreinfra'
ENDPOINT = 'https://hub.coreinfra.ai/openai/api/v1/responses'
MODEL = 'gpt-6-luna'
SETTINGS = dict(model=MODEL, reasoning_effort='low', max_output_tokens=1024,
                timeout=30.0, max_response_bytes=1048576)
PREPARATION = ROOT / 'runs/2026-10-18-ordinary-luna-preparation-v1'
RUN = ROOT / 'runs/2026-10-18-ordinary-luna-live-v1'
OFFLINE_KEY = 'specmetrics-offline-fixture-key-not-a-credential'


def now():
    return datetime.now(timezone.utc).isoformat()


def producers():
    files = local_closure(ROOT, [Path(__file__).resolve()])
    files += [ROOT / n for n in ('requirements-categorical-pilot.txt', 'requirements-categorical-pilot.lock',
                                'ordinary-luna-categorical-pilot-v1.md')]
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(files)}


def sdk_inventory():
    lock = (ROOT / 'requirements-categorical-pilot.lock').read_text()
    names = [line.split('==')[0].split(' @ ')[0] for line in lock.splitlines()
             if line and not line.startswith(('#', ' '))]
    sources = {}
    for name in ('mellea_jev', 'openai', 'httpx2', 'httpcore2', 'typesafe_sdk'):
        module = importlib.import_module(name)
        package = Path(module.__file__).resolve().parent
        files = {str(p.relative_to(package)): sha(p.read_bytes()) for p in sorted(package.rglob('*.py'))}
        sources[name] = dict(python_files=len(files), source_tree_sha256=sha(encoded(files).encode()))
    versions = {name: importlib.metadata.version(name) for name in names}
    require(versions['mellea-jev-adapter'] == '0.8.0' and versions['openai'] == '3.31.0', 'SDK version differs')
    return dict(distributions=versions, source_trees=sources)


def task_from(value):
    return CategoricalTask(state=value['state'], questions={
        name: ChoiceQuestion(instructions=q['instructions'], criteria=q['criteria'])
        for name, q in value['questions'].items()})


def provider(*, key=None, transport=None):
    return ResponsesChoiceProvider(api_key=key, api_key_env='COREINFRA_API_KEY',
        endpoint_url=ENDPOINT, transport=transport, **SETTINGS)


def envelope(answers):
    """Synthetic offline envelope, never provider evidence or reference labels."""
    return encoded(dict(id='offline-fixture', object='response', status='completed', model=MODEL,
        output=[dict(type='message', role='assistant', status='completed',
                     content=[dict(type='output_text', text=encoded(dict(answers=answers)))])])).encode()


def result_record(result):
    return dict(answers=dict(result.answers), requested_model=result.requested_model,
        returned_model=result.returned_model, request_id=result.request_id,
        usage=(dict(input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens)
               if result.usage is not None else None),
        adapter_revision=result.adapter_revision, settings=dict(result.settings or {}))


def render(task):
    calls = []
    answers = {axis: 'insufficient' if axis == 'evidence_confidence' else 'unknown' for axis in task.questions}

    def handle(request):
        require(request.method == 'POST' and str(request.url) == ENDPOINT, 'unexpected SDK operation')
        calls.append(request.content)
        return httpx2.Response(200, content=envelope(answers), headers={'content-type': 'application/json'})

    with provider(key=OFFLINE_KEY, transport=httpx2.MockTransport(handle)) as client:
        result = client.classify(task)
    require(len(calls) == 1 and result.evidence.request_json.encode() == calls[0], 'SDK render evidence differs')
    return result.evidence.request_json


def native_reference():
    current = parity.score(parity.PREPARATION, parity.RUN)
    saved = decode((parity.RUN / 'comparison.json').read_bytes())
    require(parity.portable_comparison(current) == parity.portable_comparison(saved), 'native comparison differs')
    receipt = decode((parity.RUN / 'result-receipt.json').read_bytes())
    require(receipt['producer_sha256'] == parity.source_digests()
            and receipt['file_sha256'] == {str(p.relative_to(parity.RUN)): sha(p.read_bytes())
                for p in parity.RUN.rglob('*') if p.is_file() and p.name != 'result-receipt.json'}, 'native receipt differs')
    return saved


def expected():
    manifest = parity.verify(parity.PREPARATION)
    native_reference()
    requests = []
    for old in manifest['requests']:
        if old['provider'] != 'jev-coreinfra':
            continue
        wire = decode(old['wire_json'])
        value = dict(state=decode(wire['state']), questions={
            name: dict(instructions=q['instructions'], criteria=q['criteria'])
            for name, q in wire['questions'].items()})
        task = task_from(value)
        require(task.to_dict() == value, 'SDK changed semantic task')
        request_json = render(task)
        requests.append(dict(request_id=old['case_id'] + '-' + old['arm'] + '-' + PROVIDER,
            case_id=old['case_id'], arm=old['arm'], source_request_id=old['request_id'],
            native_wire_sha256=old['wire_sha256'], state_sha256=sha(wire['state'].encode()),
            task=value, request_json=request_json, request_sha256=sha(request_json.encode())))
    require(len(requests) == 8, 'pilot requires eight unchanged views')
    return dict(study=STUDY, provider=PROVIDER, endpoint=ENDPOINT, settings=SETTINGS,
        python_constraint='>=3.11', sdk=sdk_inventory(), producer_sha256=producers(),
        source_preparation_receipt_sha256=sha((parity.PREPARATION / 'preparation-receipt.json').read_bytes()),
        native_result_receipt_sha256=sha((parity.RUN / 'result-receipt.json').read_bytes()),
        sol_top_line_sha256=sha((parity.SOL_RUN / 'top-line.json').read_bytes()),
        sol_receipt_sha256=sha((parity.SOL_RUN / 'receipt.json').read_bytes()), new_sol_calls=0,
        planned_requests=8, max_http_dispatches=8, automatic_retries=0, semantic_retries=False,
        grouping='four named questions over shared state in one request per view',
        question_semantics='same state, original categories and aligned instructions as native parity run',
        format_difference='Responses strict schema and shared generation; native question evaluation internals unknown',
        evidence_scope='SDK credential-redacted bounded evidence plus local dispatch ledger; not remote attestation',
        authorization='User approved the eight-view ordinary-Luna pilot after reviewing SDK 0.8.0 proposal.',
        scoring=dict(axes=list(AXES), primary_axes=list(parity.previous.PRIMARY), planned_axis_slots=32,
            planned_primary_slots=16, reference_authority='agreement_with_saved_Sol_not_semantic_accuracy',
            incomplete='keep errors and prefix visible; no complete-cohort agreement',
            probabilities='not_generated_or_consumed', automatic_fact_acceptance=False, metric_effect='none'),
        requests=requests)


def freeze(output):
    manifest = expected()
    output.mkdir(exist_ok=False)
    (output / 'manifest.json').write_text(encoded(manifest) + '\n')
    (output / 'preparation-receipt.json').write_text(encoded(dict(study=STUDY,
        manifest_sha256=sha((output / 'manifest.json').read_bytes()), producer_sha256=producers(), hosted_requests=0)) + '\n')
    return verify(output)


def verify(preparation):
    require({p.name for p in preparation.iterdir()} == {'manifest.json', 'preparation-receipt.json'}, 'preparation inventory differs')
    manifest = expected()
    require((preparation / 'manifest.json').read_text() == encoded(manifest) + '\n', 'frozen pilot differs')
    require(decode((preparation / 'preparation-receipt.json').read_bytes()) == dict(study=STUDY,
        manifest_sha256=sha((preparation / 'manifest.json').read_bytes()), producer_sha256=producers(), hosted_requests=0),
        'preparation receipt differs')
    return manifest


def stage(preparation, run):
    manifest = verify(preparation)
    run.mkdir(exist_ok=False)
    (run / 'manifest.json').write_bytes((preparation / 'manifest.json').read_bytes())
    (run / 'preparation-binding.json').write_text(encoded(dict(study=STUDY,
        preparation_receipt_sha256=sha((preparation / 'preparation-receipt.json').read_bytes()),
        logical_request_limit=8, http_dispatch_limit=8, semantic_retries=False, new_sol_calls=0)) + '\n')
    return dict(staged=True, inference=False, planned_requests=manifest['planned_requests'])


def check_run(preparation, run):
    manifest = verify(preparation)
    require((run / 'manifest.json').read_bytes() == (preparation / 'manifest.json').read_bytes(), 'run manifest differs')
    require(decode((run / 'preparation-binding.json').read_bytes()) == dict(study=STUDY,
        preparation_receipt_sha256=sha((preparation / 'preparation-receipt.json').read_bytes()),
        logical_request_limit=8, http_dispatch_limit=8, semantic_retries=False, new_sol_calls=0), 'run binding differs')
    return manifest


class DispatchTransport(httpx2.BaseTransport):
    """Record only body identity and safe counters, never headers/credentials."""
    def __init__(self, inner, request, emit):
        self.inner, self.request, self.emit, self.calls = inner, request, emit, 0

    def handle_request(self, request):
        # The endpoint router forwards a stream. MockTransport normally reads it
        # later; an auditing transport must materialize it before .content.
        request.read()
        require(self.calls == 0 and request.method == 'POST' and str(request.url) == ENDPOINT
                and request.content == self.request['request_json'].encode(), 'SDK dispatch differs or repeats')
        self.calls += 1
        self.emit(dict(event='http_dispatch_started', request_sha256=sha(request.content),
                       post_may_have_been_sent=True))
        return self.inner.handle_request(request)

    def close(self):
        self.inner.close()


def execute(preparation, run, *, live=False, transport_factory=None):
    manifest = check_run(preparation, run)
    if not live:
        return dict(validated=True, inference=False, planned_requests=8)
    require(bool(os.environ.get('COREINFRA_API_KEY')), 'COREINFRA_API_KEY is unavailable')
    require(not any((run / n).exists() for n in ('attempts.jsonl', 'responses.jsonl', 'receipt.json')),
            'refuse to repeat or overwrite a run')
    sources, sdk = producers(), sdk_inventory()
    receipt = dict(study=STUDY, manifest_sha256=sha((run / 'manifest.json').read_bytes()),
        producer_sha256=sources, sdk=sdk,
        execution_runtime=dict(python=platform.python_version(), implementation=platform.python_implementation(),
                               platform=platform.system()),
        started_at=now(), planned_requests=8, max_http_dispatches=8, attempted_tasks=0,
        http_dispatches=0, potentially_billable_posts=0, ambiguous_posts=0,
        duplicate_execution_possible=False, successful_tasks=0, completed=False,
        automatic_retries=0, new_sol_calls=0, stop_reason=None)
    with (run / 'attempts.jsonl').open('x') as ledger:
        try:
            with (run / 'responses.jsonl').open('x') as output:
                for item in manifest['requests']:
                    require(producers() == sources and receipt['http_dispatches'] < 8, 'producer or budget differs')
                    receipt['attempted_tasks'] += 1

                    def emit(event):
                        ledger.write(encoded(dict(request_id=item['request_id'], recorded_at=now(), **event)) + '\n')
                        ledger.flush()
                        os.fsync(ledger.fileno())
                        if event['event'] == 'http_dispatch_started':
                            receipt['http_dispatches'] += 1
                            receipt['potentially_billable_posts'] += 1  # Conservative dispatch boundary.

                    inner = (transport_factory(item) if transport_factory is not None
                             else httpx2.HTTPTransport(retries=0, trust_env=False))
                    audited = DispatchTransport(inner, item, emit)
                    started = time.monotonic()
                    result, evidence, status = None, None, 'completed'
                    try:
                        with provider(transport=audited) as client:
                            answer = client.classify(task_from(item['task']))
                        evidence = answer.evidence
                        result = result_record(answer)
                        if answer.requested_model != MODEL or answer.returned_model != MODEL:
                            status, result = 'response_identity_error', None
                    except ResponsesProviderError as error:
                        status, evidence = type(error).__name__, error.evidence
                    except Exception as error:
                        # Preserve unexpected client defects without their text or
                        # unredacted diagnostic objects; stop the cohort afterward.
                        status = 'unexpected_' + type(error).__name__
                    body = evidence.response_body if evidence else None
                    ambiguous = audited.calls if audited.calls and body is None else 0
                    elapsed = time.monotonic() - started
                    row = dict(request_id=item['request_id'], case_id=item['case_id'], arm=item['arm'],
                        request_sha256=item['request_sha256'], http_dispatches=audited.calls,
                        status=status, result=result, elapsed_seconds=elapsed, ambiguous_posts=ambiguous,
                        sdk_request_json=evidence.request_json if evidence else None,
                        sdk_response_base64=base64.b64encode(body).decode() if body is not None else None,
                        sdk_response_sha256=sha(body) if body is not None else None)
                    output.write(encoded(row) + '\n')
                    output.flush()
                    os.fsync(output.fileno())
                    receipt['ambiguous_posts'] += ambiguous
                    receipt['successful_tasks'] += status == 'completed'
                    emit(dict(event='sdk_call_finished', status=status, http_dispatches=audited.calls,
                              ambiguous_posts=ambiguous, elapsed_seconds=elapsed))
                    if status != 'completed':
                        receipt['stop_reason'] = status
                        break
                receipt['completed'] = receipt['successful_tasks'] == 8
        except BaseException as error:
            receipt['stop_reason'] = type(error).__name__  # No exception text or credentials.
            raise
        finally:
            receipt.update(finished_at=now(), producers_unchanged=producers() == sources and sdk_inventory() == sdk,
                file_sha256={n: sha((run / n).read_bytes()) for n in ('attempts.jsonl', 'responses.jsonl')
                             if (run / n).is_file()})
            with (run / 'receipt.json').open('x') as stream:
                stream.write(encoded(receipt) + '\n')
    return receipt


def replay(item, body, request_id):
    calls = []

    def handle(request):
        require(request.content == item['request_json'].encode() and str(request.url) == ENDPOINT,
                'replay SDK request differs')
        calls.append(request.content)
        headers = {'content-type': 'application/json'}
        if request_id is not None:
            headers['x-request-id'] = request_id
        return httpx2.Response(200, content=body, headers=headers)

    with provider(key=OFFLINE_KEY, transport=httpx2.MockTransport(handle)) as client:
        result = client.classify(task_from(item['task']))
    require(len(calls) == 1 and result.requested_model == MODEL and result.returned_model == MODEL,
            'response identity differs')
    return result_record(result)


def consistency(labels):
    candidate = NativeProposal(labels['concern_kind'], labels['evidence_confidence'],
                               labels['ownership'], labels['tool_responsibility'])
    recorder = TraceRecorder()
    violations = [code for spec, code in RULES if not spec.is_satisfied_by(candidate, recorder=recorder)]
    return dict(violations=violations, trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events])


def inspect(preparation, run):
    manifest = check_run(preparation, run)
    required = {'attempts.jsonl', 'responses.jsonl', 'receipt.json'}
    if not all((run / n).is_file() for n in required):
        return dict(status='not_executed_or_incomplete', transport_verified=False, rows=[], captured_rows=0)
    receipt = decode((run / 'receipt.json').read_bytes())
    require(receipt['study'] == STUDY and receipt['manifest_sha256'] == sha((run / 'manifest.json').read_bytes())
            and receipt['producer_sha256'] == producers() and receipt['sdk'] == manifest['sdk']
            and receipt['producers_unchanged'] is True and receipt['automatic_retries'] == 0
            and type(receipt['automatic_retries']) is int and type(receipt['new_sol_calls']) is int
            and receipt['new_sol_calls'] == 0 and receipt['duplicate_execution_possible'] is False,
            'execution receipt identity differs')
    require(receipt['file_sha256'] == {n: sha((run / n).read_bytes()) for n in ('attempts.jsonl', 'responses.jsonl')},
            'execution files differ')
    rows = [decode(line) for line in (run / 'responses.jsonl').read_bytes().splitlines()]
    events = [decode(line) for line in (run / 'attempts.jsonl').read_bytes().splitlines()]
    require(len(rows) <= 8, 'too many response rows')
    position, dispatches, successful, ambiguous = 0, 0, 0, 0
    verified = []
    for index, (item, row) in enumerate(zip(manifest['requests'], rows)):
        require(all(row[k] == item[k] for k in ('request_id', 'request_sha256', 'case_id', 'arm')),
                'response assignment differs')
        count = row['http_dispatches']
        require(type(count) is int and count in (0, 1), 'repeated or invalid dispatch count')
        if count:
            require(position < len(events), 'missing dispatch event')
            event = events[position]
            require(event['event'] == 'http_dispatch_started' and event['request_id'] == item['request_id']
                    and event['request_sha256'] == item['request_sha256']
                    and event['post_may_have_been_sent'] is True, 'dispatch identity differs')
            position += 1
        require(position < len(events), 'missing SDK completion')
        finish = events[position]
        position += 1
        require(finish['event'] == 'sdk_call_finished' and finish['request_id'] == item['request_id']
                and all(finish[k] == row[k] for k in ('status', 'http_dispatches', 'ambiguous_posts', 'elapsed_seconds')),
                'SDK completion differs')
        require(type(row['elapsed_seconds']) in (int, float) and row['elapsed_seconds'] >= 0
                and type(row['ambiguous_posts']) is int and row['ambiguous_posts'] in (0, count), 'invalid attempt metadata')
        if row['sdk_request_json'] is not None:
            require(row['sdk_request_json'] == item['request_json'], 'SDK evidence request differs')
        body = None
        if row['sdk_response_base64'] is not None:
            body = base64.b64decode(row['sdk_response_base64'], validate=True)
            require(len(body) <= SETTINGS['max_response_bytes'] and sha(body) == row['sdk_response_sha256'],
                    'SDK response body differs')
        else:
            require(row['sdk_response_sha256'] is None, 'missing SDK body')
        if row['status'] == 'completed':
            require(count == 1 and body is not None and row['ambiguous_posts'] == 0
                    and row['sdk_request_json'] == item['request_json'], 'successful row lacks evidence')
            decoded = replay(item, body, row['result']['request_id'])
            require(decoded == row['result'], 'SDK result replay differs')
            labels = decoded['answers']
            require(set(labels) == set(AXES), 'missing labels')
            verified.append(dict(request_id=item['request_id'], case_id=item['case_id'], arm=item['arm'],
                labels=labels, consistency=consistency(labels), response_sha256=sha(body)))
            successful += 1
        else:
            require(row['result'] is None and index == len(rows) - 1 and receipt['stop_reason'] == row['status'],
                    'failed SDK call was salvaged or followed by another request')
        dispatches += count
        ambiguous += row['ambiguous_posts']
    require(position == len(events), 'extra dispatch events')
    for key, expected_count in dict(planned_requests=8, max_http_dispatches=8, attempted_tasks=len(rows),
            http_dispatches=dispatches, potentially_billable_posts=dispatches,
            ambiguous_posts=ambiguous, successful_tasks=successful).items():
        require(type(receipt[key]) is int and receipt[key] == expected_count, 'receipt counter differs: ' + key)
    complete = successful == len(rows) == 8
    require(receipt['completed'] is complete and (not complete or receipt['stop_reason'] is None), 'completion claim differs')
    return dict(status='complete' if complete else 'incomplete', transport_verified=True,
        verification_scope='local_SDK_evidence_dispatch_ledger_consistency_not_remote_attestation',
        complete=complete, captured_rows=len(rows), verified_label_rows=successful,
        errors=[dict(request_id=r['request_id'], status=r['status']) for r in rows if r['status'] != 'completed'],
        rows=verified, execution_runtime=receipt['execution_runtime'],
        sdk_evidence='credential_redacted_not_unconditionally_identical_to_HTTP_wire_bytes')


def summarize(rows, references):
    axes = {axis: dict(matches=0, compared=len(rows), planned=8) for axis in AXES}
    per_arm, details = {}, []
    for arm in ('baseline', 'retrieval'):
        selected = [r for r in rows if r['arm'] == arm]
        per_arm[arm] = dict(matches=sum(sum(r['labels'][a] == references[r['case_id'], arm][a] for a in AXES)
                                        for r in selected), compared=len(selected) * 4, planned=16)
    for row in rows:
        reference = references[row['case_id'], row['arm']]
        for axis in AXES:
            axes[axis]['matches'] += row['labels'][axis] == reference[axis]
        details.append(dict(row, sol_labels=reference,
                            differing_axes=[a for a in AXES if row['labels'][a] != reference[a]]))
    return dict(valid_label_responses=len(rows), planned_responses=8, axes=axes, per_arm=per_arm,
        all_axis_matches=sum(v['matches'] for v in axes.values()), planned_axis_slots=32,
        primary_axis_matches=sum(axes[a]['matches'] for a in parity.previous.PRIMARY), planned_primary_slots=16,
        consistency_review=sum(bool(r['consistency']['violations']) for r in rows),
        coherent=sum(not r['consistency']['violations'] for r in rows),
        unknown_role=sum(r['labels']['concern_kind'] == 'unknown' for r in rows), details=details)


def score(preparation, run):
    evidence = inspect(preparation, run)
    references = {(v['case_id'], v['arm']): v['labels']
                  for v in decode((parity.SOL_RUN / 'top-line.json').read_bytes())['views']}
    rows = evidence.get('rows', []) if evidence.get('complete') else []
    native = native_reference()['providers']
    return dict(study=STUDY, provider=PROVIDER, transport=evidence,
        agreement_status='complete_label_comparison' if evidence.get('complete') else 'not_evaluable_incomplete_cohort',
        ordinary_luna=summarize(rows, references),
        native_comparators={p: {k: r[k] for k in ('all_axis_matches', 'primary_axis_matches', 'consistency_review',
                                                  'coherent', 'native_valid', 'details')} for p, r in native.items()},
        preparation_receipt_sha256=sha((preparation / 'preparation-receipt.json').read_bytes()),
        sol_top_line_sha256=sha((parity.SOL_RUN / 'top-line.json').read_bytes()), new_sol_calls=0,
        semantic_accuracy=None, automatic_fact_acceptance=False, metric_effect='none')


def seal(preparation, run):
    report = score(preparation, run)
    require(decode((run / 'comparison.json').read_bytes()) == report, 'comparison does not reconstruct')
    receipt = dict(study=STUDY, status=report['transport']['status'], producer_sha256=producers(),
        preparation_receipt_sha256=report['preparation_receipt_sha256'], new_sol_calls=0,
        file_sha256={str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*')
                     if p.is_file() and p.name != 'result-receipt.json'}, semantic_accuracy=None, automatic_fact_acceptance=False)
    with (run / 'result-receipt.json').open('x') as stream:
        stream.write(encoded(receipt) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['freeze', 'verify', 'stage', 'execute', 'score', 'seal'])
    parser.add_argument('--preparation', type=Path, default=PREPARATION)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.mode == 'freeze':
        result = freeze(args.preparation)
    elif args.mode == 'verify':
        result = verify(args.preparation)
    elif args.mode == 'stage':
        result = stage(args.preparation, args.run)
    elif args.mode == 'execute':
        result = execute(args.preparation, args.run, live=args.live)
    elif args.mode == 'seal':
        result = seal(args.preparation, args.run)
    else:
        result = score(args.preparation, args.run)
        with (args.run / 'comparison.json').open('x') as stream:
            stream.write(encoded(result) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in
        ('requests', 'producer_sha256', 'sdk', 'transport', 'ordinary_luna', 'native_comparators', 'file_sha256')}, indent=2))


if __name__ == '__main__':
    main()
