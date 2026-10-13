#!/usr/bin/env python3
"""Score v2 offline, retaining raw probabilities and Jev precision sensitivity."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from contrastive_decision_study_v2 import REFERENCE, inspect_results, load_reference
from question_grouping import digest
from score_contrastive_decisions import summarize as summarize_v1

HALF_STEP = Decimal('0.005')


def delta_interval(mechanics, policy):
    """Conservative bounds under assumed nearest-hundredth rounding, not a guarantee."""
    m, p = Decimal(str(mechanics)), Decimal(str(policy))
    lower = max(Decimal(0), p - HALF_STEP) - min(Decimal(1), m + HALF_STEP)
    upper = min(Decimal(1), p + HALF_STEP) - max(Decimal(0), m - HALF_STEP)
    return {'raw_delta': str(p - m), 'lower': str(lower), 'upper': str(upper),
            'direction': 'positive' if lower > 0 else 'negative' if upper < 0 else 'unresolved'}


def summarize(native, annotations, mapping):
    result = summarize_v1(native, annotations, mapping)
    result.update(study_kind='contrastive_mass_warning_score/v2',
                  acceptance_policy=native['acceptance_policy'],
                  warned_responses=native['warned_responses'],
                  execution_complete=native['execution_complete'])
    for provider in result['providers']:
        for repeat in provider['repeats']:
            unresolved, robust = [], 0
            for pair in repeat['pairs']:
                for role in ('mechanics', 'policy'):
                    cid = pair[role]['case_id']
                    row = next((r for r in native['rows'] if r['provider'] == provider['provider']
                                and r['repeat'] == repeat['repeat'] and r['case_id'] == cid), None)
                    pair[role]['warnings'] = row.get('warnings', []) if row else []
                if not all(pair[r]['usable_for_criteria'] for r in ('mechanics', 'policy')):
                    pair['probability_sensitivity'] = None
                    continue
                if provider['provider'] != 'jev-coreinfra':
                    pair['probability_sensitivity'] = {'policy': 'unchanged_strict_raw_probability_direction'}
                    continue
                bounds = {}
                for axis, option in (('opportunity', 'eligible'), ('concern_kind', 'policy')):
                    values = [pair[r]['prediction']['answers'][axis]['probabilities'][option]
                              for r in ('mechanics', 'policy')]
                    bounds[axis] = delta_interval(*values)
                positive = all(b['direction'] == 'positive' for b in bounds.values())
                robust += positive
                if not positive and all(Decimal(b['raw_delta']) > 0 for b in bounds.values()):
                    unresolved.append(pair['pair_id'])
                pair['probability_sensitivity'] = {
                    'assumption': 'each_Jev_probability_rounded_to_nearest_0.01_not_verified_provider_behavior',
                    'axes': bounds, 'both_lower_bounds_positive': positive}
            if provider['provider'] == 'jev-coreinfra':
                h3 = repeat['H3_secondary']
                h3.update(raw_directional_pairs=h3['directional_pairs'], directional_pairs=robust,
                          unresolved_raw_positive_pair_ids=unresolved,
                          criterion_met=robust >= h3['required'],
                          supported=repeat['operationally_complete'] and robust >= h3['required'])
    result['limits'] += (' V2 accepts bounded Jev mass warnings without normalization. '
                        'Jev H3 support additionally requires positive nearest-hundredth lower bounds; '
                        'this precision assumption is a sensitivity model, not provider calibration.')
    return result


def score(run, reference=REFERENCE):
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
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = score(args.run)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({k: result[k] for k in ('planned_requests', 'native_valid', 'warned_responses',
                                            'execution_complete', 'operationally_complete', 'metric_effect')}))


if __name__ == '__main__':
    main()
