"""Replay the frozen definition/owner-name annotation evidence without inference."""
import argparse
from collections import Counter
import json
from pathlib import Path

from prepare_context_reference_v2 import task_digest
from prepare_definition_owner_names import RUN as PREPARATION, verify
from question_grouping import canonical, digest

RUN = Path(__file__).parent / 'runs/2026-10-13-definition-owner-names-results'
AXES = ('opportunity', 'concern_kind')


def validate(packet, template, annotation, assignment):
    """Validate provenance and format; this does not grade semantic correctness."""
    if annotation.get('status') != 'independently_annotated_not_adjudicated':
        raise ValueError('Unexpected annotation authority')
    expected_inputs = [assignment['directory'] + '/' + n for n in ('packet.json', 'template.json')]
    isolation = annotation.get('isolation_report', {})
    if (assignment.get('context_inheritance') != 'none'
            or isolation.get('input_files') != expected_inputs
            or isolation.get('other_inputs_read') is not False):
        raise ValueError('Independent input scope not declared')
    cases = {c['case_id']: c for c in packet['cases']}
    templates = {r['case_id']: r for r in template['annotations']}
    rows = annotation['annotations']
    if (len(packet['cases']) != 4 or len(cases) != 4
            or len(template['annotations']) != 4 or set(templates) != set(cases)
            or len(rows) != 4 or {r['case_id'] for r in rows} != set(cases)):
        raise ValueError('Expected four unique assigned cases')
    for row in rows:
        case = cases[row['case_id']]
        for key in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256'):
            if row[key] != case[key] or row[key] != templates[row['case_id']][key]:
                raise ValueError('Template identity differs: ' + key)
        if (case['state_sha256'] != digest(canonical(case['state']))
                or case['task_sha256'] != task_digest(case, packet)
                or case['rubric_sha256'] != packet['rubric_sha256']):
            raise ValueError('Task content differs from its identity')
        for axis in AXES:
            if row[axis] not in packet['questions'][axis]['criteria']:
                raise ValueError('Unknown rubric label')
            reason = row['rationales'][axis]
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError('Both axes need explicit rationales')
        state = case['state']
        sources = [state['target']['code'], *[f['code'] for f in state['bounded_context']['fragments']]]
        covered = set()
        for quote in row['evidence_quotes']:
            axis, text = quote['axis'], quote['quote']
            if (axis not in AXES or not isinstance(text, str) or not text.strip()
                    or not any(text in source for source in sources)):
                raise ValueError('Quote must be contiguous code from this same case')
            covered.add(axis)
        if covered != set(AXES):
            raise ValueError('Evidence required for both axes')
        uncertainties = row['uncertainties']
        if (not isinstance(uncertainties, list)
                or any(not isinstance(u, str) or not u.strip() for u in uncertainties)):
            raise ValueError('Expected uncertainty strings')
        if (row['opportunity'] == 'needs_review' or row['concern_kind'] == 'unknown') and not uncertainties:
            raise ValueError('Abstention must identify missing evidence')
    return {'annotated_cases': 4, 'quote_provenance': 'passed',
            'semantic_correctness_verified': False}


