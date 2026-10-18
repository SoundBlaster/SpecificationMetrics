"""Compare captured Jev/Luna labels to the pinned Sol comparator, not semantic gold."""
import argparse
import json
from pathlib import Path

from coreinfra_retry_run import decode, sha
from paired_blind_reference_v1 import AXES, require
from paired_retrieval_execution_v1 import execute as execute_transport
from paired_retrieval_study_v1 import stage, verify as verify_preparation
from retrieval_fact_adapter_v1.dependencies import local_closure
from retrieval_index_v1.source import encoded
from sol_reference_repeatability_v1 import ROOT, RUN as SOL_RUN, verify as verify_sol
from verify_paired_retrieval_transport_v1 import inspect

CONTRACT = 'specmetrics.sol-top-line-comparison/v1'
PREPARATION = ROOT / 'runs/2026-10-18-paired-retrieval-preparation-v1'
FROZEN = ROOT / 'runs/2026-10-18-sol-top-line-comparison-contract-v1'
PRIMARY = ('concern_kind', 'ownership')


def policy():
    sol = verify_sol(SOL_RUN)
    manifest = verify_preparation(PREPARATION)
    require(sol['diagnostic']['primary_stable_in_pilot'] is True and not sol['consistency_review_tasks']
            and all(not v['needs_adjudication'] and all(v['labels'][a] is not None for a in AXES)
                    for v in sol['historical_comparison']), 'Sol comparator requires adjudication')
    return dict(contract=CONTRACT, status='frozen_before_provider_observations',
        manifest_sha256=sha((PREPARATION / 'manifest.json').read_bytes()),
        sol_top_line_sha256=sha((SOL_RUN / 'top-line.json').read_bytes()),
        sol_receipt_sha256=sha((SOL_RUN / 'receipt.json').read_bytes()),
        reference_authority='agreement_with_model_specific_comparator_not_semantic_accuracy',
        planned_requests=16, max_network_attempts=manifest['max_network_attempts'],
        planned_per_provider=8, axes=list(AXES), primary_axes=list(PRIMARY),
        planned_axis_slots_per_provider=32, planned_primary_axis_slots_per_provider=16,
        native_invalid_or_missing='separate_coverage_failure_never_silent_wrong_label_or_dropped_denominator',
        unknown='agreement_only_not_evidence_of_absence_or_positive_resolution',
        paired_delta='retrieval_minus_baseline_agreement_descriptive_not_causal_gain',
        incoherent='preserve_native_labels_and_conflicts_separately_no_automatic_fact_acceptance',
        incomplete='preserve_captured_prefix_count_but_no_agreement_without_complete_transport_verification',
        semantic_accuracy=None, H1_H2_eligibility=False, metric_effect='none')


def producers():
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in local_closure(ROOT, [Path(__file__).resolve()])}


def freeze(output):
    contract = policy()
    output.mkdir(parents=False, exist_ok=False)
    raw = (encoded(contract) + '\n').encode()
    (output / 'contract.json').write_bytes(raw)
    (output / 'receipt.json').write_text(encoded(dict(contract=CONTRACT,
        file_sha256={'contract.json': sha(raw)}, producer_sha256=producers())) + '\n')
    return verify_contract(output)


def verify_contract(output=None):
    output = FROZEN if output is None else output
    require({p.name for p in output.iterdir()} == {'contract.json', 'receipt.json'}, 'comparison contract inventory differs')
    raw = (output / 'contract.json').read_bytes()
    require(encoded(decode(raw)) == encoded(policy()) and decode((output / 'receipt.json').read_bytes()) ==
        dict(contract=CONTRACT, file_sha256={'contract.json': sha(raw)}, producer_sha256=producers()), 'comparison contract binding differs')
    return decode(raw)


def execution_binding():
    verify_contract()
    return dict(contract=CONTRACT, comparison_receipt_sha256=sha((FROZEN / 'receipt.json').read_bytes()),
        sol_top_line_sha256=sha((SOL_RUN / 'top-line.json').read_bytes()),
        authorization='user authorized matched Jev/Luna comparison after Sol top line',
        logical_request_limit=16, network_attempt_limit=48, semantic_retries_allowed=False)


def prepare_run(output):
    binding = execution_binding()
    result = stage(PREPARATION, output)
    (output / 'comparison-binding.json').write_text(encoded(binding) + '\n')
    return result


def check_binding(run):
    require(encoded(decode((run / 'comparison-binding.json').read_bytes())) == encoded(execution_binding()),
            'comparison execution/reference binding differs')


