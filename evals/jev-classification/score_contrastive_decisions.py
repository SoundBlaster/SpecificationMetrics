#!/usr/bin/env python3
"""Score frozen contrastive H1/H2/H3 offline; no inference or metric writes."""
import argparse
from collections import Counter
import json
from pathlib import Path

from contrastive_decision_study import REFERENCE, RUN, PROVIDERS, inspect_results, load_reference
from question_grouping import digest

AXES = ('opportunity', 'concern_kind')


def usable(row):
    return (row is not None and row['native_status'] == 'valid'
            and type(row['ambiguous_posts']) is int and row['ambiguous_posts'] == 0
            and row['duplicate_execution_possible'] is False)


def summarize(native, annotations, mapping):
    reference = {r['case_id']: r for r in annotations['annotations']}
    mapped = {r['case_id']: r for r in mapping['cases']}
    if (len(reference) != 12 or len(annotations['annotations']) != 12
            or len(mapped) != 12 or set(mapped) != set(reference) or native['planned_requests'] != 48):
        raise ValueError('Expected twelve cases and 48 planned requests')
    families = {}
    for cid, item in mapped.items():
        roles = families.setdefault(item['pair_id'], {})
        if item['stratum'] in roles or item['state_sha256'] != reference[cid]['state_sha256']:
            raise ValueError('Duplicate role or stale reference mapping')
        roles[item['stratum']] = cid
    if len(families) != 4 or any(set(roles) != {'mechanics', 'policy', 'withheld'} for roles in families.values()):
        raise ValueError('Expected four complete families with unique withheld controls')
    provider_ids = [p[0] for p in PROVIDERS]
    rows = {}
    for row in native['rows']:
        key = row['provider'], row['repeat'], row['case_id']
        if key in rows or key[0] not in provider_ids or type(key[1]) is not int or key[1] not in (1, 2) or key[2] not in reference:
            raise ValueError('Unexpected or duplicate scored result identity')
        rows[key] = row
    reports = []
    for provider in provider_ids:
        repeats = []
        for repeat in (1, 2):
            current = {cid: rows.get((provider, repeat, cid)) for cid in reference}
            answers = {cid: row['prediction']['answers'] for cid, row in current.items() if usable(row)}

            def describe(cid):
                row = current[cid]
                return {'case_id': cid, 'reference': {a: reference[cid][a] for a in AXES},
                        'native_status': row['native_status'] if row else 'missing',
                        'ambiguous_posts': row['ambiguous_posts'] if row else None,
                        'usable_for_criteria': cid in answers,
                        'prediction': row['prediction'] if row else None,
                        'usage': row.get('usage') if row else None}

            pairs, controls = [], []
            for pair_id, roles in sorted(families.items()):
                mechanics, policy, withheld = (roles[r] for r in ('mechanics', 'policy', 'withheld'))
                complete = mechanics in answers and policy in answers
                axis_correct = {a: complete and all(answers[cid][a]['choice'] == reference[cid][a]
                                                   for cid in (mechanics, policy)) for a in AXES}
                deltas = {axis: (answers[policy][axis]['probabilities'][label]
                                - answers[mechanics][axis]['probabilities'][label]) if complete else None
                          for axis, label in (('opportunity', 'eligible'), ('concern_kind', 'policy'))}
                pairs.append({'pair_id': pair_id, 'mechanics': describe(mechanics), 'policy': describe(policy),
                              'axis_correct': axis_correct, 'jointly_correct': all(axis_correct.values()),
                              'policy_minus_mechanics_probability': deltas,
                              'both_probability_deltas_positive': complete and all(d > 0 for d in deltas.values())})
                correct = {a: withheld in answers and answers[withheld][a]['choice'] == reference[withheld][a] for a in AXES}
                controls.append({'pair_id': pair_id, **describe(withheld), 'axis_correct': correct,
                                 'jointly_correct': all(correct.values())})
            full_ids = [cid for cid, item in mapped.items() if item['stratum'] != 'withheld']
            axes = {}
            for axis in AXES:
                confusion = Counter((reference[cid][axis], answers[cid][axis]['choice'])
                                    for cid in full_ids if cid in answers)
                axes[axis] = {'matched': sum(n for (a, b), n in confusion.items() if a == b),
                              'planned': 8, 'usable': sum(cid in answers for cid in full_ids),
                              'confusion': [{'reference': a, 'prediction': b, 'count': n}
                                            for (a, b), n in sorted(confusion.items())]}
            policy_ids = [r['policy'] for r in families.values()]
            mechanical_ids = [r['mechanics'] for r in families.values()]
            recovered = sum(cid in answers and answers[cid]['opportunity']['choice'] == 'eligible' for cid in policy_ids)
            false_positives = [cid for cid in mechanical_ids
                               if cid in answers and answers[cid]['opportunity']['choice'] == 'eligible']
            operational = len(answers) == 12 and native['attempt_ledger_complete']
            h1 = sum(p['jointly_correct'] for p in pairs)
            h2 = sum(c['jointly_correct'] for c in controls)
            h3 = sum(p['both_probability_deltas_positive'] for p in pairs)
            repeats.append({'repeat': repeat, 'planned_cases': 12, 'usable_cases': len(answers),
                            'unavailable_or_ambiguous_case_ids': [cid for cid in reference if cid not in answers],
                            'operationally_complete': operational, 'full_context_axes': axes,
                            'eligible_policy_recall': {'recovered': recovered, 'planned': 4},
                            'mechanical_false_positives': {'case_ids': false_positives, 'planned': 4,
                                                         'usable': sum(cid in answers for cid in mechanical_ids)},
                            'pairs': pairs, 'withheld_controls': controls,
                            'H1': {'correct_pairs': h1, 'planned': 4, 'criterion_met': h1 == 4,
                                   'supported': operational and h1 == 4},
                            'H2': {'correct_controls': h2, 'planned': 4, 'criterion_met': h2 == 4,
                                   'supported': operational and h2 == 4},
                            'H3_secondary': {'directional_pairs': h3, 'planned': 4, 'required': 3,
                                             'criterion_met': h3 >= 3, 'supported': operational and h3 >= 3}})
        disagreements, confidence_deltas, probability_deltas, unavailable = [], [], [], []
        paired = 0
        for cid in reference:
            pair = [rows.get((provider, repeat, cid)) for repeat in (1, 2)]
            if not all(usable(row) for row in pair):
                unavailable.append(cid)
                continue
            for axis in AXES:
                paired += 1
                first, second = [row['prediction']['answers'][axis] for row in pair]
                if first['choice'] != second['choice']:
                    disagreements.append({'case_id': cid, 'axis': axis,
                                          'repeat_1': first['choice'], 'repeat_2': second['choice']})
                confidence_deltas.append(abs(first['confidence'] - second['confidence']))
                probability_deltas.extend(abs(first['probabilities'][label] - second['probabilities'][label])
                                          for label in first['probabilities'])
        reports.append({'provider': provider, 'repeats': repeats,
                        'repeat_consistency': {'paired_axis_answers': paired, 'planned_axis_pairs': 24,
                                               'unavailable_case_ids': unavailable, 'label_disagreements': disagreements,
                                               'max_native_confidence_delta': max(confidence_deltas, default=None),
                                               'max_option_probability_delta': max(probability_deltas, default=None),
                                               'supported': native['attempt_ledger_complete'] and paired == 24 and not disagreements}})
    return {'schema_version': 1, 'study_kind': 'contrastive_raw_provider_score',
            'reference_authority': annotations['status'], 'planned_requests': 48,
            'received_rows': native['received_rows'], 'native_valid': native['native_valid'],
            'native_invalid': native['native_invalid'], 'operationally_complete': native['operationally_complete'],
            **{name: native[name] for name in ('missing_result_request_ids', 'unattempted_request_ids',
                                              'attempt_status_unknown_request_ids', 'attempted_without_result_request_ids')},
            'providers': reports, 'inference_performed_by_scorer': False, 'metric_effect': 'none',
            'formal_ownership_gate': 'not_applied_no_existing_composition_controls',
            'limits': 'Four authored development pairs, explicit contracts and four explicit withheld controls; model reference, not human gold. Hypotheses/stability are separate, missing/invalid/ambiguous results retain denominators. No cross-provider probability calibration, natural-code generalization, causal component isolation or production-readiness claim.'}


def score(run=RUN, reference=REFERENCE):
    native = inspect_results(run, reference)
    data, hashes = load_reference(reference)
    result = summarize(native, data['independent-annotations.json'], data['source-mapping.json'])
    result['evidence_sha256'] = {name: digest((run / name).read_bytes()) if (run / name).exists() else None
                                 for name in ('manifest.json', 'responses.jsonl', 'attempts.jsonl', 'receipt.json')}
    result['reference_sha256'] = hashes['independent-annotations.json']
    result['reference_review_sha256'] = hashes['reference-review.json']
    result['scorer_sha256'] = digest(Path(__file__).read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = score(args.run)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({'planned_requests': 48, 'native_valid': result['native_valid'],
                      'operationally_complete': result['operationally_complete'], 'metric_effect': 'none'}))


if __name__ == '__main__':
    main()
