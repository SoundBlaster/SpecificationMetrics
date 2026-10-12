#!/usr/bin/env python3
"""Freeze/run the 48-request contrastive diagnostic; offline unless --live."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from coreinfra_retry_run import decode
from coreinfra_transport import PROTOCOL, RetryPolicy, post
from decision_choice_contract import parse_response
from prepare_contrastive_pairs import RUN as REFERENCE, build as prepare
from question_grouping import canonical, digest
from validate_contrastive_reference import compare

ROOT = Path(__file__).parent
RUN = ROOT / 'runs/2026-10-13-contrastive-native-wires'
STUDY = 'contrastive_mechanics_policy_native/v1'
PROVIDERS = (
    ('jev-coreinfra', 'jev-1.13.0', 'https://hub.coreinfra.ai/typesafe/api/v1/systemone'),
    ('luna-decision-coreinfra', 'gpt-6-luna', 'https://hub.coreinfra.ai/openai/api/v1/decisions'),
)
INPUTS = ('scenarios.json', 'source-evidence.json', 'study-plan.json', 'case-packet.json',
          'source-mapping.json', 'author-proposals.json', 'annotation-template.json',
          'logical-schedule.json', 'preparation-receipt.json', 'independent-annotations.json',
          'reference-review.json', 'reference-review.md')
PRODUCERS = ('contrastive_decision_study.py', 'score_contrastive_decisions.py',
             'prepare_contrastive_pairs.py', 'validate_contrastive_reference.py',
             'decision_choice_contract.py', 'coreinfra_transport.py',
             'coreinfra_retry_run.py', 'question_grouping.py')
OUTPUTS = ('attempts.jsonl', 'responses.jsonl', 'receipt.json')


def load_reference(reference=REFERENCE):
    """Verify the reviewed phase, not the historical blank template's status."""
    raw = {name: (reference / name).read_bytes() for name in INPUTS}
    data = {name: decode(value) for name, value in raw.items() if name.endswith('.json')}
    for name, expected in prepare(reference).items():
        if canonical(data[name]) != canonical(expected):
            raise ValueError('Preparation no longer replays: ' + name)
    packet = data['case-packet.json']
    review = data['reference-review.json']
    result = compare(packet, data['independent-annotations.json'],
                     data['author-proposals.json'], data['source-mapping.json'])
    bindings = {'reference_sha256': 'independent-annotations.json',
                'packet_file_sha256': 'case-packet.json', 'template_sha256': 'annotation-template.json',
                'proposals_sha256': 'author-proposals.json', 'mapping_sha256': 'source-mapping.json'}
    if (review['status'] != 'independent_model_reference_reviewed_native_wires_pending'
            or review['comparison'] != result or review['label_overrides'] != []
            or review['metric_effect'] != 'none'
            or review['validator_sha256'] != digest((ROOT / 'validate_contrastive_reference.py').read_bytes())
            or any(review[key] != digest(raw[name]) for key, name in bindings.items())):
        raise ValueError('Reference review is non-ready or stale')
    # The protocol requires opposed full pairs and separately adjudicated controls.
    # A future disagreement requires a new corpus/version, never forced labels.
    labels = {'mechanics': ('excluded', 'mechanics'), 'policy': ('eligible', 'policy'),
              'withheld': ('needs_review', 'unknown')}
    annotations = {r['case_id']: r for r in data['independent-annotations.json']['annotations']}
    for item in data['source-mapping.json']['cases']:
        row = annotations[item['case_id']]
        if (row['opportunity'], row['concern_kind']) != labels[item['stratum']]:
            raise ValueError('Reference does not support the preregistered contrast; revise the study')
    plan = data['study-plan.json']
    if ([(p['id'], p['requested_model'], p['endpoint']) for p in plan['providers']] != list(PROVIDERS)
            or plan['design']['retry_protocol'] != PROTOCOL):
        raise ValueError('Provider/retry contract differs from reviewed protocol')
    return data, {name: digest(value) for name, value in raw.items()}


