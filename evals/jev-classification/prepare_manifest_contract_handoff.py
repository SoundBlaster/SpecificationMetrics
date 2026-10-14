"""Prepare scoped delivery folders and blank receipts; never launch inference."""
import argparse
import json
from pathlib import Path

import prepare_manifest_contract_factorial as preparation
from question_grouping import digest


def review_template(plan):
    criteria = {}
    for name, cells in (('H_contract', ('02', '04')), ('H_consumers', ('03', '04')),
                        ('H_target_fidelity', ('01', '02', '03', '04'))):
        criteria[name] = {'status': 'pending_manual_review', 'met': None,
                          'entries': [{'slot': a['slot'], 'cell': a['cell'], 'case_id': 'target-01',
                                       'raw_output_sha256': None, 'criterion_met': None,
                                       'supporting_quote': None, 'review_note': None}
                                      for a in plan['assignments'] if a['cell'] in cells]}
    return {'status': 'blank_manual_review_not_result', 'criteria': criteria,
            'reviewer': None, 'human_gold': False, 'reference_frozen_for_provider_scoring': False,
            'metric_effect': 'none'}


def materialize(destination, run=preparation.RUN):
    outputs = preparation.verify(run)
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    prompts, receipts = destination / 'prompts', destination / 'receipts'
    prompts.mkdir(); receipts.mkdir()
    assignments = []
    for a in outputs['dispatch-plan.json']['assignments']:
        directory = destination / a['slot']
        directory.mkdir()
        hashes = {}
        for alias, source in (('packet.json', a['packet']), ('template.json', a['template'])):
            raw = preparation.encoded(outputs[source])
            with (directory / alias).open('xb') as stream:
                stream.write(raw)
            hashes[alias] = digest(raw)
        prompt = preparation.PROMPT.format(directory=directory)
        (prompts / (a['slot'] + '.txt')).write_text(prompt)
        receipt = {'slot': a['slot'], 'directory': str(directory), 'context_inheritance': None,
                   'context_inheritance_planned': 'none', 'agent_task': None,
                   'model_identity': 'not_dispatched_inherit_default_if_authorized',
                   'input_file_sha256': hashes, 'dispatched_prompt_sha256': digest(prompt.encode()),
                   'raw_output_sha256': None, 'provider_requests': 0,
                   'human_gold': False, 'metric_effect': 'none',
                   'reference_frozen_for_provider_scoring': False}
        (receipts / (a['slot'] + '.json')).write_bytes(preparation.encoded(receipt))
        assignments.append({'slot': a['slot'], 'cell': a['cell'], 'repetition': a['repetition'],
                            'directory': str(directory), 'prompt': 'prompts/' + a['slot'] + '.txt',
                            'attempt_receipt': 'receipts/' + a['slot'] + '.json'})
    review = review_template(outputs['dispatch-plan.json'])
    (destination / 'semantic-review.template.json').write_bytes(preparation.encoded(review))
    receipt = {'status': 'delivery_prepared_not_dispatched', 'annotation_started': False,
               'preparation_receipt_sha256': digest((run / 'preparation-receipt.json').read_bytes()),
               'producer_sha256': digest(Path(__file__).read_bytes()),
               'assignments': assignments, 'retained_attempts': [], 'excluded_attempts': [],
               'provider_requests': 0, 'metric_effect': 'none', 'human_gold': False,
               'reference_frozen_for_provider_scoring': False,
               'isolation_boundary': 'planned_fresh_context_and_scoped_files_not_filesystem_enforcement'}
    (destination / 'delivery-receipt.json').write_bytes(preparation.encoded(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=preparation.RUN)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    preparation.verify(args.run)
    receipt = materialize(args.destination, args.run) if args.destination else None
    print(json.dumps({'status': 'delivery_prepared_not_dispatched' if receipt else 'handoff_preview_only',
                      'fresh_contexts_planned': 12, 'annotation_started': False,
                      'provider_requests': 0, 'metric_effect': 'none'}, indent=2))


if __name__ == '__main__':
    main()
