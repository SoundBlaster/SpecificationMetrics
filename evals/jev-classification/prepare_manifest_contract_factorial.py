"""Freeze twelve one-target tasks crossing documented contract and consumers."""
import argparse
import copy
import json
from pathlib import Path

from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest

ROOT = Path(__file__).parent
EVIDENCE = ROOT / 'runs/2026-10-14-manifest-contract-evidence'
RUN = ROOT / 'runs/2026-10-14-manifest-contract-factorial-preparation'
BASE_PACKET = ROOT / 'runs/2026-10-13-definition-owner-names-preparation/packet-annotator-13.json'
CATALOG_SHA = 'c07d73baf845e6b564732033fe8b8650ec4404b1d368156f4d470046dd7ecf02'
EVIDENCE_RECEIPT_SHA = '4af7bad9d5fff9fcd1a80b7cf30a355679991effdda029391b0b8eeaff893ab1'
CONDITIONS = (
    {'cell': '01', 'documents': False, 'consumers': False},
    {'cell': '02', 'documents': True, 'consumers': False},
    {'cell': '03', 'documents': False, 'consumers': True},
    {'cell': '04', 'documents': True, 'consumers': True},
)
PROMPT = '''Independently annotate the ONE exact Python expression in your assigned packet, using only its target, bounded_context, architecture_profile and complete supplied rubric/questions. You have no author labels or provider predictions. Read ONLY {directory}/packet.json and {directory}/template.json; do not inspect repository files, other packets, memory, earlier sessions, study plans, source mappings, network, environment or credentials. Classify opportunity and concern_kind independently. Judge the entire target; do not silently replace it with a clause or classify the whole containing function. Keep material uncertainty and do not invent omitted contracts, ownership or effects. Document fragments are documentary evidence at their stated authority, not Python code or canonical Requirements by implication. Save strict JSON to {directory}/annotations.json. Preserve every template case_id/state_sha256/task_sha256/rubric_sha256. Replace null labels, provide nonempty rationales for both axes, and an uncertainties list of strings. Provide exact contiguous evidence quotes from this case's target.code or fragment code/text for BOTH axes; each quote has axis, fragment_id (target or the supplied fragment ID) and quote keys. Set status to independently_annotated_not_adjudicated and isolation_report with input_files containing exactly the two assigned absolute paths and other_inputs_read false, or disclose deviations truthfully. Write only annotations.json. Use a non-login shell and prefix commands with rtk (rtk proxy for raw tools). Do not invoke agents or recursive delegation, alter Git/PR state or access credentials. Return the output path and limitations.'''


def encoded(value):
    return value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()


def inputs():
    catalog_file, receipt_file = EVIDENCE / 'evidence-bundles.json', EVIDENCE / 'evidence-receipt.json'
    if digest(catalog_file.read_bytes()) != CATALOG_SHA or digest(receipt_file.read_bytes()) != EVIDENCE_RECEIPT_SHA:
        raise ValueError('Frozen evidence selection differs')
    receipt = json.loads(receipt_file.read_text())
    for path, sha in receipt['input_file_sha256'].items():
        if digest((ROOT / path).read_bytes()) != sha:
            raise ValueError('Evidence source input differs: ' + path)
    for name, sha in receipt['artifact_file_sha256'].items():
        if digest((EVIDENCE / name).read_bytes()) != sha:
            raise ValueError('Evidence artifact differs: ' + name)
    packet = json.loads(BASE_PACKET.read_text())
    base = next(c for c in packet['cases'] if c['case_id'] == 'probe-c')
    catalog = json.loads(catalog_file.read_text())
    if (digest(canonical(base['state'])) != catalog['baseline_state_sha256']
            or base['state']['target'] != catalog['target']
            or [f['code'] for f in catalog['base_fragments']]
            != [f['code'] for f in base['state']['bounded_context']['fragments']]):
        raise ValueError('Original parser baseline differs')
    return catalog, packet, base


