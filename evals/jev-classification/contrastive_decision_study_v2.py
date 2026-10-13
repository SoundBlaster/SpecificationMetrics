#!/usr/bin/env python3
"""Contrastive v2: warn on bounded Jev mass drift; offline unless --live."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from contrastive_decision_study import (OUTPUTS, REFERENCE, ROOT,
                                       PRODUCERS as V1_PRODUCERS, build as build_v1,
                                       load_reference)
from coreinfra_retry_run import decode
from coreinfra_transport import PROTOCOL, RetryPolicy, post
from decision_choice_contract_v2 import POLICY, evaluate_response
from question_grouping import canonical, digest

STUDY = 'contrastive_mechanics_policy_native/v2'
PRODUCERS = V1_PRODUCERS + ('contrastive_decision_study_v2.py',
                          'decision_choice_contract_v2.py', 'score_contrastive_decisions_v2.py')


def build(reference=REFERENCE):
    manifest = build_v1(reference)
    manifest.update(study=STUDY, acceptance_policy={
        'id': POLICY, 'provider': 'jev-coreinfra', 'model': 'jev-1.13.0',
        'option_counts': [3, 4], 'strict_absolute_tolerance': '0.000001',
        'warning_absolute_allowance': '0.01', 'arithmetic': 'decimal_from_returned_numbers',
        'probability_transform': 'none', 'confidence_transform': 'none',
        'invalid_answer': 'retain_unavailable_continue',
        'identity_failure': 'retain_unavailable_stop',
        'transport_failure': 'retain_failure_stop',
        'completion': 'all_48_result_rows_separate_from_usable_coverage',
        'H3_precision_assumption': 'Jev nearest-hundredth intervals; not a provider guarantee',
    }, producer_digests={name: digest((ROOT / name).read_bytes()) for name in PRODUCERS})
    manifest['criteria'] = dict(manifest['criteria'])
    manifest['criteria']['H3_pass'] = ('At least 3/4 pairs in each repeat have both positive deltas; '
        'for Jev require positive lower endpoints under nearest-hundredth sensitivity. '
        'Raw-positive pairs whose intervals include zero are unresolved, not positive evidence.')
    return manifest


def validate(run, reference=REFERENCE):
    raw = (run / 'manifest.json').read_bytes()
    manifest = decode(raw)
    if canonical(manifest) != canonical(build(reference)):
        raise ValueError('Frozen v2 manifest differs from current inputs/producers/policy')
    return manifest, RetryPolicy(**manifest['retry_policy']), digest(raw)


def execute(run, *, live=False, reference=REFERENCE, sender=post):
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
                   'native_invalid_responses': 0, 'warned_responses': 0, 'acceptance_policy': POLICY,
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
                    row['validation'] = {'policy': POLICY, 'status': 'not_evaluated',
                                         'warnings': [], 'rejection_code': None}
                    if row['status'] == 'json_received':
                        _, metadata, identity_error = evaluate_response(canonical(row['response']),
                            provider=item['provider'], model=item['requested_model'], questions=questions)
                        row['validation'] = metadata
                        if metadata['status'] == 'valid':
                            receipt['native_valid_responses'] += 1
                            receipt['warned_responses'] += bool(metadata['warnings'])
                        else:
                            receipt['native_invalid_responses'] += 1
                        if identity_error:
                            stop = 'native_identity_error'
                    else:
                        stop = row['status']
                    out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    out.flush()
                    os.fsync(out.fileno())
                    if stop:
                        receipt['stop_reason'] = stop
                        break
                validate(run, reference)
                receipt['completed'] = receipt['attempted_requests'] == 48 and receipt['stop_reason'] is None
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


def inspect_results(run, reference=REFERENCE):
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
        if (rid not in expected or rid in seen or rid != order[len(seen)]
                or row['wire_sha256'] != expected[rid]['wire_sha256']):
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
        metadata = {'policy': POLICY, 'status': 'not_evaluated', 'warnings': [], 'rejection_code': None}
        identity_error = False
        if row['status'] == 'json_received':
            result['prediction'], metadata, identity_error = evaluate_response(canonical(row['response']),
                provider=request['provider'], model=request['requested_model'], questions=questions)
        if canonical(row.get('validation')) != canonical(metadata):
            raise ValueError('Saved validation differs from raw response replay')
        result.update(native_status=metadata['status'], warnings=metadata['warnings'],
                      rejection_code=metadata['rejection_code'], identity_error=identity_error)
        if rows and (rows[-1]['identity_error'] or rows[-1]['transport_status'] != 'json_received'):
            raise ValueError('Result follows a fatal identity/transport error')
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
                or receipt['acceptance_policy'] != POLICY
                or type(receipt['completed']) is not bool or type(receipt['attempt_ledger_complete']) is not bool):
            raise ValueError('Receipt not bound to manifest')
        counters = ('network_attempts', 'attempted_requests', 'potentially_billable_posts',
                    'received_json_responses', 'native_valid_responses', 'native_invalid_responses',
                    'warned_responses')
        if any(type(receipt[k]) is not int or receipt[k] < 0 for k in counters):
            raise ValueError('Invalid receipt counters')
        complete = ledger_path.exists() and receipt.get('attempt_ledger_complete') is True
        if complete:
            terminal = rows[-1] if rows else None
            expected_stop = ('native_identity_error' if terminal and terminal['identity_error']
                             else terminal['transport_status'] if terminal and terminal['transport_status'] != 'json_received'
                             else None)
            if (receipt['stop_reason'] != expected_stop
                    or receipt['completed'] is not (len(rows) == 48 and expected_stop is None)
                    or (len(rows) < 48 and expected_stop is None)):
                raise ValueError('Receipt completion/stop differs from result lifecycle')
        if complete and (not finished or receipt['network_attempts'] != starts
                         or receipt['attempted_requests'] != len(events)
                         or receipt['potentially_billable_posts'] != posts or seen != set(events)
                         or any(a[len(a)]['attempt_finished']['retry_scheduled'] for a in events.values())
                         or receipt['received_json_responses'] != sum(r['transport_status'] == 'json_received' for r in rows)
                         or receipt['native_valid_responses'] != sum(r['native_status'] == 'valid' for r in rows)
                         or receipt['native_invalid_responses'] != sum(r['native_status'] == 'invalid' for r in rows)
                         or receipt['warned_responses'] != sum(bool(r['warnings']) for r in rows)
                         or receipt['ambiguous_posts'] != sum(r['ambiguous_posts'] for r in rows)
                         or receipt['duplicate_execution_possible'] is not any(r['duplicate_execution_possible'] for r in rows)):
            raise ValueError('Complete receipt and attempt ledger disagree')
    if starts > 144 or len(events) > 48:
        raise ValueError('Attempt ledger exceeds frozen budget')
    attempted = set(events) | seen
    missing = [rid for rid in expected if rid not in seen]
    return {'planned_requests': 48, 'received_rows': len(rows),
            'native_valid': sum(r['native_status'] == 'valid' for r in rows),
            'native_invalid': sum(r['native_status'] == 'invalid' for r in rows), 'rows': rows,
            'warned_responses': sum(bool(r['warnings']) for r in rows), 'acceptance_policy': POLICY,
            'execution_complete': complete and receipt.get('completed') is True,
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
    parser.add_argument('--run', type=Path, help='New v2 run directory; never the spent v1 directory')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare', action='store_true', help='Freeze a NEW v2 manifest offline')
    modes.add_argument('--live', action='store_true', help='Explicit opt-in: 48 requests / at most 144 attempts')
    modes.add_argument('--inspect-results', action='store_true', help='Replay raw v2 evidence offline')
    args = parser.parse_args()
    if (args.prepare or args.live or args.inspect_results) and args.run is None:
        parser.error('--run is required for prepare/live/inspect-results')
    if args.prepare:
        manifest = build()
        args.run.mkdir(parents=True, exist_ok=False)
        with (args.run / 'manifest.json').open('x', encoding='utf-8') as out:
            json.dump(manifest, out, ensure_ascii=False, indent=2)
            out.write('\n')
    if args.run is None:
        manifest = build()
        result = {'validated_inputs': True, 'manifest_frozen': False, 'study': STUDY,
                  'acceptance_policy': manifest['acceptance_policy'], 'planned_requests': 48,
                  'max_network_attempts': 144, 'inference': False, 'metric_effect': 'none'}
    else:
        result = inspect_results(args.run) if args.inspect_results else execute(args.run, live=args.live)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
