"""Preserve verified completed prefixes without qualifying an incomplete cohort."""
import base64
import math
import re

import coreinfra_retry_run as transport
from coreinfra_transport import PROTOCOL, RetryPolicy
from paired_retrieval_study_v1 import STUDY, source_digests, verify
from retrieval_fact_adapter_v1 import adapt_response, producer_digests as adapter_inventory
from retrieval_index_v1.source import encoded


def require(condition, message):
    if not condition:
        raise ValueError(message)


from verify_paired_retrieval_transport_v1 import inspect as inspect_complete


def read_prefix(raw):
    """Keep complete JSON records; only an unterminated final fragment is diagnostic."""
    rows = []
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            value = transport.decode(line)
        except (ValueError, UnicodeError, RecursionError):
            if index == len(lines) - 1 and not line.endswith(b'\n'):
                return rows, dict(status='truncated_final_record', line=index + 1,
                                  bytes=len(line), sha256=transport.sha(line))
            raise ValueError('invalid interior or terminated JSONL record') from None
        require(isinstance(value, dict), 'JSONL record must be an object')
        rows.append(value)
    return rows, None


def inspect(preparation, run):
    manifest = verify(preparation)
    expected_manifest = (preparation / 'manifest.json').read_bytes()
    require((run / 'manifest.json').read_bytes() == expected_manifest, 'execution manifest differs')
    names = (*transport.OUTPUTS, 'execution-binding.json')
    present = {name: (run / name).read_bytes() for name in names if (run / name).is_file()}
    if set(present) != set(names):
        return dict(study=STUDY, status='incomplete_transport_evidence', transport_verified=False,
                    missing_files=sorted(set(names) - present.keys()), rows=[], pairs=[], semantic_status='unscored')
    binding = transport.decode(present['execution-binding.json'])
    runtime = binding.get('adapter_runtime_inventory')
    current_runtime = adapter_inventory()
    require(binding['study'] == STUDY and binding['manifest_sha256'] == transport.sha(expected_manifest)
            and binding['status'] == 'local_execution_snapshot_not_remote_attestation'
            and binding['producers_unchanged'] is True
            and binding['study_source_digests'] == source_digests()
            and isinstance(runtime, dict) and bool(runtime)
            and all(isinstance(k, str) and isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v)
                    for k, v in runtime.items())
            and {k: v for k, v in runtime.items() if not k.startswith('@')} ==
                {k: v for k, v in current_runtime.items() if not k.startswith('@')}
            and '@runtime/python' in runtime
            and all(k in runtime for k in current_runtime if k.startswith('@distribution/')),
            'execution binding differs')
    require(binding['file_sha256'] == {n: transport.sha(present[n]) for n in transport.OUTPUTS},
            'execution body/receipt/ledger checksum differs')
    receipt = transport.decode(present['receipt.json'])
    require(receipt['manifest_sha256'] == transport.sha(expected_manifest)
            and receipt['protocol'] == PROTOCOL and receipt['semantic_status'] == 'unscored'
            and receipt['producer_digests'] == manifest['producer_digests']
            and receipt['retry_policy'] == manifest['retry_policy']
            and type(receipt['planned_requests']) is int and receipt['planned_requests'] == manifest['planned_requests']
            and type(receipt['max_network_attempts']) is int
            and receipt['max_network_attempts'] == manifest['max_network_attempts'], 'receipt identity differs')
    if receipt['completed'] is True and receipt['attempt_ledger_complete'] is True:
        return inspect_complete(preparation, run)
    requests = manifest['requests']
    rows, response_tail = read_prefix(present['responses.jsonl'])
    events, ledger_tail = read_prefix(present['attempts.jsonl'])
    require(len(rows) <= len(requests), 'extra response rows')
    policy = RetryPolicy(**manifest['retry_policy'])
    position, starts, posts, ambiguous, duplicate = 0, 0, 0, 0, False
    adaptations = []
    prefix_stop = None
    for index, (request, row) in enumerate(zip(requests, rows)):
        before = position
        if row.get('status') != 'json_received' or row.get('http_status') != 200:
            prefix_stop = dict(index=index, reason='request_not_successful')
            break
        try:
            require(row['request_id'] == request['request_id'] and row['wire_sha256'] == request['wire_sha256']
                    and row['protocol'] == PROTOCOL and row['policy'] == transport.decode(encoded(policy.receipt()))
                    and row['status'] == 'json_received' and row['http_status'] == 200,
                    'response is not bound to scheduled successful request')
            attempts = []
            request_posts, request_ambiguous = 0, 0
            while True:
                require(position < len(events), 'attempt ledger is incomplete')
                start = events[position]
                position += 1
                number = len(attempts) + 1
                require(start['event'] == 'attempt_started' and type(start['attempt']) is int
                        and start['attempt'] == number and number <= policy.max_attempts, 'invalid attempt start')
                group = [start]
                require(position < len(events), 'missing attempt termination')
                sent = events[position]['event'] == 'post_may_start'
                if sent:
                    group.append(events[position])
                    position += 1
                require(position < len(events), 'missing attempt termination')
                finish = events[position]
                group.append(finish)
                position += 1
                require(all(e['request_id'] == request['request_id'] and e['wire_sha256'] == request['wire_sha256']
                            and e['protocol'] == PROTOCOL and type(e['attempt']) is int
                            and e['attempt'] == number for e in group), 'attempt identity differs')
                require(finish['event'] == 'attempt_finished' and type(finish['retry_scheduled']) is bool
                        and finish['post_may_have_been_sent'] is sent, 'invalid attempt termination')
                require(type(finish['elapsed_seconds']) in (int, float) and math.isfinite(finish['elapsed_seconds'])
                        and finish['elapsed_seconds'] >= 0, 'invalid elapsed time')
                retry = finish['retry_scheduled']
                if retry:
                    require(number < policy.max_attempts and finish['status'] == 'transport_error'
                            and (finish.get('transient_tls') is True or finish.get('incomplete_http_body') is True)
                            and finish['http_status'] in (None, 200)
                            and finish['backoff_seconds'] == policy.backoff_seconds[number - 1], 'invalid retry')
                else:
                    require(finish['status'] == 'http_response' and finish['http_status'] == 200
                            and finish['backoff_seconds'] == 0 and sent, 'request did not terminate successfully')
                attempts.append({k: v for k, v in finish.items()
                                 if k not in ('event', 'protocol', 'wire_sha256', 'recorded_at', 'request_id')})
                request_posts += sent
                request_ambiguous += finish['status'] == 'transport_error' and sent
                if not retry:
                    break
            require(row['attempts'] == attempts and type(row['network_attempts']) is int
                    and row['network_attempts'] == len(attempts)
                    and type(row['potentially_billable_posts']) is int and row['potentially_billable_posts'] == request_posts
                    and type(row['ambiguous_posts']) is int and row['ambiguous_posts'] == request_ambiguous
                    and row['duplicate_execution_possible'] is (request_ambiguous > 0 and request_posts > 1),
                    'response aggregates differ from attempt ledger')
            try:
                raw = base64.b64decode(row['raw_body_base64'], validate=True)
            except (ValueError, TypeError):
                raise ValueError('invalid captured response body') from None
            require(len(raw) <= policy.max_response_bytes and transport.sha(raw) == row['raw_body_sha256']
                    and transport.decode(raw) == row['response'], 'captured response body differs')
            adapted = adapt_response(preparation / request['preparation'], request['provider'], raw)
            adapted.update(transport_verified=True, attribution='verified_local_completed_prefix',
                           request_id=request['request_id'], case_id=request['case_id'], arm=request['arm'],
                           execution_binding_sha256=transport.sha(present['execution-binding.json']))
            adaptations.append(adapted)
            starts += len(attempts)
            posts += request_posts
            ambiguous += request_ambiguous
            duplicate |= row['duplicate_execution_possible']
        except (ValueError, KeyError, TypeError, UnicodeError):
            position = before
            prefix_stop = dict(index=index, reason='completed_record_not_verifiable')
            break
    require(starts <= manifest['max_network_attempts'], 'prefix exceeds reserved attempts')
    bounds = dict(network_attempts=(starts, manifest['max_network_attempts']),
        attempted_requests=(len(adaptations), len(requests)),
        received_json_responses=(len(adaptations), len(requests)),
        potentially_billable_posts=(posts, manifest['max_network_attempts']))
    for name, (minimum, maximum) in bounds.items():
        require(type(receipt[name]) is int and minimum <= receipt[name] <= maximum,
                'receipt contradicts verified prefix: ' + name)
    return dict(study=STUDY, status='incomplete_transport_evidence', transport_verified=False,
        stop_reason=receipt['stop_reason'], operationally_complete=False, native_contract_valid=None,
        rows=adaptations, pairs=[], semantic_status='unscored_incomplete_execution', metric_effect='none',
        verification_scope='completed_prefix_local_ledger_and_body_not_complete_cohort',
        captured_complete_records=len(rows), response_tail=response_tail, ledger_tail=ledger_tail,
        prefix_stop=prefix_stop, verified_completed_prefix=len(adaptations))