def build(reference=REFERENCE):
    data, input_hashes = load_reference(reference)
    packet, schedule = data['case-packet.json'], data['logical-schedule.json']
    cases = {case['case_id']: case for case in packet['cases']}
    questions = packet['questions']
    if set(questions) != {'opportunity', 'concern_kind'} or any(q['type'] != 'choice' for q in questions.values()):
        raise ValueError('Expected two Choice questions')
    providers = {provider: (model, endpoint) for provider, model, endpoint in PROVIDERS}
    requests = []
    for item in schedule['requests']:
        state = canonical(cases[item['case_id']]['state'])
        if digest(state) != item['state_sha256'] or len(state) > 16 * 1024:
            raise ValueError('Stale or oversized state')
        model, endpoint = providers[item['provider']]
        if item['provider'] == 'jev-coreinfra':
            body = {'model': model, 'state': state.decode('utf-8'), 'questions': questions}
        else:
            body = {'model': model, 'input': state.decode('utf-8'), 'questions': [
                {'type': 'choice', 'name': axis, 'instructions': q['instructions'],
                 'choices': [{'value': label, 'description': description}
                             for label, description in sorted(q['criteria'].items())]}
                for axis, q in sorted(questions.items())]}
        wire = canonical(body)
        if len(wire) > 64 * 1024:
            raise ValueError('Oversized wire; never truncate')
        requests.append({**item, 'requested_model': model, 'endpoint': endpoint,
                         'questions_sha256': digest(canonical(questions)),
                         'wire_json': wire.decode('utf-8'), 'wire_sha256': digest(wire)})
    return {'schema_version': 1, 'study': STUDY, 'protocol': PROTOCOL,
            'status': 'native_wires_frozen_live_not_started', 'semantic_status': 'unscored',
            'reference_authority': data['reference-review.json']['authority'],
            'input_sha256': input_hashes,
            'producer_digests': {name: digest((ROOT / name).read_bytes()) for name in PRODUCERS},
            'retry_policy': asdict(RetryPolicy()), 'planned_requests': 48, 'max_network_attempts': 144,
            'hypotheses': data['study-plan.json']['hypotheses'],
            'criteria': data['study-plan.json']['criteria'], 'requests': requests,
            'encoding': 'Identical canonical UTF-8 state and rubric; native envelopes differ. Only state and questions reach providers; no case/pair IDs, author proposals, reference labels or annotation instructions.',
            'metric_effect': 'none', 'live_authorization': 'Explicit --live opt-in required; this artifact does not authorize inference.'}


def validate(run=RUN, reference=REFERENCE):
    raw = (run / 'manifest.json').read_bytes()
    manifest = decode(raw)
    if canonical(manifest) != canonical(build(reference)):
        raise ValueError('Frozen native manifest differs from current inputs/producers')
    return manifest, RetryPolicy(**manifest['retry_policy']), digest(raw)


