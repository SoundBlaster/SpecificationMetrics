"""Frozen paired scoring: inspect real transport; qualify reference before H1/H2."""
import argparse
import json
from pathlib import Path

from coreinfra_retry_run import decode, sha
from paired_blind_reference_v1 import AXES
from paired_reference_qualification_v1 import ANNOTATIONS, ROOT, verify as qualify_reference
from paired_retrieval_study_v1 import verify as verify_preparation
from prepare_retrieval_context_v1 import QUESTIONS
from retrieval_fact_adapter_v1.dependencies import local_closure
from retrieval_index_v1.source import digest, encoded
from verify_paired_retrieval_transport_v1 import inspect

CONTRACT = 'specmetrics.paired-retrieval-scoring/v1'
PREPARATION = ROOT / 'runs/2026-10-18-paired-retrieval-preparation-v1'
QUALIFICATION = ROOT / 'runs/2026-10-18-paired-reference-qualification-v1'
FROZEN = ROOT / 'runs/2026-10-18-paired-scoring-contract-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def policy():
    manifest = verify_preparation(PREPARATION)
    qualification = qualify_reference(QUALIFICATION)
    return dict(contract=CONTRACT, status='frozen_before_provider_observations',
        manifest_sha256=sha((PREPARATION / 'manifest.json').read_bytes()),
        reference_sha256=sha((ANNOTATIONS / 'reference.json').read_bytes()),
        qualification_receipt_sha256=sha((QUALIFICATION / 'receipt.json').read_bytes()),
        reference_design_status=qualification['status'],
        questions_sha256=digest(encoded(QUESTIONS)), axes=list(AXES),
        planned_responses=16, planned_responses_per_provider=8,
        planned_target_pairs_per_provider=4, planned_axis_slots_per_provider=32,
        reserved_max_network_attempts=manifest['max_network_attempts'],
        unknown='exact_reference_match_is_agreement_not_absence_or_supported_resolution',
        invalid_or_missing='operational_or_coverage_failure_not_wrong_domain_label',
        ambiguity='retain_diagnostics_but_no_H1_H2_effect_score',
        H1='positive_net_supported_role_and_ownership_resolutions_per_adjudicable_target_pair; gains_and_losses_separate',
        H1_resolution='coherent_correct_role_with_supported_ordinal_evidence_or_correct_nonunknown_owner_against_view_reference',
        H2='zero_new_unsupported_retrieval_ownership_assertions_against_qualified_view_reference',
        H3='all_16_verified_responses_native_valid_no_ambiguous_posts_or_duplicate_execution',
        quality_prerequisites=['qualified_actual_annotator_design', 'complete_unambiguous_local_transport',
                               'all_native_responses_valid_and_category_consistent', 'adjudicated_comparable_views'],
        reference_qualification_mandatory=True, inference_authorized=False, metric_effect='none')


def producer_digests():
    return {str(p.relative_to(ROOT)): sha(p.read_bytes())
            for p in local_closure(ROOT, [Path(__file__).resolve()])}


def freeze(output):
    output.mkdir(parents=False, exist_ok=False)
    raw = (encoded(policy()) + '\n').encode()
    (output / 'contract.json').write_bytes(raw)
    (output / 'receipt.json').write_text(encoded(dict(contract=CONTRACT,
        file_sha256={'contract.json': sha(raw)}, producer_sha256=producer_digests())) + '\n')
    return verify_contract(output)


def verify_contract(output=None):
    output = FROZEN if output is None else output
    require({p.name for p in output.iterdir()} == {'contract.json', 'receipt.json'}, 'scoring contract inventory differs')
    raw = (output / 'contract.json').read_bytes()
    require(decode(raw) == policy(), 'scoring contract differs from policy reconstruction')
    require(decode((output / 'receipt.json').read_bytes()) == dict(contract=CONTRACT,
        file_sha256={'contract.json': sha(raw)}, producer_sha256=producer_digests()), 'scoring producer binding differs')
    return decode(raw)


