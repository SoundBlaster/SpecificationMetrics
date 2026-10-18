"""Frozen v1 ledger checks specialized for the instruction-only experiment.

Copied from verify_paired_retrieval_transport_v1 without changing old producers.
The shared-runner refactor remains deferred until the diagnostic is assessed.
"""
import argparse
import base64
import json
import math
import re
from pathlib import Path

import coreinfra_retry_run as transport
from coreinfra_transport import PROTOCOL, RetryPolicy
from instruction_parity_v1 import STUDY, source_digests, check_run, adapt_request
from retrieval_fact_adapter_v1 import producer_digests as adapter_inventory
from retrieval_index_v1.source import encoded


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect(preparation, run):
    manifest = check_run(preparation, run)
    expected_manifest = (preparation / 'manifest.json').read_bytes()
    require((run / 'manifest.json').read_bytes() == expected_manifest, 'execution manifest differs')
    names = (*transport.OUTPUTS, 'execution-binding.json')
    present = {name: (run / name).read_bytes() for name in names if (run / name).is_file()}
    if set(present) != set(names):
        return dict(study=STUDY, status='incomplete_transport_evidence', transport_verified=False,
                    missing_files=sorted(set(names) - present.keys()), pairs=[], semantic_status='unscored')
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
    if receipt['completed'] is not True or receipt['attempt_ledger_complete'] is not True:
        return dict(study=STUDY, status='incomplete_transport_evidence', transport_verified=False,
                    stop_reason=receipt['stop_reason'], pairs=[], semantic_status='unscored')
    requests = manifest['requests']
    rows = [transport.decode(line) for line in present['responses.jsonl'].splitlines()]
    events = [transport.decode(line) for line in present['attempts.jsonl'].splitlines()]
    require(len(rows) == len(requests), 'complete receipt has missing or extra response rows')
    policy = RetryPolicy(**manifest['retry_policy'])
    position, starts, posts, ambiguous, duplicate = 0, 0, 0, 0, False
    adaptations = []
    for request, row in zip(requests, rows):
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
        adapted = adapt_request(request, raw)
        adapted.update(transport_verified=True, attribution='verified_local_transport_record',
                       request_id=request['request_id'], case_id=request['case_id'], arm=request['arm'],
                       execution_binding_sha256=transport.sha(present['execution-binding.json']))
        adaptations.append(adapted)
        starts += len(attempts)
        posts += request_posts
        ambiguous += request_ambiguous
        duplicate |= row['duplicate_execution_possible']
    require(position == len(events) and starts <= manifest['max_network_attempts'], 'extra or over-budget events')
    for name, count in dict(network_attempts=starts, attempted_requests=len(requests),
                            received_json_responses=len(rows), potentially_billable_posts=posts,
                            ambiguous_posts=ambiguous).items():
        require(type(receipt[name]) is int and receipt[name] == count, 'receipt counter differs: ' + name)
    require(receipt['duplicate_execution_possible'] is duplicate and receipt['stop_reason'] is None,
            'receipt completion differs')
    pairs = []
    for case_id in dict.fromkeys(r['case_id'] for r in requests):
        for provider in context_providers(requests):
            selected = {a['arm']: a for a in adaptations if a['case_id'] == case_id and a['provider'] == provider}
            require(set(selected) == {'baseline', 'retrieval'}, 'missing pair member')
            pairs.append(dict(case_id=case_id, provider=provider,
                statuses={arm: a['status'] for arm, a in selected.items()},
                changed_labels=(selected['baseline']['prediction']['labels'] != selected['retrieval']['prediction']['labels']
                                if all(a['prediction'] is not None for a in selected.values()) else None),
                semantic_status='unscored_pending_independent_reference'))
    return dict(study=STUDY, status='complete_local_transport_evidence', transport_verified=True,
                verification_scope='local_manifest_ledger_receipt_body_consistency_not_remote_attestation',
                operationally_complete=not duplicate and ambiguous == 0,
                native_contract_valid=all(a['native_status'] == 'valid' for a in adaptations),
                raw_file_sha256={n: transport.sha(raw) for n, raw in present.items()},
                analysis_runtime_inventory=adaptations[0]['adapter_producer_sha256'],
                recorded_execution_runtime_inventory=binding['adapter_runtime_inventory'],
                analysis_runtime_matches_execution=current_runtime == runtime,
                rows=adaptations, pairs=pairs, semantic_status='unscored_pending_independent_reference',
                metric_effect='none')


def context_providers(requests):
    return list(dict.fromkeys(r['provider'] for r in requests))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.preparation, args.run)
    with args.output.open('x') as stream:
        stream.write(encoded(report) + '\n')
    print(json.dumps(dict(status=report['status'], transport_verified=report['transport_verified'])))


if __name__ == '__main__':
    main()
