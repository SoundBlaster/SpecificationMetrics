"""Offline replay of this completed, single-attempt-per-request smoke only."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parent
ROOT = RUN.parent.parent
sys.path.insert(0, str(ROOT))
import prepare_intent_first_native as preparation


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def analyze():
    names = ('manifest.json', 'receipt.json', 'responses.jsonl', 'attempts.jsonl',
             'native-report.json', 'authorization.json')
    snapshot = {name: (RUN / name).read_bytes() for name in names}
    manifest, receipt = (json.loads(snapshot[n]) for n in names[:2])
    rows = [json.loads(line) for line in snapshot['responses.jsonl'].splitlines()]
    events = [json.loads(line) for line in snapshot['attempts.jsonl'].splitlines()]
    report = preparation.inspect(RUN)
    require(report == json.loads(snapshot['native-report.json']), 'native report replay differs')
    require(report['response_file_sha256'] == sha(snapshot['responses.jsonl']), 'response snapshot differs')
    require(snapshot['manifest.json'] == preparation.verify()['manifest.json'], 'manifest differs')
    require(receipt['manifest_sha256'] == sha(snapshot['manifest.json']), 'receipt manifest differs')
    require(receipt['producer_digests'] == manifest['producer_digests'], 'producer binding differs')
    require(receipt['retry_policy'] == manifest['retry_policy'], 'retry policy differs')
    expected_ids = [r['request_id'] for r in manifest['requests']]
    require(len(expected_ids) == len(set(expected_ids)) == 8, 'request coverage differs')
    require([r['request_id'] for r in rows] == expected_ids, 'response order/coverage differs')
    require(len(events) == 24, 'expected exactly eight three-event groups')
    protocol = manifest['protocol']
    provider_totals, observations = {}, []
    for index, (request, row, native) in enumerate(zip(manifest['requests'], rows, report['rows'])):
        group = events[index * 3:index * 3 + 3]
        require([e['event'] for e in group] == ['attempt_started', 'post_may_start', 'attempt_finished'],
                'attempt lifecycle differs')
        for event in group:
            require(event['request_id'] == request['request_id'] and event['attempt'] == 1
                    and event['protocol'] == protocol and event['wire_sha256'] == request['wire_sha256'],
                    'event identity/attempt differs')
        finished = group[-1]
        excluded = {'event', 'protocol', 'wire_sha256', 'recorded_at', 'request_id'}
        require(row['attempts'] == [{k: v for k, v in finished.items() if k not in excluded}],
                'finished event differs from response attempt')
        require(row['policy'] == dict(manifest['retry_policy'], protocol=protocol), 'row policy differs')
        require(finished['http_status'] == 200 and finished['status'] == 'http_response'
                and finished['post_may_have_been_sent'] is True
                and finished['retry_scheduled'] is False and finished['backoff_seconds'] == 0,
                'not the observed one-attempt HTTP success')
        require(row['network_attempts'] == row['potentially_billable_posts'] == 1
                and row['ambiguous_posts'] == 0 and row['duplicate_execution_possible'] is False
                and row['status'] == 'json_received' and row['semantic_status'] == 'unscored',
                'row accounting differs')
        require(native['native_status'] == 'valid', 'unexpected native failure')
        prediction = native['prediction']
        provider = request['provider']
        totals = provider_totals.setdefault(provider, dict(requests=0, consistent_tuples=0,
                                                         input_tokens=0, output_tokens=0))
        totals['requests'] += 1
        totals['consistent_tuples'] += int(prediction['tuple_consistent'])
        usage = row['response']['usage']
        for field in ('input_tokens', 'output_tokens'):
            totals[field] += usage[field]
        observations.append(dict(request_id=request['request_id'], provider=provider,
                                 labels=prediction['labels'], violations=prediction['tuple_violations'],
                                 probability_mass_warnings=prediction['warnings'],
                                 elapsed_seconds=finished['elapsed_seconds'], reported_usage=usage))
    expected_receipt = dict(protocol=protocol, planned_requests=8, max_network_attempts=24,
                            attempted_requests=8, received_json_responses=8, network_attempts=8,
                            potentially_billable_posts=8, ambiguous_posts=0,
                            duplicate_execution_possible=False, attempt_ledger_complete=True,
                            completed=True, stop_reason=None, semantic_status='unscored')
    require(all(receipt.get(k) == v for k, v in expected_receipt.items()), 'receipt accounting differs')
    elapsed = (datetime.fromisoformat(receipt['finished_at']) -
               datetime.fromisoformat(receipt['started_at'])).total_seconds()
    # These are recorded local lifecycle checks, not provider execution/billing attestation.
    for name, value in snapshot.items():
        require((RUN / name).read_bytes() == value, 'artifact changed during replay: ' + name)
    return dict(status='offline_replay_verified_not_semantically_scored',
                source_sha256={n: sha(v) for n, v in snapshot.items()},
                analyzer_sha256=sha(Path(__file__).read_bytes()),
                local_ledger_response_receipt_associations_verified=True,
                independent_provider_execution_or_billing_attestation=False,
                planned_requests=8, received_responses=8, network_attempts=8, tls_retries=0,
                native_valid=8, consistent_tuples=sum(t['consistent_tuples'] for t in provider_totals.values()),
                elapsed_wall_seconds=elapsed, provider_reported_usage=provider_totals,
                rows=observations, semantic_accuracy=None, full_v4_1_annotation=False,
                provider_scoring_enabled=False, metric_effect='none')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='create analysis.json exclusively')
    args = parser.parse_args()
    result = encoded(analyze())
    if args.write:
        with (RUN / 'analysis.json').open('xb') as stream:
            stream.write(result)
    else:
        require((RUN / 'analysis.json').read_bytes() == result, 'analysis replay differs')
        inventory = (RUN / 'SHA256SUMS').read_text().splitlines()
        listed = {}
        for line in inventory:
            digest, name = line.split('  ', 1)
            require(name == Path(name).name and name not in listed, 'invalid inventory entry')
            listed[name] = digest
        require(set(listed) == {p.name for p in RUN.iterdir() if p.is_file()} - {'SHA256SUMS'},
                'inventory coverage differs')
        require(all(sha((RUN / name).read_bytes()) == digest for name, digest in listed.items()),
                'inventory hash differs')
    print('Verified offline: 8 responses, 8 native-valid, 4 consistent tuples; no inference/scoring.')


if __name__ == '__main__':
    main()