def summarize(rows, requests, references, *, qualified):
    """Pure arithmetic; only the CLI's verified qualification supplies authority.

    Unit fixtures can exercise qualified arithmetic. This v1's pinned real
    qualification is false and has no CLI override or alternative reference path.
    """
    expected = {r['request_id']: r for r in requests}
    require(len(expected) == len(requests), 'duplicate planned request')
    observed = {}
    for row in rows:
        rid = row['request_id']
        require(rid in expected and rid not in observed, 'unexpected or duplicate response identity')
        request = expected[rid]
        require(all(row[k] == request[k] for k in ('case_id', 'provider', 'arm')), 'response target/provider/arm differs')
        observed[rid] = row
    reports = {}
    for provider in dict.fromkeys(r['provider'] for r in requests):
        plan = [r for r in requests if r['provider'] == provider]
        selected = [observed[r['request_id']] for r in plan if r['request_id'] in observed]
        valid = [r for r in selected if r['native_status'] == 'valid']
        coherent = [r for r in valid if r['status'] == 'proposed_not_accepted']
        matrices = {axis: {} for axis in AXES}
        matches = 0
        for row in valid:
            reference = references[row['case_id'], row['arm']]
            labels = row['prediction']['labels']
            for axis in AXES:
                key = reference[axis] + ' -> ' + labels[axis]
                matrices[axis][key] = matrices[axis].get(key, 0) + 1
                matches += labels[axis] == reference[axis]
        H1 = H2 = dict(status='not_evaluable_reference_design')
        comparisons = []
        if qualified and len(coherent) == len(plan):
            net = gains = losses = new_unsupported = adjudicable = 0
            for case in dict.fromkeys(r['case_id'] for r in plan):
                arms = {r['arm']: r['prediction']['labels'] for r in coherent if r['case_id'] == case}
                require(set(arms) == {'baseline', 'retrieval'}, 'incomplete qualified pair')
                ref = {arm: references[case, arm] for arm in arms}
                for axis in ('concern_kind', 'ownership'):
                    require(len({v[axis] for v in ref.values() if v[axis] != 'unknown'}) <= 1,
                            'qualified pair has unresolved conflicting reference values')
                usable = any(v['ownership'] != 'unknown' or v['concern_kind'] != 'unknown'
                             and v['evidence_confidence'] == 'supported' for v in ref.values())
                adjudicable += usable
                resolutions, unsupported = {}, {}
                for arm, labels in arms.items():
                    truth = ref[arm]
                    resolutions[arm] = (
                        int(truth['concern_kind'] != 'unknown' and truth['evidence_confidence'] == 'supported'
                            and labels['concern_kind'] == truth['concern_kind']
                            and labels['evidence_confidence'] == 'supported'),
                        int(truth['ownership'] != 'unknown' and labels['ownership'] == truth['ownership']))
                    unsupported[arm] = labels['ownership'] != 'unknown' and labels['ownership'] != truth['ownership']
                changes = [r - b for b, r in zip(resolutions['baseline'], resolutions['retrieval'])]
                delta = sum(changes)
                new_claim = unsupported['retrieval'] and (not unsupported['baseline']
                    or arms['baseline']['ownership'] != arms['retrieval']['ownership'])
                net += delta
                gains += sum(c > 0 for c in changes)
                losses += sum(c < 0 for c in changes)
                new_unsupported += new_claim
                comparisons.append(dict(case_id=case, role_owner_resolutions=resolutions,
                                        gains=sum(c > 0 for c in changes), losses=sum(c < 0 for c in changes),
                                        unsupported_ownership=unsupported, new_unsupported_ownership=bool(new_claim)))
            H1 = dict(status=('not_evaluable_no_supported_reference_resolutions' if not adjudicable else
                              'supported_in_pilot' if net > 0 else 'not_supported_in_pilot'),
                      net_supported_fact_resolutions=net, gains=gains, losses=losses,
                      target_pair_denominator=adjudicable,
                      mean_net_resolutions_per_pair=net / adjudicable if adjudicable else None)
            H2 = dict(status='passes_pilot_no_regression' if new_unsupported == 0 else 'fails_pilot_no_regression',
                      new_unsupported_ownership_assertions=new_unsupported, target_pair_denominator=len(comparisons))
        elif qualified:
            H1 = H2 = dict(status='not_evaluable_incomplete_or_incoherent_responses')
        reports[provider] = dict(planned_responses=len(plan), verified_rows_available=len(selected),
            native_valid=len(valid), native_invalid=len(selected) - len(valid),
            consistency_review=len(valid) - len(coherent), coherent=len(coherent),
            planned_axis_slots=len(plan) * len(AXES), compared_diagnostic_axis_slots=len(valid) * len(AXES),
            diagnostic_label_matches=matches, diagnostic_label_mismatches=len(valid) * len(AXES) - matches,
            diagnostic_confusion_counts=matrices, H1=H1, H2=H2, paired_resolution_details=comparisons)
    return reports


def score(run):
    contract = verify_contract()
    qualification = qualify_reference(QUALIFICATION)
    manifest = verify_preparation(PREPARATION)
    transport = inspect(PREPARATION, run)  # Never trust a caller-supplied inspector report.
    references = {(v['case_id'], v['arm']): v['labels']
                  for v in decode((ANNOTATIONS / 'reference.json').read_bytes())['views']}
    complete = transport['transport_verified'] is True
    operational = complete and transport['operationally_complete'] is True
    native = complete and transport['native_contract_valid'] is True
    require(qualification['paired_quality_scoring_allowed'] is False,
            'v1 requires a new contract/version before a different reference qualification is accepted')
    providers = summarize(transport.get('rows', []), manifest['requests'], references, qualified=False)
    if not complete:
        h3 = 'fails_incomplete_execution' if transport.get('stop_reason') else 'not_evaluable_incomplete_evidence'
    else:
        h3 = 'passes_pilot' if operational and native else 'fails_ambiguity_or_native_contract'
    return dict(contract=CONTRACT, scoring_contract_sha256=sha((FROZEN / 'contract.json').read_bytes()),
        reference_design_status=qualification['status'], paired_quality_scoring_allowed=False,
        transport_status=transport['status'], transport_evidence=transport,
        providers=providers, H3=dict(status=h3, planned_responses=contract['planned_responses'],
                                   reserved_max_network_attempts=contract['reserved_max_network_attempts']),
        interpretation='diagnostic_label_agreement_is_not_accuracy_or_paired_effect_evidence',
        inference_authorized=False, metric_effect='none')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', type=Path)
    mode.add_argument('--verify-contract', action='store_true')
    mode.add_argument('--run', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.freeze:
        result = freeze(args.freeze)
    elif args.verify_contract:
        result = verify_contract()
    else:
        if not args.output:
            parser.error('run requires an exclusive new output path')
        result = score(args.run)
        with args.output.open('x') as stream:
            stream.write(encoded(result) + '\n')
    print(json.dumps(dict(contract=CONTRACT, validated=True,
                          status=result.get('status', result.get('transport_status')))))


if __name__ == '__main__':
    main()
