"""Prepare a blinded same-view repeatability pilot; no dispatch or model calls."""
import argparse
from itertools import combinations
import json
from pathlib import Path

from coreinfra_retry_run import decode, sha
from paired_blind_reference_v1 import AXES, PREPARATION
from paired_reference_qualification_v2 import ANNOTATIONS, ROOT, producers as qualification_producers, qualify
from retrieval_index_v1.source import encoded

CONTRACT = 'specmetrics.paired-reference-repeatability/v1'
REPEATS = 3


def build_plan():
    qualification = qualify()
    reference = decode((ANNOTATIONS / 'reference.json').read_bytes())
    views = {(r['case_id'], r['arm']): r for r in reference['views']}
    tasks = []
    for repeat in range(1, REPEATS + 1):
        cases = sorted({case for case, arm in views}, key=lambda c: sha(f'{CONTRACT}:{repeat}:{c}'.encode()))
        for position, case in enumerate(cases):
            arms = ('baseline', 'retrieval') if (repeat + position) % 2 else ('retrieval', 'baseline')
            for arm in arms:
                view = views[case, arm]
                packet = PREPARATION / 'blind' / view['view_id']
                inputs = [ANNOTATIONS / 'annotation-brief.txt', ANNOTATIONS / 'annotation-rubric.json',
                          packet / 'packet.json', packet / 'annotation-template.json']
                tasks.append(dict(task_id='repeat-' + sha(f'{repeat}:{view["view_id"]}'.encode())[:16],
                    repeat=repeat, case_id=case, arm=arm, view_id=view['view_id'], fork_turns='none',
                    execution_identity='pending_new_context',
                    input_sha256={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in inputs},
                    prompt_source=str((ANNOTATIONS / 'prompts' / (view['task_id'] + '.txt')).relative_to(ROOT)),
                    prompt_sha256=sha((ANNOTATIONS / 'prompts' / (view['task_id'] + '.txt')).read_bytes())))
    return dict(contract=CONTRACT, status='prepared_not_dispatched', visibility='integrator_only',
        qualification_sha256=sha(encoded(qualification).encode()),
        annotation_receipt_sha256=sha((ANNOTATIONS / 'receipt.json').read_bytes()),
        historical_results_used_as_repeats=False, repeats_per_view=REPEATS, views=8, tasks=tasks,
        budget=dict(new_annotation_contexts=24, hosted_coreinfra_requests=0, automatic_retries=0),
        configuration_binding=dict(status='pending_before_dispatch', requested_model=None, reasoning_effort=None,
            required='one_explicit_model_reasoning_and_common_settings_binding_for_all_24_tasks',
            unavailable_runtime_fields='record_as_unavailable_never_invent_or_equate_with_requested',
            seed_policy='record_if_exposed_uncontrolled_randomness_otherwise'),
        ordering='three_deterministic_blocks_each_4_baseline_4_retrieval_interleaved_by_case',
        isolation='one_fresh_context_per_task_no_history_memory_tools_search_or_cross_task_messages',
        prompt_delivery='only_copy_of_assigned_prompt_no_plan_reference_results_or_other_views',
        measurement=dict(primary_axes=['concern_kind', 'ownership'], secondary_axes=['evidence_confidence', 'tool_responsibility'],
            planned_same_view_pairs=24, planned_axis_pairs=96, planned_primary_axis_pairs=48,
            unit='eight_views_nested_in_four_targets_not_96_independent_observations',
            stability_criterion='all_three_repeats_agree_on_both_primary_axes_for_each_view',
            secondary_disagreement='report_and_review_no_silent_majority_or_label_replacement',
            missing_or_invalid='not_evaluable_never_drop_denominators',
            quality_authority='diagnostic_repeatability_not_truth_or_H1_H2_eligibility'),
        completion_requirements=['sealed_outputs_bound_to_inputs_configuration_and_unique_contexts',
            'source_quotes_spans_and_label_consistency_verified_before_any_reference_adjudication',
            'review_all_disagreements_before_new_versioned_reference_and_scoring_contract'],
        dispatch_authorized=False, paired_quality_scoring_allowed=False, metric_effect='none')