def summarize(rows, requests, references):
    expected = {r['request_id']: r for r in requests}
    require(len(expected) == len(requests), 'duplicate planned request')
    observed = {}
    for row in rows:
        rid = row['request_id']
        require(rid in expected and rid not in observed, 'unexpected/duplicate response')
        require(all(row[k] == expected[rid][k] for k in ('case_id', 'arm', 'provider')), 'response assignment differs')
        observed[rid] = row
    reports = {}
    for provider in dict.fromkeys(r['provider'] for r in requests):
        planned = [r for r in requests if r['provider'] == provider]
        selected = [observed[r['request_id']] for r in planned if r['request_id'] in observed]
        valid = [r for r in selected if r['native_status'] == 'valid']
        per_arm, details = {}, []
        for arm in ('baseline', 'retrieval'):
            schedule = [r for r in planned if r['arm'] == arm]
            subset = [r for r in valid if r['arm'] == arm]
            axes = {a: dict(matches=0, compared=len(subset), planned=len(schedule)) for a in AXES}
            for row in subset:
                reference = references[row['case_id'], arm]
                labels = row['prediction']['labels']
                different = [a for a in AXES if labels[a] != reference[a]]
                for axis in AXES:
                    axes[axis]['matches'] += labels[axis] == reference[axis]
                details.append(dict(request_id=row['request_id'], case_id=row['case_id'], arm=arm,
                    labels=labels, sol_labels=reference, differing_axes=different,
                    consistency_violations=row['consistency_violations'], native_warnings=row['prediction']['warnings'],
                    response_sha256=row['response_sha256']))
            per_arm[arm] = dict(axes=axes, all_axis_matches=sum(v['matches'] for v in axes.values()),
                primary_axis_matches=sum(axes[a]['matches'] for a in PRIMARY),
                compared_axis_slots=len(subset) * len(AXES), planned_axis_slots=len(schedule) * len(AXES))
        complete = len(valid) == len(planned)
        reports[provider] = dict(planned_responses=len(planned), verified_rows=len(selected), native_valid=len(valid),
            native_invalid=len(selected) - len(valid), coherent=sum(r['status'] == 'proposed_not_accepted' for r in valid),
            consistency_review=sum(r['status'] != 'proposed_not_accepted' for r in valid),
            all_axis_matches=sum(a['all_axis_matches'] for a in per_arm.values()),
            compared_axis_slots=len(valid) * len(AXES), planned_axis_slots=len(planned) * len(AXES),
            primary_axis_matches=sum(a['primary_axis_matches'] for a in per_arm.values()),
            planned_primary_axis_slots=len(planned) * len(PRIMARY), per_arm=per_arm, details=details,
            paired_all_axis_match_delta=(per_arm['retrieval']['all_axis_matches'] - per_arm['baseline']['all_axis_matches']) if complete else None,
            agreement_status='complete_native_label_comparison' if complete else 'not_evaluable_complete_cohort_missing_or_invalid')
    return reports


def score(run):
    contract = verify_contract()
    check_binding(run)
    transport = inspect(PREPARATION, run)
    manifest = verify_preparation(PREPARATION)
    top_line = decode((SOL_RUN / 'top-line.json').read_bytes())
    references = {(v['case_id'], v['arm']): v['labels'] for v in top_line['views']}
    captured = [decode(line) for line in (run / 'responses.jsonl').read_bytes().splitlines()] if (run / 'responses.jsonl').exists() else []
    return dict(contract=CONTRACT, comparison_contract_sha256=sha((FROZEN / 'contract.json').read_bytes()),
        sol_top_line_sha256=contract['sol_top_line_sha256'], reference_authority=contract['reference_authority'],
        transport_evidence=transport, captured_response_rows=len(captured),
        captured_prefix_is_not_verified_without_complete_inspector_evidence=True,
        providers=summarize(transport.get('rows', []), manifest['requests'], references),
        semantic_accuracy=None, H1_H2_eligibility=False, automatic_fact_acceptance=False, metric_effect='none')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', type=Path)
    mode.add_argument('--verify-contract', action='store_true')
    mode.add_argument('--stage', type=Path)
    mode.add_argument('--execute', type=Path)
    mode.add_argument('--score', type=Path)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.freeze:
        result = freeze(args.freeze)
    elif args.verify_contract:
        result = verify_contract()
    elif args.stage:
        result = prepare_run(args.stage)
    elif args.execute:
        check_binding(args.execute)
        result = execute_transport(PREPARATION, args.execute, live=args.live)
    else:
        if not args.output:
            parser.error('score requires an exclusive new output')
        result = score(args.score)
        with args.output.open('x') as stream:
            stream.write(encoded(result) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('requests', 'transport_evidence', 'providers')}, indent=2))


if __name__ == '__main__':
    main()
