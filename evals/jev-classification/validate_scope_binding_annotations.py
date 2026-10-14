"""Validate corrected scope-v3.1 delivery and retained answers offline."""
import argparse
import json
from pathlib import Path

import prepare_scope_binding_v3_1 as preparation
import validate_manifest_contract_factorial as shared
from question_grouping import canonical, digest

PROTOCOL = 'scope-binding-v3.1'
AXES = shared.AXES


def implementation_bindings(run):
    names = ('prepare_scope_binding_handoff.py', 'validate_scope_binding_annotations.py',
             'validate_manifest_contract_factorial.py')
    return {'protocol': PROTOCOL,
            'preparation_receipt_sha256': digest((run / 'preparation-receipt.json').read_bytes()),
            'implementation_file_sha256': {n: digest((preparation.ROOT / n).read_bytes()) for n in names}}


def case_bindings(outputs, assignment):
    result = []
    for entry, case in zip(assignment['cases'], outputs[assignment['packet']]['cases']):
        scope = case['state']['evaluation_scope']
        if case['scope_binding_sha256'] != digest(canonical(scope)):
            raise ValueError('Scope binding digest differs from case content')
        result.append({**entry, 'scope_unit': scope['unit'],
                       **{k: case[k] for k in ('state_sha256', 'task_sha256', 'rubric_sha256',
                                              'scope_binding_sha256')}})
    return result


def checked_delivery(run, receipt):
    outputs = preparation.verify(run)  # Never accept v2 or superseded v3.0.
    if not isinstance(receipt, dict):
        raise ValueError('Expected attempt receipt object')
    matches = [a for a in outputs['dispatch-plan.json']['assignments'] if a['slot'] == receipt.get('slot')]
    if len(matches) != 1:
        raise ValueError('Unknown frozen assignment slot')
    assignment = matches[0]
    for name, expected in implementation_bindings(run).items():
        if receipt.get(name) != expected:
            raise ValueError('Receipt protocol/implementation binding differs: ' + name)
    if receipt.get('cases') != case_bindings(outputs, assignment):
        raise ValueError('Receipt case/scope assignment differs')
    for name, expected in (('provider_requests', 0), ('human_gold', False), ('metric_effect', 'none'),
                           ('reference_frozen_for_provider_scoring', False)):
        if type(receipt.get(name)) is not type(expected) or receipt[name] != expected:
            raise ValueError('Receipt authority invariant differs: ' + name)
    directory = receipt.get('directory')
    if not isinstance(directory, str) or not Path(directory).is_absolute() or Path(directory).name != assignment['slot']:
        raise ValueError('Absolute annotator directory must match its slot')
    folder = Path(directory)
    expected_paths = {'packet.json': folder / 'packet.json', 'template.json': folder / 'template.json',
                      'prompt.txt': folder.parent / 'prompts' / (assignment['slot'] + '.txt')}
    paths, hashes = receipt.get('delivered_files'), receipt.get('input_file_sha256')
    if (not isinstance(paths, dict) or set(paths) != set(expected_paths)
            or not isinstance(hashes, dict) or set(hashes) != {'packet.json', 'template.json'}):
        raise ValueError('Exactly three delivered paths and two input hashes required')
    expected_bytes = {'packet.json': preparation.encoded(outputs[assignment['packet']]),
                      'template.json': preparation.encoded(outputs[assignment['template']]),
                      'prompt.txt': preparation.PROMPT.format(directory=directory).encode()}
    for name, expected in expected_bytes.items():
        path = paths[name]
        if not isinstance(path, str) or not Path(path).is_absolute() or Path(path) != expected_paths[name]:
            raise ValueError('Delivered path is not its declared dispatch file: ' + name)
        try:
            raw = Path(path).read_bytes()
        except OSError as error:
            raise ValueError('Delivered file unavailable: ' + name) from error
        if raw != expected:
            raise ValueError('Delivered bytes differ: ' + name)
        recorded = receipt.get('dispatched_prompt_sha256') if name == 'prompt.txt' else hashes[name]
        if recorded != digest(raw):
            raise ValueError('Recorded delivered hash differs: ' + name)
    return outputs, assignment


def validate_delivery(run, receipt):
    _, assignment = checked_delivery(run, receipt)
    return {'status': 'scope_delivery_bytes_verified_not_dispatched', 'slot': assignment['slot'],
            'protocol': PROTOCOL, 'scope_input_binding_verified': True,
            'semantic_correctness_verified': False, 'metric_effect': 'none'}


def validate_annotation(packet, template, annotation, receipt):
    if not isinstance(annotation, dict) or not isinstance(annotation.get('annotations'), list):
        raise ValueError('Expected structured annotations object')
    rows = annotation['annotations']
    expected = {c['case_id']: c for c in packet['cases']}
    if (len(rows) != len(expected) or any(not isinstance(r, dict) or not isinstance(r.get('case_id'), str) for r in rows)
            or {r['case_id'] for r in rows} != set(expected)):
        raise ValueError('Assigned case set differs')
    for row in rows:
        case = expected[row['case_id']]
        if (row.get('scope_unit') != case['state']['evaluation_scope']['unit']
                or row.get('scope_binding_sha256') != case['scope_binding_sha256']):
            raise ValueError('Returned scope acknowledgment differs')
    try:
        result = shared.validate_annotation(packet, template, annotation, receipt)
    except (TypeError, KeyError) as error:
        raise ValueError('Malformed annotation structure') from error
    return {**result, 'status': 'scope_annotation_provenance_validated_not_adjudicated',
            'scope_acknowledgments_verified': True, 'scope_semantic_fidelity_verified': False,
            'manual_scope_review': 'pending'}


def validate_attempt(run, receipt, raw):
    outputs, assignment = checked_delivery(run, receipt)
    if receipt.get('raw_output_sha256') != digest(raw):
        raise ValueError('Retained raw output binding differs')
    try:
        annotation = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ValueError('Raw output must be UTF-8 JSON') from error
    result = validate_annotation(outputs[assignment['packet']], outputs[assignment['template']], annotation, receipt)
    return {**result, 'protocol': PROTOCOL, 'slot': assignment['slot'], 'cases': receipt['cases'],
            'raw_output_sha256': digest(raw), 'provider_requests': receipt['provider_requests'],
            'model_runtime_identity_verified': False}


def validate_preparation(run=preparation.RUN):
    preparation.verify(run)
    return {'status': 'scope_handoff_available_not_dispatched', 'protocol': PROTOCOL,
            'fresh_contexts_planned': 12, 'case_annotations_planned': 48,
            'annotation_started': False, 'semantic_correctness_verified': False,
            'provider_requests': 0, 'metric_effect': 'none'}


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
