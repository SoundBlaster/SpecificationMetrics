"""Prepare two balanced, blinded rubric-v2 annotation rounds; offline only."""
import argparse
import copy
import json
from pathlib import Path

from prepare_balanced_context_reference import RUN as V1, build as prepare_v1
from question_grouping import canonical, digest

ROOT = Path(__file__).parent
RUN = ROOT / 'runs/2026-10-13-rubric-v2-reference'
RUBRIC = ROOT / 'rubrics/expression-fit-v2.json'
CONTROLS = ('context-01', 'context-03', 'context-04', 'context-05', 'context-06',
            'context-07', 'context-08', 'context-10', 'context-11', 'context-17')


def encoded(value):
    return value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()


def task_digest(case, packet):
    return digest(canonical({'state': case['state'], 'questions': packet['questions'],
                             'instructions': packet['instructions'],
                             'rubric_file_sha256': packet['rubric_sha256'],
                             'annotation_prompt_sha256': packet['annotation_prompt_sha256']}))


def build():
    for name, value in prepare_v1().items():
        if canonical(json.loads((V1 / name).read_text())) != canonical(value):
            raise ValueError('Frozen v1 delivery differs: ' + name)
    raw_rubric = RUBRIC.read_bytes()
    rubric = json.loads(raw_rubric)
    prompt = (V1 / 'annotation-prompt.txt').read_text().replace(
        'case_id/state_sha256 unchanged', 'case_id/state_sha256/task_sha256/rubric_sha256 unchanged').encode()
    outputs = {'rubric.json': raw_rubric, 'annotation-prompt.txt': prompt}
    mapping = json.loads((V1 / 'source-mapping.json').read_text())
    task_ids = {}
    for slot in ('01', '02', '03'):
        packet = json.loads((V1 / f'annotation-packet-{slot}.json').read_text())
        packet.update(questions=rubric['questions'], rubric_id=rubric['id'],
                      rubric_sha256=digest(raw_rubric), questions_sha256=digest(canonical(rubric['questions'])),
                      annotation_prompt_sha256=digest(prompt))
        template = []
        for case in packet['cases']:
            if case['state_sha256'] != digest(canonical(case['state'])):
                raise ValueError('Source state differs')
            case.update(task_sha256=task_digest(case, packet), rubric_sha256=packet['rubric_sha256'])
            task_ids[case['case_id']] = case['task_sha256']
            template.append({**{k: case[k] for k in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256')},
                             'opportunity': None, 'concern_kind': None, 'evidence_quotes': [], 'uncertainties': []})
        outputs[f'annotation-packet-{slot}.json'] = packet
        outputs[f'annotation-template-{slot}.json'] = {'status': 'blank_not_reference', 'annotations': template}
    for row in mapping['cases']:
        row.update(task_sha256=task_ids[row['case_id']], rubric_sha256=digest(raw_rubric))
    outputs['source-mapping.json'] = mapping
    outputs['study-plan.json'] = {
        'status': 'criteria_frozen_before_annotation_not_provider_protocol',
        'rounds': 2, 'fresh_contexts': 6, 'cases_per_round': 18, 'total_case_annotations': 36,
        'delivery': 'same_packet_bytes_and_order_in_both_rounds_two_cases_per_mode_one_view_per_target',
        'H1': {'purpose': 'descriptive_within_v2_annotation_reliability',
               'min_matched_per_axis': 16, 'min_joint_matches': 15, 'denominator': 18},
        'H2': {'purpose': 'guard_against_blanket_abstention_on_previously_decisive_development_controls',
               'case_ids': list(CONTROLS), 'require_both_axes_decisive_in_both_rounds': True,
               'selection': 'ten_v1_jointly_stable_and_decisive_states_selected_before_v2_answers',
               'expected_v2_labels_assigned': False, 'human_gold': False},
        'semantic_review': 'Agreement and decisive coverage do not prove correctness; inspect evidence and ownership separately.',
        'comparison_to_v1': 'descriptive_only_rubric_and_bookkeeping_prompt_change_no_concurrent_randomized_v1_arm',
        'provider_requests': 0, 'metric_effect': 'none'}
    inputs = {f'{V1.name}/{n}': digest((V1 / n).read_bytes()) for n in
              ['source-mapping.json', 'annotation-prompt.txt'] + [f'annotation-packet-{s}.json' for s in ('01', '02', '03')]}
    inputs[str(RUBRIC.relative_to(ROOT))] = digest(raw_rubric)
    outputs['preparation-receipt.json'] = {
        'status': 'v2_delivery_prepared_independent_annotation_pending',
        'source_file_sha256': inputs, 'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {n: digest(encoded(v)) for n, v in outputs.items()},
        'task_identity': 'canonical_state_questions_packet_instructions_rubric_file_digest_prompt_template_digest',
        'new_jev_luna_requests': 0, 'metric_effect': 'none'}
    return outputs


def verify(run=RUN):
    outputs = build()
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Saved v2 preparation differs: ' + name)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        outputs = build()
        if any((args.run / n).exists() for n in outputs):
            raise ValueError('Refusing to overwrite v2 preparation')
        args.run.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            with (args.run / name).open('xb') as out:
                out.write(encoded(value))
    else:
        verify(args.run)
    print(json.dumps({'states': 18, 'rounds': 2, 'fresh_contexts': 6, 'jev_luna_requests': 0}))


if __name__ == '__main__':
    main()
