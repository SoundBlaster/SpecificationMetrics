"""Validate frozen preparation or one retained annotation attempt offline."""
import argparse
from collections import Counter
import json
from pathlib import Path

import prepare_manifest_contract_factorial as preparation
from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest

AXES = ('opportunity', 'concern_kind')


def validate_annotation(packet, template, annotation, assignment):
    if not isinstance(annotation, dict) or annotation.get('status') != 'independently_annotated_not_adjudicated':
        raise ValueError('Unexpected annotation authority')
    directory = assignment.get('directory')
    if (not isinstance(directory, str) or not Path(directory).is_absolute()
            or assignment.get('context_inheritance') != 'none'
            or not isinstance(assignment.get('agent_task'), str) or not assignment['agent_task'].strip()):
        raise ValueError('Fresh context assignment must be explicitly recorded')
    isolation = annotation.get('isolation_report', {})
    if (not isinstance(isolation, dict) or isolation.get('other_inputs_read') is not False
            or isolation.get('input_files') != [directory + '/' + n for n in ('packet.json', 'template.json')]):
        raise ValueError('Assigned input scope deviates')
    rows, cases = annotation.get('annotations'), packet['cases']
    if (len(cases) != 1 or len(template['annotations']) != 1 or not isinstance(rows, list)
            or len(rows) != 1 or not isinstance(rows[0], dict)):
        raise ValueError('Expected one assigned annotation')
    case, blank, row = cases[0], template['annotations'][0], rows[0]
    for field in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256'):
        if row.get(field) != case[field] or blank[field] != case[field]:
            raise ValueError('Assigned annotation identity differs: ' + field)
    if (case['state_sha256'] != digest(canonical(case['state']))
            or case['task_sha256'] != task_digest(case, packet)
            or case['rubric_sha256'] != packet['rubric_sha256']):
        raise ValueError('Assigned task content differs')
    reasons = row.get('rationales', {})
    for axis in AXES:
        label = row.get(axis)
        if not isinstance(label, str) or label not in packet['questions'][axis]['criteria']:
            raise ValueError('Unknown rubric label')
        if not isinstance(reasons, dict) or not isinstance(reasons.get(axis), str) or not reasons[axis].strip():
            raise ValueError('Both axes require nonempty rationales')
    sources = {'target': case['state']['target']['code']}
    for fragment in case['state']['bounded_context']['fragments']:
        sources[fragment['fragment_id']] = fragment.get('code', fragment.get('text'))
    evidence = row.get('evidence_quotes')
    if not isinstance(evidence, list):
        raise ValueError('Exact fragment-bound quotes required')
    covered = set()
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {'axis', 'fragment_id', 'quote'}:
            raise ValueError('Quote must identify its axis and exact fragment')
        text = item['quote']
        if (item['axis'] not in AXES or item['fragment_id'] not in sources
                or not isinstance(text, str) or not text.strip()
                or text not in sources[item['fragment_id']]):
            raise ValueError('Quote differs from its assigned fragment')
        covered.add(item['axis'])
    if covered != set(AXES):
        raise ValueError('Both axes require evidence')
    uncertainties = row.get('uncertainties')
    if (not isinstance(uncertainties, list)
            or any(not isinstance(u, str) or not u.strip() for u in uncertainties)):
        raise ValueError('Expected uncertainty strings')
    if (row['opportunity'] == 'needs_review' or row['concern_kind'] == 'unknown') and not uncertainties:
        raise ValueError('Abstention must explain material uncertainty')
    return {'status': 'annotation_provenance_validated_not_adjudicated', 'annotated_cases': 1,
            'semantic_correctness_verified': False, 'manual_rationale_checks': 'pending',
            'human_gold': False, 'metric_effect': 'none',
            'isolation_boundary': 'fresh_context_assignment_and_self_report_not_filesystem_enforcement'}


def validate_attempt(run, assignment, raw):
    outputs = preparation.verify(run)
    plan = outputs['dispatch-plan.json']
    if not isinstance(assignment, dict):
        raise ValueError('Expected attempt receipt object')
    selected = [a for a in plan['assignments'] if a['slot'] == assignment.get('slot')]
    if len(selected) != 1:
        raise ValueError('Unknown frozen assignment slot')
    expected = {'provider_requests': 0, 'human_gold': False, 'metric_effect': 'none',
                'reference_frozen_for_provider_scoring': False}
    for field, value in expected.items():
        if type(assignment.get(field)) is not type(value) or assignment[field] != value:
            raise ValueError('Attempt receipt invariant differs: ' + field)
    selected = selected[0]
    for name, source in (('packet.json', selected['packet']), ('template.json', selected['template'])):
        if assignment.get('input_file_sha256', {}).get(name) != digest(preparation.encoded(outputs[source])):
            raise ValueError('Attempt input binding differs')
    directory = assignment.get('directory')
    if not isinstance(directory, str):
        raise ValueError('Attempt directory must be recorded')
    prompt = preparation.PROMPT.format(directory=directory)
    if assignment.get('dispatched_prompt_sha256') != digest(prompt.encode()):
        raise ValueError('Attempt prompt binding differs')
    if assignment.get('raw_output_sha256') != digest(raw):
        raise ValueError('Retained raw output binding differs')
    result = validate_annotation(outputs[selected['packet']], outputs[selected['template']], json.loads(raw), assignment)
    return {**result, 'slot': selected['slot'], 'cell': selected['cell'],
            'provider_requests': assignment['provider_requests'], 'raw_output_sha256': digest(raw)}


def validate_preparation(run=preparation.RUN):
    outputs = preparation.verify(run)
    plan = outputs['dispatch-plan.json']
    task_counts = Counter(outputs[a['packet']]['cases'][0]['task_sha256'] for a in plan['assignments'])
    if sorted(task_counts.values()) != [3, 3, 3, 3]:
        raise ValueError('Expected four tasks with three independent repetitions')
    return {'status': 'preparation_validated_not_dispatched', 'distinct_tasks': 4,
            'fresh_contexts_planned': 12, 'case_annotations_planned': 12,
            'annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none',
            'semantic_correctness_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=preparation.RUN)
    parser.add_argument('--assignment', type=Path)
    parser.add_argument('--annotation', type=Path)
    args = parser.parse_args()
    if bool(args.assignment) != bool(args.annotation):
        parser.error('--assignment and --annotation must be supplied together')
    result = (validate_attempt(args.run, json.loads(args.assignment.read_text()), args.annotation.read_bytes())
              if args.annotation else validate_preparation(args.run))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
