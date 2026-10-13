"""Validate rubric-bound independent annotations and report reliability, offline."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from compare_context_references import compare as v1_comparison
from prepare_context_evidence import RUN as ORIGINAL
from prepare_context_reference_v2 import ROOT, RUN, V1, task_digest, verify
from question_grouping import digest
from validate_context_annotations import AXES, compare_views, validate as validate_structure

ABSTAIN = {'opportunity': 'needs_review', 'concern_kind': 'unknown'}


def validate(packet, annotation, assignment):
    result = validate_structure(packet, annotation, assignment)
    cases = {c['case_id']: c for c in packet['cases']}
    for row in annotation['annotations']:
        case = cases[row['case_id']]
        if (row.get('rubric_sha256') != packet['rubric_sha256']
                or case.get('rubric_sha256') != packet['rubric_sha256']
                or row.get('task_sha256') != case['task_sha256']
                or row.get('task_sha256') != task_digest(case, packet)):
            raise ValueError('Rubric-bound annotation task mismatch')
    return {**result, 'task_identity_verified': True}


def coverage(rows):
    return {'total': len(rows),
            'labels': {a: dict(sorted(Counter(r[a] for r in rows).items())) for a in AXES},
            'decisive': {a: sum(r[a] != ABSTAIN[a] for r in rows) for a in AXES},
            'joint_decisive': sum(all(r[a] != ABSTAIN[a] for a in AXES) for r in rows)}


def compare_rounds(rounds, plan):
    ids = set(rounds[0])
    if len(rounds) != 2 or len(ids) != 18 or set(rounds[1]) != ids:
        raise ValueError('Expected two rounds covering the same eighteen tasks')
    pairs = []
    for cid in sorted(ids):
        first, second = [r[cid] for r in rounds]
        task = first.get('task_sha256')
        if (not isinstance(task, str) or not re.fullmatch('[0-9a-f]{64}', task)
                or task != second.get('task_sha256')
                or not first.get('rubric_sha256') or first['rubric_sha256'] != second.get('rubric_sha256')
                or first['state_sha256'] != second['state_sha256']):
            raise ValueError('Same-input repeats require state AND rubric-bound task identity')
        pairs.append({'case_id': cid, 'state_sha256': first['state_sha256'], 'task_sha256': task,
                      'round_1': {a: first[a] for a in AXES}, 'round_2': {a: second[a] for a in AXES},
                      'changed_axes': [a for a in AXES if first[a] != second[a]]})
    agreement = {a: {'matched': sum(a not in p['changed_axes'] for p in pairs), 'total': 18} for a in AXES}
    joint = sum(not p['changed_axes'] for p in pairs)
    conditional = {}
    for axis in AXES:
        decisive = [p for p in pairs if all(p[r][axis] != ABSTAIN[axis] for r in ('round_1', 'round_2'))]
        conditional[axis] = {'matched': sum(axis not in p['changed_axes'] for p in decisive), 'total': len(decisive)}
    controls = plan['H2']['case_ids']
    if len(controls) != 10 or len(set(controls)) != 10 or not set(controls) <= ids:
        raise ValueError('Expected ten distinct preregistered development controls')
    losses = [{'case_id': cid, 'round': n, 'axis': a} for cid in controls
              for n, rows in enumerate(rounds, 1) for a in AXES if rows[cid][a] == ABSTAIN[a]]
    return {'cases': pairs, 'agreement': agreement, 'joint_agreement': {'matched': joint, 'total': 18},
            'agreement_when_both_decisive': conditional,
            'coverage': [coverage(list(r.values())) for r in rounds],
            'H1': {'passed': all(agreement[a]['matched'] >= plan['H1']['min_matched_per_axis'] for a in AXES)
                    and joint >= plan['H1']['min_joint_matches'], 'criterion': plan['H1']},
            'H2': {'passed': not losses, 'controls': len(controls), 'abstentions_on_controls': losses},
            'semantic_correctness_verified': False, 'label_overrides': [],
            'reference_frozen_for_provider_scoring': False}


def build(run=RUN):
    preparation = verify(run)
    plan = preparation['study-plan.json']
    mapping = preparation['source-mapping.json']
    packets = [preparation[f'annotation-packet-{s}.json'] for s in ('01', '02', '03')]
    rounds, validations, inputs = [], [], []
    directories, agents = set(), set()
    view_comparisons = []
    for repeat in (1, 2):
        prefix = f'round-{repeat}/'
        name = prefix + 'annotation-assignments.json'
        inputs.append(name)
        metadata = json.loads((run / name).read_text())
        assignments = metadata['assignments']
        if (metadata['round'] != repeat or len(assignments) != 3
                or {a['slot'] for a in assignments} != {'01', '02', '03'}):
            raise ValueError('Expected three fresh contexts per round')
        annotations = []
        for assignment in sorted(assignments, key=lambda a: a['slot']):
            slot = assignment['slot']
            for alias, kind in [('packet.json', 'packet'), ('template.json', 'template')]:
                source = f'annotation-{kind}-{slot}.json'
                binding = assignment['files'][alias]
                if binding['source'] != source or binding['sha256'] != digest((run / source).read_bytes()):
                    raise ValueError('Assigned input bytes differ')
            if assignment['directory'] in directories or assignment['agent_task'] in agents:
                raise ValueError('Annotation contexts must be fresh and distinct')
            directories.add(assignment['directory']); agents.add(assignment['agent_task'])
            output = prefix + f'independent-annotations-{slot}.json'
            inputs.append(output)
            raw = (run / output).read_bytes()
            prompt = (run / 'annotation-prompt.txt').read_text().rstrip('\n').format(directory=assignment['directory'])
            if (assignment['output_sha256'] != digest(raw)
                    or assignment['dispatched_prompt_sha256'] != digest(prompt.encode())):
                raise ValueError('Raw output or dispatch prompt binding mismatch')
            annotation = json.loads(raw)
            validations.append(validate(preparation[f'annotation-packet-{slot}.json'], annotation, assignment))
            annotations.append(annotation)
        rows = [r for d in annotations for r in d['annotations']]
        rounds.append({r['case_id']: r for r in rows})
        view_comparisons.append(compare_views(mapping, packets, annotations))
    result = compare_rounds(rounds, plan)
    by_view = {m['case_id']: m['evidence_mode'] for m in mapping['cases']}
    result['coverage_by_view'] = [{mode: coverage([r for cid, r in rows.items() if by_view[cid] == mode])
                                  for mode in sorted(set(by_view.values()))} for rows in rounds]
    old = v1_comparison()
    baseline = {'agreement': old['agreement'],
                'joint_agreement': {'matched': sum(not r['changed_axes'] for r in old['cases']), 'total': 18},
                'input_file_sha256': old['input_file_sha256'], 'coverage': [],
                'comparison_kind': 'cross_rubric_descriptive_not_same_task_or_causal_improvement'}
    for folder in (ORIGINAL, V1):
        rows = [r for s in ('01', '02', '03')
                for r in json.loads((folder / f'independent-annotations-{s}.json').read_text())['annotations']]
        baseline['coverage'].append(coverage(rows))
    return {'status': 'independent_v2_annotations_validated_integrator_review_separate',
            'input_file_sha256': {n: digest((run / n).read_bytes()) for n in [*preparation, *inputs]},
            'producer_sha256': {n: digest((ROOT / n).read_bytes()) for n in
                               ('validate_context_reference_v2.py', 'validate_context_annotations.py', 'compare_context_references.py')},
            'validations': validations, 'within_v2': result, 'views': view_comparisons,
            'baseline_v1': baseline, 'new_jev_luna_requests': 0, 'metric_effect': 'none',
            'interpretation': 'Six related families, two fresh annotations per state. Agreement, abstention and semantic correctness are separate. Model identity is inherited and not independently verified.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    args = parser.parse_args()
    print(json.dumps(build(args.run), indent=2))


if __name__ == '__main__':
    main()