def summarize(observations):
    groups = []
    for target in ('probe-a', 'probe-b', 'probe-c', 'probe-d'):
        for cell in ('01', '02', '03', '04'):
            rows = [r for r in observations if r['case_id'] == target and r['cell'] == cell]
            if len(rows) != 4:
                raise ValueError('Expected four repetitions per target/cell')
            groups.append({'case_id': target, 'cell': cell, 'n': 4,
                           'labels': {a: dict(sorted(Counter(r[a] for r in rows).items())) for a in AXES},
                           'decisive_counts': {a: sum(r[a] not in ('needs_review', 'unknown') for r in rows) for a in AXES},
                           'joint_counts': dict(sorted(Counter(r['opportunity'] + '/' + r['concern_kind'] for r in rows).items()))})
    focal = [r for r in observations if r['case_id'] == 'probe-a']
    control = [r for r in observations if r['case_id'] == 'probe-d']
    name_pairs = []
    for original, neutral in (('01', '03'), ('02', '04')):
        hist = [next(g for g in groups if g['case_id'] == 'probe-a' and g['cell'] == c)['labels']['concern_kind']
                for c in (original, neutral)]
        name_pairs.append({'original_cell': original, 'neutral_cell': neutral, 'histograms_match': hist[0] == hist[1]})
    return {'target_cell_distributions': groups,
            'prospective_label_criteria': {
                'H_ownership': {'met': all(r['opportunity'] == 'excluded' for r in focal), 'n': len(focal)},
                'H_names': {'met': all(p['histograms_match'] for p in name_pairs), 'comparisons': name_pairs},
                'H_local_control': {'met': all(r['opportunity'] == 'excluded' and r['concern_kind'] == 'mechanics' for r in control), 'n': len(control)}},
            'H_definition': 'Requires separate integrator rationale review; not inferred from Choice labels.',
            'semantic_correctness_verified': False, 'human_gold': False,
            'reference_frozen_for_provider_scoring': False, 'metric_effect': 'none'}


def build(run=RUN):
    verify()  # Replays the immutable preparation, including source and task bindings.
    receipt = json.loads((run / 'execution-receipt.json').read_text())
    assignments = receipt['assignments']
    expected_slots = {f'annotator-{i:02d}' for i in range(1, 17)}
    if len(assignments) != 16 or {a['slot'] for a in assignments} != expected_slots:
        raise ValueError('Expected sixteen fresh contexts')
    if len({a['agent_task'] for a in assignments}) != 16 or len({a['directory'] for a in assignments}) != 16:
        raise ValueError('Annotation contexts must be distinct')
    for name, sha in receipt['preparation_file_sha256'].items():
        if digest((PREPARATION / name).read_bytes()) != sha:
            raise ValueError('Frozen preparation binding differs')
    plan = json.loads((PREPARATION / 'dispatch-plan.json').read_text())
    by_slot = {a['slot']: a for a in plan['assignments']}
    observations, validations = [], []
    for a in assignments:
        original = by_slot[a['slot']]
        if any(a[k] != original[k] for k in ('packet', 'template', 'cases')):
            raise ValueError('Assignment differs from frozen dispatch plan')
        prompt = (PREPARATION / 'annotation-prompt.txt').read_text().format(directory=a['directory'])
        if digest(prompt.encode()) != a['prompt_sha256']:
            raise ValueError('Dispatched prompt differs')
        for kind, alias in (('packet', 'packet.json'), ('template', 'template.json')):
            if digest((PREPARATION / a[kind]).read_bytes()) != a['input_sha256'][alias]:
                raise ValueError('Assigned input differs')
        raw = (run / a['annotation_output']).read_bytes()
        if digest(raw) != a['output_sha256']:
            raise ValueError('Raw annotation differs')
        packet = json.loads((PREPARATION / a['packet']).read_text())
        template = json.loads((PREPARATION / a['template']).read_text())
        annotation = json.loads(raw)
        validations.append({'slot': a['slot'], **validate(packet, template, annotation, a)})
        selected = {c['case_id']: c for c in a['cases']}
        observations.extend({'slot': a['slot'], **selected[row['case_id']],
                             **{k: row[k] for k in ('opportunity', 'concern_kind', 'task_sha256')}}
                            for row in annotation['annotations'])
    return {'status': 'raw_annotations_validated_semantic_review_separate',
            'contexts': 16, 'case_annotations': 64, 'provider_requests': 0,
            'validation': validations, 'summary': summarize(observations),
            'isolation_boundary': 'fresh_context_scoped_inputs_self_report_not_filesystem_enforcement',
            'producer_sha256': digest(Path(__file__).read_bytes()),
            'execution_receipt_sha256': digest((run / 'execution-receipt.json').read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    args = parser.parse_args()
    print(json.dumps(build(args.run), indent=2))


if __name__ == '__main__':
    main()