def execute(run=RUN, *, live=False, reference=REFERENCE, sender=post):
    manifest, policy, manifest_hash = validate(run, reference)
    if not live:
        return {'validated': True, 'planned_requests': 48, 'max_network_attempts': 144,
                'manifest_sha256': manifest_hash, 'inference': False, 'metric_effect': 'none'}
    if any((run / name).exists() for name in OUTPUTS):
        raise ValueError('Refusing to repeat or overwrite a hosted run')
    key = os.environ.get('COREINFRA_API_KEY')
    if not key or any(ord(c) <= 32 or ord(c) >= 127 for c in key):
        raise ValueError('Missing or invalid COREINFRA_API_KEY')
    # Exclusive ledger creation is the run lock. Persist intent before any POST.
    with (run / 'attempts.jsonl').open('x', encoding='utf-8') as ledger:
        started = time.monotonic()
        receipt = {'study': STUDY, 'protocol': PROTOCOL, 'manifest_sha256': manifest_hash,
                   'started_at': datetime.now(timezone.utc).isoformat(),
                   'planned_requests': 48, 'max_network_attempts': 144,
                   'attempted_requests': 0, 'network_attempts': 0, 'potentially_billable_posts': 0,
                   'received_json_responses': 0, 'native_valid_responses': 0,
                   'ambiguous_posts': 0, 'duplicate_execution_possible': False,
                   'attempt_ledger_complete': True, 'completed': False, 'stop_reason': None,
                   'semantic_status': 'unscored', 'metric_effect': 'none'}

        def emit(event):
            ledger.write(json.dumps({'request_id': item['request_id'], **event}) + '\n')
            ledger.flush()
            os.fsync(ledger.fileno())
            if event['event'] == 'attempt_started':
                receipt['network_attempts'] += 1
            if event['event'] == 'post_may_start':
                receipt['potentially_billable_posts'] += 1

        try:
            with (run / 'responses.jsonl').open('x', encoding='utf-8') as out:
                questions = decode((reference / 'case-packet.json').read_bytes())['questions']
                for item in manifest['requests']:
                    validate(run, reference)
                    if receipt['network_attempts'] + policy.max_attempts > 144:
                        raise ValueError('Attempt budget exhausted')
                    receipt['attempted_requests'] += 1
                    result = sender(item['endpoint'], item['wire_json'].encode('utf-8'), key,
                                    live=True, policy=policy, emit=emit)
                    receipt['ambiguous_posts'] += result['ambiguous_posts']
                    receipt['duplicate_execution_possible'] |= result['duplicate_execution_possible']
                    raw = result.pop('body')
                    row = {'request_id': item['request_id'], **result, 'response': None}
                    stop = None
                    if result['status'] == 'http_response':
                        if result['http_status'] != 200:
                            row['status'] = 'http_error'  # Never retain arbitrary error bodies.
                        else:
                            try:
                                row['response'] = decode(raw)
                                if not isinstance(row['response'], dict):
                                    raise ValueError('Expected JSON object')
                                row['status'] = 'json_received'
                                receipt['received_json_responses'] += 1
                            except (ValueError, UnicodeError):
                                row['response'] = None
                                row['status'] = 'response_decode_error'
                    if row['status'] == 'json_received':
                        try:
                            parse_response(canonical(row['response']), provider=item['provider'],
                                           model=item['requested_model'], questions=questions)
                            receipt['native_valid_responses'] += 1
                        except (ValueError, TypeError, KeyError):
                            stop = 'native_contract_invalid'
                    else:
                        stop = row['status']
                    out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    out.flush()
                    os.fsync(out.fileno())
                    if stop:
                        receipt['stop_reason'] = stop
                        break
                validate(run, reference)
                receipt['completed'] = receipt['native_valid_responses'] == 48
        except BaseException as error:
            receipt['stop_reason'] = type(error).__name__
            receipt['attempt_ledger_complete'] = False
            receipt['ambiguous_posts'] = None
            receipt['duplicate_execution_possible'] = None
            raise
        finally:
            receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
            receipt['elapsed_seconds'] = round(time.monotonic() - started, 6)
            with (run / 'receipt.json').open('x', encoding='utf-8') as out:
                json.dump(receipt, out, indent=2)
                out.write('\n')
    return receipt


