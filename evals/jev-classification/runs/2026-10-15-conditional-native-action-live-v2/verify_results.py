"""Replay this completed 18-response run offline; never request inference."""
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
import conditional_native_action_v2 as prep

require = prep.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compare(rows):
    """Apply preregistered H1/H2 criteria; echo compliance is not accuracy."""
    output = {}
    for provider in prep.old.native.PROVIDERS:
        selected = [r for r in rows if r['provider'] == provider]
        index = {(r['case_id'], r['arm']): r for r in selected}
        require(len(index) == len(selected), 'duplicate case/arm in comparison')
        baseline = [r for r in selected if r['arm'] == 'baseline']
        conditioned = [r for r in selected if r['arm'] == 'conditioned']
        complete = (len(baseline) == len(conditioned) == 4
                    and {r['case_id'] for r in baseline} == {r['case_id'] for r in conditioned}
                    and all(r['native_status'] == 'valid' for r in baseline + conditioned))
        def action(case, arm):
            row = index.get((case, arm))
            return row['prediction']['labels']['recommendation'] if row and row['native_status'] == 'valid' else None
        counts = {}
        for arm, group in (('baseline', baseline), ('conditioned', conditioned)):
            valid = [r for r in group if r['native_status'] == 'valid']
            counts[arm] = dict(observed=len(group), native_valid=len(valid),
                               consistent_returned_tuples=sum(r['prediction']['tuple_consistent'] for r in valid),
                               actions_violating_common_premises=sum(bool(r['action_violations_against_development_premises'])
                                                                     for r in valid),
                               premise_echo_matches=(sum(r['premise_echo_matches'] is True for r in valid)
                                                     if arm == 'conditioned' else None))
        new_yaml = (action('target-04-cell01', 'conditioned') == 'formalize'
                    and action('target-04-cell01', 'baseline') != 'formalize')
        lost_gate = (action('target-02-cell01', 'baseline') == 'formalize'
                     and action('target-02-cell01', 'conditioned') != 'formalize')
        if not complete:
            h1 = 'incomplete_not_evaluable'
        elif counts['conditioned']['premise_echo_matches'] != 4:
            h1 = 'not_supported_premise_echo_failed'
        elif new_yaml or lost_gate:
            h1 = 'not_supported_control_regression'
        elif (counts['conditioned']['actions_violating_common_premises'] <
              counts['baseline']['actions_violating_common_premises']):
            h1 = 'supported_in_this_batch'
        else:
            h1 = 'not_supported_no_strict_improvement'
        pair = [index.get((prep.old.BDD, arm)) for arm in ('conditioned', 'ownership_witness')]
        if not all(r and r['native_status'] == 'valid' and r['premise_echo_matches'] is True for r in pair):
            h2 = 'incomplete_or_premise_failure_not_evaluable'
        else:
            before, after = (r['prediction']['labels']['recommendation'] == 'reuse_specification' for r in pair)
            h2 = ('no_incremental_evidence_already_reused' if before and after else
                  'supported_in_single_pair' if after else
                  'regression_in_single_pair' if before else 'not_supported_in_single_pair')
        output[provider] = dict(counts=counts, H1=h1, H2=h2,
                                controls=dict(new_yaml_formalization=new_yaml, lost_gate_formalization=lost_gate),
                                bdd_actions={arm: action(prep.old.BDD, arm) for arm in prep.old.ARMS})
    return output


