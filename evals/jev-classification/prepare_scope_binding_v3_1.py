"""Preserve unpublished v3.0 history; prepare corrected scope-input contract v3.1."""
import argparse
import copy
import json
from pathlib import Path

import prepare_scope_binding_diagnostic as historical
from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest

ROOT = historical.ROOT
RUN = ROOT / 'runs/2026-10-14-scope-binding-preparation-v3-1'
encoded = historical.encoded
PROMPT = (
    'Independently annotate the FOUR exact Python expressions in your packet. '
    'The permitted semantic inputs are ONLY each case\'s state.target, '
    'state.bounded_context, state.architecture_profile, state.evaluation_scope '
    '(including its unit, definition and application_binding), and the supplied '
    'complete rubric/questions. ' + historical.SCOPE_INSTRUCTION +
    'Read ONLY {directory}/packet.json and {directory}/template.json. '
    'Do not read repository files, other packets, memory, previous sessions, '
    'study plans, source mappings, network, environment or credentials. '
    'Do not transfer evidence between cases or inspect author labels or predictions. '
    'Classify opportunity and concern_kind independently for the whole exact '
    'target, retaining material uncertainty and documentary authority. '
    'Do not invent omitted contracts, ownership, effects or runtime execution. '
    'Save strict JSON to {directory}/annotations.json. Preserve every template '
    'case_id/state_sha256/task_sha256/rubric_sha256/scope_unit/scope_binding_sha256. '
    'Replace null labels, give nonempty rationales for both axes explicitly '
    'identifying the selected unit, and an uncertainties list of strings. '
    'For BOTH axes supply exact contiguous evidence quotes from that case\'s '
    'target.code or bounded_context fragment code/text, with axis, fragment_id '
    '(target or supplied fragment ID), and quote keys. '
    'Set status to independently_annotated_not_adjudicated. Set isolation_report '
    'input_files to exactly the two assigned absolute paths and other_inputs_read '
    'false, or truthfully disclose deviations. Write only annotations.json. '
    'Use a non-login shell; prefix commands with rtk (rtk proxy for raw tools). '
    'Do not invoke agents, change Git/PR state or access credentials. '
    'Return the output path and limitations.'
)


def build():
    outputs = copy.deepcopy(historical.verify())
    rubric = json.loads(outputs['rubric.json'])
    rubric.update(id='specification_metrics.expression-fit.v3.1-scope-diagnostic', version='3.1',
                  supersedes=rubric['id'])
    outputs['rubric.json'] = encoded(rubric)
    outputs['annotation-prompt.txt'] = PROMPT.encode()
    tasks = {}
    for assignment in outputs['dispatch-plan.json']['assignments']:
        packet = outputs[assignment['packet']]
        packet.update(rubric_id=rubric['id'], rubric_sha256=digest(outputs['rubric.json']),
                      annotation_prompt_sha256=digest(PROMPT.encode()))
        blanks = []
        for entry, case in zip(assignment['cases'], packet['cases']):
            scope = case['state']['evaluation_scope']
            case.update(rubric_sha256=packet['rubric_sha256'],
                        scope_binding_sha256=digest(canonical(scope)))
            case['task_sha256'] = task_digest(case, packet)
            tasks[entry['case_id'], entry['cell']] = case['task_sha256']
            blanks.append({**{k: case[k] for k in ('case_id', 'state_sha256', 'task_sha256',
                                                  'rubric_sha256', 'scope_binding_sha256')},
                           'scope_unit': scope['unit'], 'opportunity': None, 'concern_kind': None,
                           'rationales': {'opportunity': '', 'concern_kind': ''},
                           'evidence_quotes': [], 'uncertainties': []})
        outputs[assignment['template']]['annotations'] = blanks
    for row in outputs['source-mapping.json']['conditions']:
        row.update(task_sha256=tasks[row['case_id'], row['cell']])
    outputs['dispatch-plan.json']['version'] = '3.1'
    outputs['study-plan.json'].update(version='3.1',
        contract_correction='Allowed-input list explicitly includes evaluation_scope; structured scope acknowledgments are identity checks, not semantic judgment.')
    outputs['supersession.json'] = {
        'status': 'v3_0_superseded_before_annotation_not_failed_model_run',
        'prior_receipt_sha256': digest((historical.RUN / 'preparation-receipt.json').read_bytes()),
        'reason': 'PR #57 review: prefixed scope instruction conflicted with inherited exhaustive allowed-input list.',
        'prior_annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none'}
    del outputs['preparation-receipt.json']
    inputs = (historical.RUN / 'preparation-receipt.json', Path(historical.__file__))
    outputs['preparation-receipt.json'] = {
        'schema_version': '3.1', 'status': 'prepared_not_dispatched',
        'input_file_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in inputs},
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {n: digest(encoded(v)) for n, v in outputs.items()},
        'distinct_tasks': 16, 'fresh_contexts_planned': 12, 'case_annotations_planned': 48,
        'annotation_started': False, 'dispatch_ready': False,
        'provider_requests': 0, 'metric_effect': 'none', 'human_gold': False}
    return outputs


def verify(run=RUN):
    outputs = build()
    if {p.name for p in run.iterdir()} != set(outputs):
        raise ValueError('Scope v3.1 file set differs')
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Frozen scope v3.1 differs: ' + name)
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
    print(json.dumps({'status': 'prepared_not_dispatched', 'version': '3.1', 'provider_requests': 0}))


if __name__ == '__main__':
    main()