def inspect_results(run=RUN, reference=REFERENCE):
    """Decode raw evidence; no missing output is assumed to mean no POST."""
    manifest, policy, manifest_hash = validate(run, reference)
    questions = decode((reference / 'case-packet.json').read_bytes())['questions']
    expected = {r['request_id']: r for r in manifest['requests']}
    order = list(expected)
    events, rows, seen = {}, [], set()
    ledger_path = run / 'attempts.jsonl'
    for raw in ledger_path.read_bytes().splitlines() if ledger_path.exists() else []:
        event = decode(raw)
        rid, number = event['request_id'], event['attempt']
        if (rid not in expected or event['wire_sha256'] != expected[rid]['wire_sha256']
                or event['protocol'] != PROTOCOL or type(number) is not int
                or not 1 <= number <= policy.max_attempts):
            raise ValueError('Attempt not bound to frozen wire/protocol/budget')
        if (rid not in events and rid != order[len(events)]) or (rid in events and rid != list(events)[-1]):
            raise ValueError('Attempt order differs from frozen schedule')
        if rid not in events and events:
            previous = events[next(reversed(events))]
            last = previous[len(previous)].get('attempt_finished')
            if last is None or last['retry_scheduled']:
                raise ValueError('Next request started before prior attempt terminated')
        attempts = events.setdefault(rid, {})
        if event['event'] == 'attempt_started':
            if number != len(attempts) + 1 or (attempts and 'attempt_finished' not in attempts[number - 1]):
                raise ValueError('Non-sequential or duplicate attempt')
            if attempts and attempts[number - 1]['attempt_finished']['retry_scheduled'] is not True:
                raise ValueError('Retry was not scheduled')
            attempts[number] = {'attempt_started': event}
        elif event['event'] in ('post_may_start', 'attempt_finished'):
            if number not in attempts or event['event'] in attempts[number] or 'attempt_finished' in attempts[number]:
                raise ValueError('Unexpected attempt lifecycle event')
            attempts[number][event['event']] = event
            if event['event'] == 'attempt_finished':
                if (type(event['retry_scheduled']) is not bool
                        or event['post_may_have_been_sent'] is not ('post_may_start' in attempts[number])
                        or (number == policy.max_attempts and event['retry_scheduled'])):
                    raise ValueError('Invalid attempt termination')
        else:
            raise ValueError('Unknown attempt event')
    path = run / 'responses.jsonl'
    for raw in path.read_bytes().splitlines() if path.exists() else []:
        row = decode(raw)
        rid = row['request_id']
        if rid not in expected or rid in seen or row['wire_sha256'] != expected[rid]['wire_sha256']:
            raise ValueError('Duplicate, unexpected or stale result')
        if (row['protocol'] != PROTOCOL or canonical(row['policy']) != canonical(policy.receipt())
                or row['status'] not in {'json_received', 'http_error', 'response_decode_error',
                                         'transport_error', 'response_too_large'}
                or type(row['network_attempts']) is not int or not 1 <= row['network_attempts'] <= 3
                or any(type(row[name]) is not int or not 0 <= row[name] <= row['network_attempts']
                       for name in ('potentially_billable_posts', 'ambiguous_posts'))
                or type(row['duplicate_execution_possible']) is not bool
                or (row['status'] == 'json_received' and (row['http_status'] != 200 or not isinstance(row['response'], dict)))):
            raise ValueError('Malformed result protocol/status/attempt aggregates')
        seen.add(rid)
        attempts = events.get(rid, {})
        if attempts and all('attempt_finished' in a for a in attempts.values()):
            finished_attempts = [a['attempt_finished'] for a in attempts.values()]
            # The row's aggregates must agree with the durable event evidence.
            recorded_attempts = [{k: v for k, v in a.items()
                                  if k not in ('event', 'protocol', 'wire_sha256', 'recorded_at', 'request_id')}
                                 for a in finished_attempts]
            ambiguity = sum(a['status'] == 'transport_error' and a['post_may_have_been_sent'] for a in finished_attempts)
            posts = sum('post_may_start' in a for a in attempts.values())
            if (row['attempts'] != recorded_attempts or row['network_attempts'] != len(attempts)
                    or row['potentially_billable_posts'] != posts or row['ambiguous_posts'] != ambiguity
                    or row['duplicate_execution_possible'] is not (ambiguity > 0 and posts > 1)):
                raise ValueError('Result aggregates and durable attempt ledger disagree')
        request = expected[rid]
        result = {key: request[key] for key in ('request_id', 'provider', 'case_id', 'repeat')}
        result.update(transport_status=row['status'], native_status='not_evaluated', prediction=None,
                      ambiguous_posts=row.get('ambiguous_posts'),
                      duplicate_execution_possible=row.get('duplicate_execution_possible'),
                      usage=row['response'].get('usage') if isinstance(row.get('response'), dict) else None)
        if row['status'] == 'json_received':
            try:
                result['prediction'] = parse_response(canonical(row['response']), provider=request['provider'],
                                                     model=request['requested_model'], questions=questions)
                result['native_status'] = 'valid'
            except (ValueError, TypeError, KeyError):
                result['native_status'] = 'invalid'
        rows.append(result)
    starts = sum(len(a) for a in events.values())
    posts = sum('post_may_start' in a for attempts in events.values() for a in attempts.values())
    finished = all('attempt_finished' in a for attempts in events.values() for a in attempts.values())
    receipt_path = run / 'receipt.json'
    receipt = decode(receipt_path.read_bytes()) if receipt_path.exists() else None
    complete = False
    if receipt is not None:
        if (receipt['manifest_sha256'] != manifest_hash or receipt['study'] != STUDY
                or receipt['protocol'] != PROTOCOL or receipt['planned_requests'] != 48
                or receipt['max_network_attempts'] != 144
                or type(receipt['completed']) is not bool or type(receipt['attempt_ledger_complete']) is not bool):
            raise ValueError('Receipt not bound to manifest')
        complete = ledger_path.exists() and receipt.get('attempt_ledger_complete') is True
        if complete and (not finished or receipt['network_attempts'] != starts
                         or receipt['attempted_requests'] != len(events)
                         or receipt['potentially_billable_posts'] != posts or seen != set(events)
                         or any(a[len(a)]['attempt_finished']['retry_scheduled'] for a in events.values())
                         or receipt['received_json_responses'] != sum(r['transport_status'] == 'json_received' for r in rows)
                         or receipt['native_valid_responses'] != sum(r['native_status'] == 'valid' for r in rows)
                         or receipt['ambiguous_posts'] != sum(r['ambiguous_posts'] for r in rows)
                         or receipt['duplicate_execution_possible'] is not any(r['duplicate_execution_possible'] for r in rows)):
            raise ValueError('Complete receipt and attempt ledger disagree')
    attempted = set(events) | seen
    missing = [rid for rid in expected if rid not in seen]
    return {'planned_requests': 48, 'received_rows': len(rows),
            'native_valid': sum(r['native_status'] == 'valid' for r in rows),
            'native_invalid': sum(r['native_status'] == 'invalid' for r in rows), 'rows': rows,
            'missing_result_request_ids': missing,
            'attempted_without_result_request_ids': [rid for rid in missing if rid in attempted],
            'unattempted_request_ids': [rid for rid in missing if rid not in attempted] if complete else [],
            'attempt_status_unknown_request_ids': [rid for rid in missing if rid not in attempted] if not complete else [],
            'attempt_ledger_complete': complete, 'receipt': receipt,
            'operationally_complete': (complete and len(rows) == 48
                and all(r['native_status'] == 'valid' and r['ambiguous_posts'] == 0
                        and r['duplicate_execution_possible'] is False for r in rows)
                and receipt.get('completed') is True),
            'metric_effect': 'none', 'semantic_status': 'unscored'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare', action='store_true', help='Create a NEW native manifest offline')
    modes.add_argument('--live', action='store_true', help='Explicit opt-in: 48 requests / at most 144 attempts')
    modes.add_argument('--inspect-results', action='store_true', help='Offline strict native decoding')
    args = parser.parse_args()
    if args.prepare:
        manifest = build()
        args.run.mkdir(parents=True, exist_ok=False)
        with (args.run / 'manifest.json').open('x', encoding='utf-8') as out:
            json.dump(manifest, out, ensure_ascii=False, indent=2)
            out.write('\n')
    result = inspect_results(args.run) if args.inspect_results else execute(args.run, live=args.live)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
