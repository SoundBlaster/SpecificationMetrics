"""Materialize corrected scope-v3.1 inputs and pending receipts without inference."""
import argparse
import json
from pathlib import Path

import prepare_scope_binding_v3_1 as preparation
import validate_scope_binding_annotations as validation


def review_template(outputs):
    entries = []
    for assignment in outputs['dispatch-plan.json']['assignments']:
        for binding in validation.case_bindings(outputs, assignment):
            entries.append({'slot': assignment['slot'], **binding, 'raw_output_sha256': None,
                            'criterion_met': None, 'review_note': None,
                            'rationale_quotes': {axis: None for axis in validation.AXES}})
    # Each criterion gets its own objects; filling one must not mutate another.
    return {'status': 'blank_manual_review_not_result', 'reviewer': None,
            'criteria': {name: {'status': 'pending_manual_review', 'met': None,
                                'entries': json.loads(json.dumps(entries))}
                         for name in ('scope_fidelity', 'role_witness', 'ownership')},
            'formal_traceability': {'status': 'pending_attempt_validation', 'validated_attempts': [],
                                   'expected_attempts': 12},
            'human_gold': False, 'metric_effect': 'none', 'labels_adjudicated': False,
            'reference_frozen_for_provider_scoring': False}


def materialize(destination, run=preparation.RUN):
    outputs = preparation.verify(run)
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'prompts').mkdir()
    (destination / 'receipts').mkdir()
    deliveries = []
    protocol = validation.implementation_bindings(run)
    for assignment in outputs['dispatch-plan.json']['assignments']:
        slot = assignment['slot']
        folder = destination / slot
        folder.mkdir()
        paths = {'packet.json': folder / 'packet.json', 'template.json': folder / 'template.json',
                 'prompt.txt': destination / 'prompts' / (slot + '.txt')}
        contents = {'packet.json': preparation.encoded(outputs[assignment['packet']]),
                    'template.json': preparation.encoded(outputs[assignment['template']]),
                    'prompt.txt': preparation.PROMPT.format(directory=folder).encode()}
        for name, raw in contents.items():
            with paths[name].open('xb') as stream:
                stream.write(raw)
        receipt = {**protocol, 'slot': slot, 'directory': str(folder),
                   'cases': validation.case_bindings(outputs, assignment),
                   'delivered_files': {n: str(p) for n, p in paths.items()},
                   'input_file_sha256': {n: validation.digest(paths[n].read_bytes()) for n in ('packet.json', 'template.json')},
                   'dispatched_prompt_sha256': validation.digest(paths['prompt.txt'].read_bytes()),
                   'raw_output_sha256': None, 'context_inheritance': None,
                   'context_inheritance_planned': 'none', 'agent_task': None,
                   'requested_model': None, 'requested_reasoning_effort': None,
                   'runtime_model_identity': None, 'provider_requests': 0,
                   'human_gold': False, 'metric_effect': 'none',
                   'reference_frozen_for_provider_scoring': False}
        validation.validate_delivery(run, receipt)
        receipt_path = destination / 'receipts' / (slot + '.json')
        receipt_path.write_bytes(preparation.encoded(receipt))
        deliveries.append({'slot': slot, 'directory': str(folder), 'cases': receipt['cases'],
                           'prompt': 'prompts/' + slot + '.txt', 'attempt_receipt': 'receipts/' + slot + '.json'})
    (destination / 'semantic-review.template.json').write_bytes(preparation.encoded(review_template(outputs)))
    receipt = {**protocol, 'status': 'scope_delivery_prepared_not_dispatched', 'annotation_started': False,
               'assignments': deliveries, 'retained_attempts': [], 'excluded_attempts': [],
               'preparation_stage_dispatch_ready': outputs['preparation-receipt.json']['dispatch_ready'],
               'scope_handoff_available': True, 'semantic_grader_implemented': False,
               'provider_requests': 0, 'metric_effect': 'none', 'human_gold': False,
               'reference_frozen_for_provider_scoring': False,
               'isolation_boundary': 'scoped_assignment_and_self_report_not_filesystem_enforcement'}
    (destination / 'delivery-receipt.json').write_bytes(preparation.encoded(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=preparation.RUN)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    preparation.verify(args.run)
    receipt = materialize(args.destination, args.run) if args.destination else None
    print(json.dumps({'status': receipt['status'] if receipt else 'scope_handoff_preview_only',
                      'protocol': validation.PROTOCOL, 'fresh_contexts_planned': 12,
                      'case_annotations_planned': 48, 'annotation_started': False,
                      'provider_requests': 0, 'metric_effect': 'none'}, indent=2))


if __name__ == '__main__':
    main()