def analyze():
    names = ('manifest.json', 'responses.jsonl', 'attempts.jsonl', 'receipt.json',
             'authorization.json', 'native-report.json')
    data = {n: (RUN / n).read_bytes() for n in names}
    manifest, receipt, authorization = (json.loads(data[n]) for n in ('manifest.json', 'receipt.json', 'authorization.json'))
    require(data['manifest.json'] == prep.verify()['manifest.json'], 'execution manifest differs')
    require(receipt['manifest_sha256'] == sha(data['manifest.json']), 'receipt manifest hash differs')
    require(receipt['protocol'] == manifest['protocol'], 'receipt protocol differs')
    require(receipt['producer_digests'] == manifest['producer_digests']
            and receipt['retry_policy'] == manifest['retry_policy'], 'receipt producer/policy differs')
    require(authorization['logical_requests'] == 18 and authorization['max_network_attempts'] == 54,
            'authorization budget differs')
    require(datetime.fromisoformat(authorization['recorded_at_utc']) <= datetime.fromisoformat(receipt['started_at']),
            'authorization was not recorded before execution')
    report = prep.inspect(RUN)
    require(report == json.loads(data['native-report.json'])
            and report['response_file_sha256'] == sha(data['responses.jsonl']), 'native report snapshot/replay differs')
    rows = [json.loads(line) for line in data['responses.jsonl'].splitlines()]
    events = [json.loads(line) for line in data['attempts.jsonl'].splitlines()]
    require(len(rows) == len(manifest['requests']) == 18 and len(events) == 54, 'completed run coverage differs')
    require([r['request_id'] for r in rows] == [r['request_id'] for r in manifest['requests']], 'response coverage/order differs')
    require(all(r['native_status'] == 'valid' for r in report['rows']), 'observed native validity differs')
    usage = {}
    for i, (request, row) in enumerate(zip(manifest['requests'], rows)):
        group = events[i * 3:i * 3 + 3]
        require([e['event'] for e in group] == ['attempt_started', 'post_may_start', 'attempt_finished'],
                'expected one complete successful attempt lifecycle')
        for event in group:
            require(event['request_id'] == request['request_id'] and event['attempt'] == 1
                    and event['protocol'] == manifest['protocol'] and event['wire_sha256'] == request['wire_sha256'],
                    'event identity differs')
        finished = group[-1]
        excluded = {'event', 'protocol', 'wire_sha256', 'recorded_at', 'request_id'}
        require(row['attempts'] == [{k: v for k, v in finished.items() if k not in excluded}], 'event/response attempt differs')
        require(finished['http_status'] == 200 and finished['status'] == 'http_response'
                and finished['post_may_have_been_sent'] is True and finished['retry_scheduled'] is False
                and finished['backoff_seconds'] == 0, 'observed successful attempt differs')
        require(row['policy'] == dict(manifest['retry_policy'], protocol=manifest['protocol'])
                and row['status'] == 'json_received' and row['http_status'] == 200
                and row['network_attempts'] == row['potentially_billable_posts'] == 1
                and row['ambiguous_posts'] == 0 and row['duplicate_execution_possible'] is False
                and row['semantic_status'] == 'unscored',
                'response accounting differs')
        totals = usage.setdefault(request['provider'], dict(input_tokens=0, output_tokens=0))
        for field in totals:
            totals[field] += row['response']['usage'][field]
    expected_receipt = dict(planned_requests=18, max_network_attempts=54, attempted_requests=18,
                            received_json_responses=18, network_attempts=18, potentially_billable_posts=18,
                            ambiguous_posts=0, duplicate_execution_possible=False, attempt_ledger_complete=True,
                            completed=True, stop_reason=None, semantic_status='unscored')
    require(all(receipt.get(k) == v for k, v in expected_receipt.items()), 'receipt completion/accounting differs')
    for name, raw in data.items():
        require((RUN / name).read_bytes() == raw, 'artifact changed during replay')
    return dict(study=prep.STUDY, status='completed_local_evidence_verified_not_accuracy_scored',
                source_sha256={n: sha(raw) for n, raw in data.items()}, analyzer_sha256=sha(Path(__file__).read_bytes()),
                local_ledger_response_receipt_associations_verified=True,
                independent_provider_execution_or_billing_attestation=False,
                received=18, network_attempts=18, tls_retries=0, native_valid=18,
                consistent_returned_tuples=sum(r['prediction']['tuple_consistent'] for r in report['rows']),
                mass_warnings=sum(len(r['prediction']['warnings']) for r in report['rows']),
                wall_seconds=(datetime.fromisoformat(receipt['finished_at'])-
                              datetime.fromisoformat(receipt['started_at'])).total_seconds(),
                provider_reported_usage=usage, comparisons=compare(report['rows']),
                semantic_accuracy=None, provider_scoring_enabled=False, full_v4_1_annotation=False, metric_effect='none')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    value = prep.encoded(analyze())
    if args.write:
        with (RUN / 'analysis.json').open('xb') as stream:
            stream.write(value)
    else:
        require((RUN / 'analysis.json').read_bytes() == value, 'analysis replay differs')
        inventory = {}
        for line in (RUN / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            require(name == Path(name).name and name not in inventory, 'invalid inventory')
            inventory[name] = digest
        require(set(inventory) == {p.name for p in RUN.iterdir() if p.is_file()} - {'SHA256SUMS'}, 'inventory coverage differs')
        require(all(sha((RUN / name).read_bytes()) == digest for name, digest in inventory.items()), 'inventory hash differs')
    print('Offline replay verified: 18 responses/attempts, unchanged preregistered comparisons; no inference.')


if __name__ == '__main__':
    main()
