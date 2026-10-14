"""Freeze balanced v2 packets; preserve unexecuted one-target v1 unchanged."""
import argparse
import copy
import json
from pathlib import Path

import prepare_manifest_contract_factorial as legacy
from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest

ROOT = legacy.ROOT
EVIDENCE = ROOT / 'runs/2026-10-14-manifest-contract-balanced-evidence-v2'
RUN = ROOT / 'runs/2026-10-14-manifest-contract-balanced-preparation-v2'
CATALOG_SHA = '31d36ec52e81a74c60fd070c601f9fc50f3cceed79680273bd730ad24dfd29e2'
CONDITIONS = legacy.CONDITIONS
encoded = legacy.encoded
PROMPT = legacy.PROMPT.replace('the ONE exact Python expression', 'the FOUR distinct exact Python expressions').replace(
    'only its target, bounded_context', 'only each case\'s own target, bounded_context').replace(
    'Judge the entire target;', 'Do not transfer evidence between cases. Judge each entire target;')


def build():
    legacy.verify()  # Historical v1 artifacts and producer remain byte-identical.
    catalog_path = EVIDENCE / 'evidence-bundles.json'
    if digest(catalog_path.read_bytes()) != CATALOG_SHA:
        raise ValueError('Balanced source selection differs')
    catalog = json.loads(catalog_path.read_text())
    _, original, base = legacy.inputs()
    metadata = {k: copy.deepcopy(v) for k, v in original.items() if k != 'cases'}
    metadata['annotation_prompt_sha256'] = digest(PROMPT.encode())
    cases, mapping = {}, []
    for target in catalog['targets']:
        for condition in CONDITIONS:
            selected = (target['base_fragments']
                        + (target['document_fragments'] if condition['documents'] else [])
                        + (target['consumer_fragments'] if condition['consumers'] else []))
            fragments = []
            for i, item in enumerate(selected, 1):
                fields = ('code',) if i <= len(target['base_fragments']) else ('kind', 'code', 'text', 'authority', 'language')
                fragments.append({'fragment_id': f'fragment-{i:02d}',
                                  **{k: copy.deepcopy(item[k]) for k in fields if k in item}})
            state = {'architecture_profile': copy.deepcopy(base['state']['architecture_profile']),
                     'target': target['target'],
                     'bounded_context': {**copy.deepcopy(base['state']['bounded_context']), 'fragments': fragments}}
            case = {'case_id': target['case_id'], 'state': state, 'state_sha256': digest(canonical(state)),
                    'rubric_sha256': metadata['rubric_sha256']}
            case['task_sha256'] = task_digest(case, metadata)
            cases[(target['case_id'], condition['cell'])] = case
            mapping.append({'case_id': target['case_id'], 'family': target['family'], **condition,
                            'state_sha256': case['state_sha256'], 'task_sha256': case['task_sha256'],
                            'fragments': [{'fragment_id': f'fragment-{i:02d}', **f['origin']}
                                          for i, f in enumerate(selected, 1)]})
    outputs, assignments = {}, []
    # XOR forms the four-element group. Excluding the GF(4) permutation
    # [0,2,3,1] from the complete 4x4 schedule gives 12 contexts with BOTH
    # target-position and condition-position counts exactly three.
    excluded_order = (0, 2, 3, 1)
    for repetition in range(3):
        for mode in range(4):
            order = [o for o in range(4) if o != excluded_order[mode]][repetition]
            selected = [(catalog['targets'][position ^ order]['case_id'],
                         CONDITIONS[(position ^ order) ^ mode]['cell']) for position in range(4)]
            slot = f'annotator-{len(assignments) + 1:02d}'
            packet = {**metadata, 'cases': [cases[key] for key in selected]}
            template = {'status': 'blank_not_reference', 'annotations': [
                {**{k: c[k] for k in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256')},
                 'opportunity': None, 'concern_kind': None, 'rationales': {'opportunity': '', 'concern_kind': ''},
                 'evidence_quotes': [], 'uncertainties': []} for c in packet['cases']]}
            outputs[f'packet-{slot}.json'] = packet
            outputs[f'template-{slot}.json'] = template
            assignments.append({'slot': slot, 'repetition': repetition + 1,
                                'packet': f'packet-{slot}.json', 'template': f'template-{slot}.json',
                                'agent_task': None, 'directory': None, 'annotation_output': None,
                                'cases': [{'case_id': cid, 'cell': cell, 'position': i + 1}
                                          for i, (cid, cell) in enumerate(selected)]})
    outputs['rubric.json'] = (legacy.RUN / 'rubric.json').read_bytes()
    outputs['annotation-prompt.txt'] = PROMPT.encode()
    outputs['upstream-LICENSE.txt'] = (EVIDENCE / 'upstream-LICENSE.txt').read_bytes()
    outputs['dispatch-plan.json'] = {'status': 'prepared_not_dispatched', 'version': 2,
                                    'fresh_contexts_planned': 12, 'targets_per_context': 4,
                                    'case_annotations_planned': 48, 'contexts_per_target_cell': 3,
                                    'assignments': assignments, 'provider_requests': 0, 'metric_effect': 'none'}
    outputs['source-mapping.json'] = {'status': 'integrator_only_not_for_annotation',
                                     'source_revision': catalog['source_revision'], 'conditions': mapping}
    study = copy.deepcopy(legacy.build()['study-plan.json'])
    study.update(version=2, focal_target='target-01', control_targets=['target-02', 'target-03', 'target-04'],
                 fresh_contexts_planned=12, case_annotations_planned=48,
                 assignment='Each fresh context receives all four conditions across four distinct targets, one view per target. Every target-cell and target/condition position has three repetitions.')
    study['prospective_checks']['H_contract'] += ' This manual interpretation check applies only to target-01.'
    study['prospective_checks']['H_consumers'] += ' This manual interpretation check applies only to target-01.'
    study['prospective_checks']['H_target_fidelity'] += ' Operational capability prohibitions apply to target-01; all other cases must preserve their own exact target boundaries.'
    study['prospective_checks']['H_traceability'] = 'All 48 rows retain assigned identities, case-local quotes for both axes and declared isolation. Formal validation does not grade semantic support.'
    study['reporting'].append('Report controls separately; their documentary/consumer additions are target-specific and must not be pooled into a common treatment effect.')
    study['limits'] += ['Balanced mixtures remove one-mode-per-context assignment, not every annotator/target confound or common model bias.',
                       'Control cases can prime interpretation indirectly; no direct focal path-helper or documented manifest contract appears in control bundles.',
                       'The BDD document is a review-only draft and must not be treated as canonical adoption.']
    outputs['study-plan.json'] = study
    outputs['supersession.json'] = {'status': 'v1_superseded_before_dispatch_not_failed_model_run',
                                    'prior_preparation': '../' + legacy.RUN.name,
                                    'prior_receipt_sha256': digest((legacy.RUN / 'preparation-receipt.json').read_bytes()),
                                    'reason': 'PR #52 review identified one-mode-per-context assignment contrary to AGENTS.md. V1 artifacts and producer are preserved; no annotations existed.',
                                    'prior_annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none'}
    inputs = [catalog_path, legacy.RUN / 'preparation-receipt.json', ROOT / 'prepare_manifest_contract_factorial.py']
    outputs['preparation-receipt.json'] = {
        'status': 'prepared_not_dispatched', 'schema_version': 2,
        'input_file_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in inputs},
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {n: digest(encoded(v)) for n, v in outputs.items()},
        'distinct_tasks': 16, 'fresh_contexts_planned': 12, 'case_annotations_planned': 48,
        'provider_requests': 0, 'metric_effect': 'none'}
    return outputs


def verify(run=RUN):
    outputs = build()
    if {p.name for p in run.iterdir()} != set(outputs):
        raise ValueError('Balanced preparation file set differs')
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Frozen balanced preparation differs: ' + name)
    return outputs


def write(run):
    outputs = build()
    run.mkdir(parents=True, exist_ok=False)
    for name, value in outputs.items():
        with (run / name).open('xb') as stream:
            stream.write(encoded(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    write(args.run) if args.write else verify(args.run)
    print(json.dumps({'distinct_tasks': 16, 'fresh_contexts_planned': 12,
                      'case_annotations_planned': 48, 'annotation_started': False, 'provider_requests': 0}))


if __name__ == '__main__':
    main()