def build():
    catalog, original, base = inputs()
    metadata = {k: copy.deepcopy(v) for k, v in original.items() if k != 'cases'}
    metadata['annotation_prompt_sha256'] = digest(PROMPT.encode())
    outputs, cases, mapping = {}, {}, []
    for condition in CONDITIONS:
        state = copy.deepcopy(base['state'])
        selected = catalog['base_fragments'] + (catalog['document_fragments'] if condition['documents'] else []) + (catalog['consumer_fragments'] if condition['consumers'] else [])
        fragments = state['bounded_context']['fragments']
        for item in selected[4:]:
            fragment = {k: copy.deepcopy(item[k]) for k in ('kind', 'code', 'text', 'authority', 'language') if k in item}
            fragments.append({'fragment_id': f'fragment-{len(fragments) + 1:02d}', **fragment})
        case = {'case_id': 'target-01', 'state': state, 'state_sha256': digest(canonical(state)),
                'rubric_sha256': metadata['rubric_sha256']}
        case['task_sha256'] = task_digest(case, metadata)
        cases[condition['cell']] = case
        mapping.append({**condition, 'case_id': case['case_id'], 'state_sha256': case['state_sha256'],
                        'task_sha256': case['task_sha256'],
                        'fragments': [{'fragment_id': f'fragment-{i:02d}', **item['origin']}
                                      for i, item in enumerate(selected, 1)]})
    assignments = []
    # Interleave all four cells within each repetition; no cell block is tied
    # to one wave. Dispatch ordering is deterministic, not randomized.
    for repetition in range(3):
        for offset in range(4):
            cell = CONDITIONS[(offset + repetition) % 4]['cell']
            slot = f'annotator-{len(assignments) + 1:02d}'
            packet = {**metadata, 'cases': [cases[cell]]}
            template = {'status': 'blank_not_reference', 'annotations': [
                {**{k: cases[cell][k] for k in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256')},
                 'opportunity': None, 'concern_kind': None,
                 'rationales': {'opportunity': '', 'concern_kind': ''},
                 'evidence_quotes': [], 'uncertainties': []}]}
            outputs[f'packet-{slot}.json'] = packet
            outputs[f'template-{slot}.json'] = template
            assignments.append({'slot': slot, 'cell': cell, 'repetition': repetition + 1,
                                'packet': f'packet-{slot}.json', 'template': f'template-{slot}.json',
                                'agent_task': None, 'directory': None, 'annotation_output': None})
    rubric_path = ROOT / 'runs/2026-10-13-definition-owner-names-preparation/rubric.json'
    outputs['rubric.json'] = rubric_path.read_bytes()
    outputs['annotation-prompt.txt'] = PROMPT.encode()
    outputs['upstream-LICENSE.txt'] = (EVIDENCE / 'upstream-LICENSE.txt').read_bytes()
    outputs['dispatch-plan.json'] = {'status': 'prepared_not_dispatched', 'fresh_contexts_planned': 12,
                                    'targets_per_context': 1, 'case_annotations_planned': 12,
                                    'contexts_per_cell': 3, 'assignments': assignments,
                                    'provider_requests': 0, 'metric_effect': 'none'}
    outputs['source-mapping.json'] = {'status': 'integrator_only_not_for_annotation',
                                     'source_revision': catalog['source_revision'], 'conditions': mapping}
    outputs['study-plan.json'] = {
        'status': 'prospective_diagnostic_not_gold', 'conditions': list(CONDITIONS),
        'target': catalog['target'], 'source_revision': catalog['source_revision'],
        'fixed': ['exact whole expression', 'original parser baseline', 'architecture profile',
                  'rubric questions and label criteria', 'owner names'],
        'prospective_checks': {
            'H_contract': 'In the six document-present responses, no rationale asserts that a documented fail-closed traversal requirement is unavailable. Missing canonical adoption or canonical-spelling justification remains allowed. Manual review, not a fixed-label expectation.',
            'H_consumers': 'In the six consumer-present responses, no rationale denies the supplied local-read/scoped-copy/HTTPS path uses or the shared staging_prefix use. Responses need not enumerate every use; unresolved primary responsibility remains allowed. Manual review.',
            'H_target_fidelity': 'All twelve explanations preserve the entire BoolOp and do not attribute symlink resolution, physical containment proof, digest verification, public-safe content, manifest membership, URL encoding or publication approval to this predicate itself. Distinguish consumer effects. Manual review.',
            'H_traceability': 'All twelve outputs retain the assigned identities, case-local exact evidence for both axes and truthfully declared input scope. Formal validation does not grade semantic support.'},
        'reporting': ['Per-cell opportunity/concern histograms and decisive coverage with denominator three.',
                      'Within-cell repetitions and disagreements; abstentions are unknown, not errors.',
                      'Compare 01↔02 and 03↔04 for documents; 01↔03 and 02↔04 for consumers.',
                      'Record all failed manual criteria and evidence for any proposed adjudication without editing raw outputs.'],
        'limits': ['One hand-selected source target; twelve judgments are not twelve source targets.',
                   'Common model bias and small samples; no statistical/causal significance claim.',
                   'Evidence additions differ in length; no equal-length placebo, so semantics and context length are not isolated.',
                   'Deterministic interleaving is not random allocation and does not eliminate temporal/model drift.',
                   'Context and bookkeeping prompt differ from the previous run; no unchanged-input replication claim.',
                   'Implemented proposal/operator documentation is not a canonical Requirement or human gold.',
                   'The selected whole expression may retain mixed policy/mechanics responsibility.'],
        'annotation_started': False, 'human_gold': False, 'provider_requests': 0,
        'author_labels_in_packets': False, 'reference_frozen_for_provider_scoring': False, 'metric_effect': 'none'}
    source_inputs = [EVIDENCE / 'evidence-bundles.json', EVIDENCE / 'evidence-receipt.json', BASE_PACKET, rubric_path]
    outputs['preparation-receipt.json'] = {
        'status': 'prepared_not_dispatched', 'schema_version': 1,
        'input_file_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in source_inputs},
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {name: digest(encoded(value)) for name, value in outputs.items()},
        'distinct_tasks': 4, 'fresh_contexts_planned': 12, 'case_annotations_planned': 12,
        'provider_requests': 0, 'metric_effect': 'none'}
    return outputs


def verify(run=RUN):
    outputs = build()
    if {p.name for p in run.iterdir()} != set(outputs):
        raise ValueError('Preparation file set differs')
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Frozen manifest factorial preparation differs: ' + name)
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
    print(json.dumps({'distinct_tasks': 4, 'fresh_contexts_planned': 12,
                      'annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none'}))


if __name__ == '__main__':
    main()
