"""Freeze/stage/decode a bounded native transport smoke, without live execution."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import coreinfra_retry_run as transport
from coreinfra_transport import PROTOCOL, RetryPolicy
from decision_choice_contract_v2 import ChoiceContractError
import intent_first_native_v1 as native
import prepare_intent_first_v4_1 as source
from question_grouping import canonical, digest

ROOT = source.ROOT
RUN = ROOT / 'runs/2026-10-15-intent-first-native-preparation-v1'
STUDY = 'specmetrics.intent-first-native-transport-smoke/v1'
IMPLEMENTATIONS = ('intent_first_native_v1.py', 'prepare_intent_first_native.py',
                   'decision_choice_contract_v2.py', 'decision_choice_contract.py',
                   'coreinfra_retry_run.py', 'coreinfra_transport.py', 'question_grouping.py')


def build():
    inputs = source.verify()
    packet = json.loads(inputs['packet.json'])
    question_hash = digest(canonical(native.QUESTIONS))
    requests = []
    for index, case in enumerate(packet['cases']):
        state = canonical(case['state'])
        if len(state) > 16 * 1024:
            raise ValueError('oversized state; never truncate')
        native_task = digest(canonical({'study': STUDY, 'policy': native.POLICY,
                                       'source_task_sha256': case['task_sha256'],
                                       'wire_state_sha256': digest(state), 'questions_sha256': question_hash}))
        providers = list(native.PROVIDERS)
        if index % 2:
            providers.reverse()
        for provider in providers:
            model, endpoint = native.PROVIDERS[provider]
            wire = canonical(native.wire_body(provider, state.decode('utf-8')))
            if len(wire) > 64 * 1024:
                raise ValueError('oversized wire; never truncate')
            requests.append({'request_id': case['case_id'] + '-' + provider, 'case_id': case['case_id'],
                             'source_task_sha256': case['task_sha256'], 'native_task_sha256': native_task,
                             'source_state_sha256': case['state_sha256'], 'wire_state_sha256': digest(state),
                             'scope_binding_sha256': case['scope_binding_sha256'],
                             'provider': provider, 'requested_model': model, 'endpoint': endpoint,
                             'questions_sha256': question_hash, 'wire_json': wire.decode('utf-8'),
                             'wire_sha256': digest(wire)})
    policy = RetryPolicy()
    manifest = {'protocol': PROTOCOL, 'study': STUDY, 'status': 'prepared_offline_not_live_authorized',
                'semantic_status': 'unscored', 'projection_policy': native.POLICY,
                'source_contract_id': packet['contract_id'], 'source_contract_sha256': packet['contract_sha256'],
                'retry_policy': asdict(policy), 'producer_digests': transport.producer_digests(),
                'projection_producer_sha256': {n: digest((ROOT / n).read_bytes()) for n in IMPLEMENTATIONS},
                'input_file_sha256': {str((source.RUN / n).relative_to(ROOT)): digest(v) for n, v in inputs.items()},
                'questions_sha256': question_hash, 'requests': requests, 'planned_requests': len(requests),
                'max_network_attempts': len(requests) * policy.max_attempts,
                'full_v4_1_annotation': False, 'native_live_compatibility_verified': False,
                'human_gold': False, 'provider_scoring_enabled': False, 'metric_effect': 'none',
                'live_authorization': 'Separate explicit authorization for 8 requests / at most 24 attempts; preparation is not consent.'}
    files = {'manifest.json': source.rules.encoded(manifest), 'questions.json': source.rules.encoded(native.QUESTIONS),
             'README.md': (
                 '# Intent-first native preparation v1\n\n'
                 'Four pinned-source development cases x two providers = 8 logical requests;\n'
                 'at most 24 network attempts including TLS retries. No live requests were made.\n'
                 'This is a native Choice projection of concern kind, ordinal evidence support and\n'
                 'recommendation. It cannot return a full v4.1 annotation: no basis/rationale/quotes\n'
                 'are synthesized. Provider confidence is stored separately from the ordinal category.\n\n'
                 'The wire contains only case state and three questions, never integrator example labels.\n'
                 'Jev and Luna receive identical canonical state and criteria in their native envelopes.\n'
                 'Models/endpoints follow the previously observed frozen native protocol; present live\n'
                 'availability and three-question API compatibility remain unverified.\n\n'
                 'See the [handoff guide](../../intent-first-native-handoff.md) for commands, limits and\n'
                 'the distinct transport, native-shape, tuple-consistency and semantic-review stages.\n'
                 'No gold/accuracy/generalization claim or production S/U change follows.\n'
             ).encode()}
    files['preparation-receipt.json'] = source.rules.encoded({
        'status': 'native_wires_prepared_no_inference', 'study': STUDY,
        'artifact_file_sha256': {n: digest(v) for n, v in files.items()},
        'projection_policy': native.POLICY, 'logical_requests': len(requests),
        'max_network_attempts': manifest['max_network_attempts'], 'provider_requests': 0,
        'full_v4_1_annotation': False, 'human_gold': False, 'metric_effect': 'none'})
    files['SHA256SUMS'] = ''.join(digest(v) + '  ' + n + '\n' for n, v in sorted(files.items())).encode()
    return files


def verify(run=RUN):
    files = build()
    if {p.name for p in run.iterdir()} != set(files):
        raise ValueError('native preparation file set differs')
    for name, value in files.items():
        if (run / name).read_bytes() != value:
            raise ValueError('native preparation bytes differ: ' + name)
    return files


def write(run):
    files = build()
    run.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (run / name).open('xb') as stream:
            stream.write(value)


def stage(destination, preparation=RUN):
    files = verify(preparation)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / 'manifest.json').open('xb') as stream:
        stream.write(files['manifest.json'])
    return transport.execute(destination, live=False)


def inspect(run, preparation=RUN):
    files = verify(preparation)
    if (run / 'manifest.json').read_bytes() != files['manifest.json']:
        raise ValueError('execution manifest differs from frozen preparation')
    manifest = json.loads(files['manifest.json'])
    expected = {r['request_id']: r for r in manifest['requests']}
    path = run / 'responses.jsonl'
    response_bytes = path.read_bytes() if path.exists() else None
    rows, seen = [], set()
    for raw in response_bytes.splitlines() if response_bytes is not None else []:
        item = transport.decode(raw)
        if not isinstance(item, dict) or item.get('status') not in {
                'json_received', 'http_error', 'response_decode_error', 'transport_error', 'response_too_large'}:
            raise ValueError('malformed transport response row')
        rid = item.get('request_id')
        if not isinstance(rid, str) or rid not in expected or rid in seen:
            raise ValueError('unexpected or duplicate response identity')
        request = expected[rid]
        if item.get('protocol') != PROTOCOL or item.get('wire_sha256') != request['wire_sha256']:
            raise ValueError('response wire/protocol binding mismatch')
        seen.add(rid)
        row = {'request_id': rid, 'provider': request['provider'], 'case_id': request['case_id'],
               'transport_status': item.get('status'), 'prediction': None, 'native_status': 'not_evaluated',
               'projection_status': 'not_evaluated'}
        if item.get('status') == 'json_received':
            if item.get('http_status') != 200 or not isinstance(item.get('response'), dict):
                raise ValueError('malformed received JSON response row')
            try:
                row['prediction'] = native.parse_response(canonical(item['response']), provider=request['provider'],
                                                           model=request['requested_model'])
                row['native_status'] = 'valid'
                row['projection_status'] = ('consistent_native_projection' if row['prediction']['tuple_consistent']
                                            else 'inconsistent_native_projection')
            except ChoiceContractError as error:
                row.update(native_status='invalid', projection_status='native_invalid', rejection_code=error.code)
        rows.append(row)
    return {'status': 'observed_native_rows_decoded_not_semantically_scored' if rows else 'no_response_rows_recorded',
            'planned_requests': len(expected), 'observed_response_rows': len(rows), 'rows': rows,
            'requests_without_response_rows': [rid for rid in expected if rid not in seen],
            'execution_inferred_from_missing_rows': False, 'transport_ledger_verified': False,
            'response_file_sha256': digest(response_bytes) if response_bytes is not None else None,
            'full_v4_1_annotation': False, 'provider_scoring_enabled': False, 'metric_effect': 'none'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN, help='frozen preparation directory')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--write', action='store_true')
    action.add_argument('--stage', type=Path, help='create a NEW transport run, offline only')
    action.add_argument('--inspect', type=Path, help='decode existing response rows, no requests')
    args = parser.parse_args()
    if args.stage:
        result = stage(args.stage, args.run)
    elif args.inspect:
        result = inspect(args.inspect, args.run)
    else:
        write(args.run) if args.write else verify(args.run)
        result = {'status': 'native_wires_prepared_no_inference', 'planned_requests': 8,
                  'max_network_attempts': 24, 'inference': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
