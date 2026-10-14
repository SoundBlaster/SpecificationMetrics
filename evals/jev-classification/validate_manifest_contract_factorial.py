"""Validate frozen preparation or one retained annotation attempt offline."""
import argparse
from collections import Counter
import json
from pathlib import Path

import prepare_manifest_contract_balanced as preparation
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
    blanks = template['annotations']
    if (len(cases) != 4 or len(blanks) != 4 or not isinstance(rows, list)
            or len(rows) != 4 or any(not isinstance(r, dict) for r in rows)):
        raise ValueError('Expected four assigned annotations')
    ids = {c['case_id'] for c in cases}
    if (len(ids) != 4 or {r.get('case_id') for r in rows} != ids
            or {r.get('case_id') for r in blanks} != ids):
        raise ValueError('Assigned case set differs')
    for case in cases:
        blank = next(r for r in blanks if r['case_id'] == case['case_id'])
        row = next(r for r in rows if r['case_id'] == case['case_id'])
        validate_row(case, blank, row, packet)
    return {'status': 'annotation_provenance_validated_not_adjudicated', 'annotated_cases': 4,
            'semantic_correctness_verified': False, 'manual_rationale_checks': 'pending',
            'human_gold': False, 'metric_effect': 'none',
            'isolation_boundary': 'fresh_context_assignment_and_self_report_not_filesystem_enforcement'}


def validate_row(case, blank, row, packet):
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


def validate_delivery(run, assignment):
    """Check retained delivered bytes; this does not prove model consumption."""
    outputs = preparation.verify(run)
    if not isinstance(assignment, dict):
        raise ValueError('Expected attempt receipt object')
    selected = [a for a in outputs['dispatch-plan.json']['assignments'] if a['slot'] == assignment.get('slot')]
    if len(selected) != 1:
        raise ValueError('Unknown frozen assignment slot')
    selected = selected[0]
    directory = assignment.get('directory')
    if not isinstance(directory, str) or not Path(directory).is_absolute():
        raise ValueError('Attempt directory must be absolute and recorded')
    delivered = assignment.get('delivered_files')
    if not isinstance(delivered, dict) or set(delivered) != {'packet.json', 'template.json', 'prompt.txt'}:
        raise ValueError('Delivered file paths must be recorded')
    expected_bytes = {
        'packet.json': preparation.encoded(outputs[selected['packet']]),
        'template.json': preparation.encoded(outputs[selected['template']]),
        'prompt.txt': preparation.PROMPT.format(directory=directory).encode(),
    }
    for name, expected in expected_bytes.items():
        path = delivered[name]
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise ValueError('Delivered file path must be absolute: ' + name)
        try:
            actual = Path(path).read_bytes()
        except OSError as error:
            raise ValueError('Delivered file unavailable: ' + name) from error
        if actual != expected:
            raise ValueError('Delivered bytes differ: ' + name)
        recorded = (assignment.get('dispatched_prompt_sha256') if name == 'prompt.txt'
                    else assignment.get('input_file_sha256', {}).get(name))
        if recorded != digest(actual):
            raise ValueError('Attempt ' + ('prompt' if name == 'prompt.txt' else 'input') + ' binding differs')
    return {'status': 'delivery_bytes_verified_not_dispatched', 'slot': selected['slot'],
            'semantic_correctness_verified': False, 'metric_effect': 'none'}


def validate_attempt(run, assignment, raw):
    validate_delivery(run, assignment)
    outputs = preparation.verify(run)
    selected = next(a for a in outputs['dispatch-plan.json']['assignments'] if a['slot'] == assignment['slot'])
    expected = {'provider_requests': 0, 'human_gold': False, 'metric_effect': 'none',
                'reference_frozen_for_provider_scoring': False}
    for field, value in expected.items():
        if type(assignment.get(field)) is not type(value) or assignment[field] != value:
            raise ValueError('Attempt receipt invariant differs: ' + field)
    if assignment.get('raw_output_sha256') != digest(raw):
        raise ValueError('Retained raw output binding differs')
    result = validate_annotation(outputs[selected['packet']], outputs[selected['template']], json.loads(raw), assignment)
    return {**result, 'slot': selected['slot'], 'cases': selected['cases'],
            'provider_requests': assignment['provider_requests'], 'raw_output_sha256': digest(raw)}


def validate_preparation(run=preparation.RUN):
    outputs = preparation.verify(run)
    plan = outputs['dispatch-plan.json']
    task_counts = Counter(c['task_sha256'] for a in plan['assignments'] for c in outputs[a['packet']]['cases'])
    if len(task_counts) != 16 or set(task_counts.values()) != {3}:
        raise ValueError('Expected sixteen tasks with three independent repetitions')
    for assignment in plan['assignments']:
        if (len(assignment['cases']) != 4
                or len({c['case_id'] for c in assignment['cases']}) != 4
                or {c['cell'] for c in assignment['cases']} != {'01', '02', '03', '04'}):
            raise ValueError('Context must balance four distinct targets and modes')
    return {'status': 'preparation_validated_not_dispatched', 'distinct_tasks': 16,
            'fresh_contexts_planned': 12, 'case_annotations_planned': 48,
            'annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none',
            'semantic_correctness_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=preparation.RUN)
    parser.add_argument('--assignment', type=Path)
    parser.add_argument('--annotation', type=Path)
    parser.add_argument('--check-delivery', action='store_true')
    args = parser.parse_args()
    if args.check_delivery:
        if not args.assignment or args.annotation:
            parser.error('--check-delivery requires --assignment and forbids --annotation')
        result = validate_delivery(args.run, json.loads(args.assignment.read_text()))
    else:
        if bool(args.assignment) != bool(args.annotation):
            parser.error('--assignment and --annotation must be supplied together')
        result = (validate_attempt(args.run, json.loads(args.assignment.read_text()), args.annotation.read_bytes())
                  if args.annotation else validate_preparation(args.run))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