def agreement(plan, rows, configuration_sha256):
    """Diagnostic label arithmetic only, after execution/source-evidence audit.

    A caller-supplied configuration digest is not runtime attestation or a
    qualification override. This function cannot produce an accepted reference.
    """
    if plan != build_plan():
        raise ValueError('repeatability plan differs from frozen design')
    tasks = {t['task_id']: t for t in plan['tasks']}
    if len(configuration_sha256) != 64 or any(c not in '0123456789abcdef' for c in configuration_sha256):
        raise ValueError('invalid bound configuration digest')
    rubric = decode((ANNOTATIONS / 'annotation-rubric.json').read_bytes())['questions']
    seen, contexts, grouped = set(), set(), {}
    for row in rows:
        tid = row['task_id']
        if tid not in tasks or tid in seen or not isinstance(row['execution_id'], str) or not row['execution_id'].strip() or row['execution_id'] in contexts:
            raise ValueError('unknown/repeated task or execution context')
        task = tasks[tid]
        if row['configuration_sha256'] != configuration_sha256 or row['input_sha256'] != task['input_sha256']:
            raise ValueError('configuration or exact-view input binding differs')
        if set(row['labels']) != set(AXES) or any(row['labels'][a] not in rubric[a]['criteria'] for a in AXES):
            raise ValueError('invalid annotation labels')
        seen.add(tid)
        contexts.add(row['execution_id'])
        grouped.setdefault(task['view_id'], []).append(row['labels'])
    complete = seen == set(tasks)
    comparisons = {a: dict(agreed=0, compared=0, planned=24) for a in AXES}
    views = []
    for view_id in sorted({t['view_id'] for t in tasks.values()}):
        labels = grouped.get(view_id, [])
        distinct = {a: sorted({r[a] for r in labels}) for a in AXES}
        for left, right in combinations(labels, 2):
            for axis in AXES:
                comparisons[axis]['compared'] += 1
                comparisons[axis]['agreed'] += left[axis] == right[axis]
        views.append(dict(view_id=view_id, observations=len(labels), distinct_labels=distinct,
            primary_unanimous=len(labels) == REPEATS and all(len(distinct[a]) == 1 for a in plan['measurement']['primary_axes']),
            differing_axes=[a for a in AXES if len(distinct[a]) > 1]))
    stable = all(v['primary_unanimous'] for v in views) if complete else None
    return dict(contract=CONTRACT, status='complete_label_diagnostic' if complete else 'not_evaluable_incomplete',
        observed=len(rows), planned=24, complete=complete, per_axis=comparisons, per_view=views,
        primary_stable_in_pilot=stable, diagnostic_only=True, source_evidence_verified_by_this_function=False,
        semantic_accuracy=None, paired_quality_scoring_allowed=False)


def producers():
    return dict(qualification_producers(), **{Path(__file__).name: sha(Path(__file__).read_bytes())})


def freeze(output):
    plan = build_plan()
    output.mkdir(parents=False, exist_ok=False)
    (output / 'prompts').mkdir()
    (output / 'plan.json').write_text(encoded(plan) + '\n')
    for task in plan['tasks']:
        (output / 'prompts' / (task['task_id'] + '.txt')).write_bytes((ROOT / task['prompt_source']).read_bytes())
    files = {str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
    (output / 'receipt.json').write_text(encoded(dict(contract=CONTRACT, file_sha256=files, producer_sha256=producers())) + '\n')
    return verify(output)


def verify(output):
    plan = build_plan()
    expected = {'plan.json': (encoded(plan) + '\n').encode()}
    expected.update({'prompts/' + t['task_id'] + '.txt': (ROOT / t['prompt_source']).read_bytes() for t in plan['tasks']})
    actual = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob('*') if p.is_file() and p != output / 'receipt.json'}
    if actual != expected or decode((output / 'receipt.json').read_bytes()) != dict(contract=CONTRACT,
            file_sha256={name: sha(raw) for name, raw in expected.items()}, producer_sha256=producers()):
        raise ValueError('repeatability plan, prompt or producer binding differs')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    plan = freeze(args.freeze) if args.freeze else verify(args.verify)
    print(json.dumps(dict(status=plan['status'], tasks=len(plan['tasks']), dispatch_authorized=plan['dispatch_authorized'])))


if __name__ == '__main__':
    main()
