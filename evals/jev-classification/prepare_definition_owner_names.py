"""Prepare an offline, balanced context/owner-name diagnostic from pinned source."""
import argparse
import ast
import copy
import io
import json
from pathlib import Path
import textwrap
import tokenize

import prepare_bdd_steps_balanced_factorial as previous
from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest

ROOT = Path(__file__).parent
RUN = ROOT / 'runs/2026-10-13-definition-owner-names-preparation'
AUDIT = RUN / 'source-audit.json'
AUDIT_SHA256 = '16d6db3a6d07382d192950ca7417c301b30ddff81da02f8222233d05fb07c8ea'
CONDITIONS = (
    {'cell': '01', 'additional_context': False, 'neutral_owner_names': False},
    {'cell': '02', 'additional_context': True, 'neutral_owner_names': False},
    {'cell': '03', 'additional_context': False, 'neutral_owner_names': True},
    {'cell': '04', 'additional_context': True, 'neutral_owner_names': True},
)
FOCAL_RENAMES = {
    'BDDPolicy': 'RuleBase', 'BDDScenarioValuesSpec': 'RuleA',
    'BDDScenarioFieldsSpec': 'RuleB', 'BDDProfileSelectionSpec': 'RuleC',
    'BDDContainerPresenceSpec': 'RuleD', 'BDDScenarioIDsSpec': 'RuleE',
    'BDDScenarioReferencesSpec': 'RuleF', 'POLICIES': 'RULES',
    'PolicyOutcome': 'RuleOutcome', 'policy': 'rule',
}
PROMPT = b'''Independently annotate the four distinct exact Python expressions in ONE packet, using only each case's target, bounded_context, architecture_profile and questions. Do not transfer evidence between cases. You have no author labels or provider predictions. Read ONLY {directory}/packet.json and {directory}/template.json; do not inspect other packets, repository files, memory, earlier sessions, source mappings, network, environment or credentials. Classify opportunity and concern_kind independently according to the complete supplied rubric. Preserve material ambiguity and do not invent omitted facts. Save strict JSON to {directory}/annotations.json. Preserve every template case_id/state_sha256/task_sha256/rubric_sha256. Replace null labels; provide nonempty rationales for both axes, exact contiguous target/context code evidence quotes for both axes, and an uncertainties list of strings. Each quote object has axis and quote keys. Set top status to independently_annotated_not_adjudicated and isolation_report with input_files containing exactly the two assigned absolute paths and other_inputs_read false, or disclose deviations truthfully. Write only annotations.json. Use a non-login shell and prefix commands with rtk (rtk proxy for raw tools). Do not invoke other agents or recursive delegation. Return the saved output path and limitations.'''


def encoded(value):
    return value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()


def rename_identifiers(code, mapping):
    """Change NAME token spans only, preserving strings, comments and whitespace."""
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    names = {t.string for t in tokens if t.type == tokenize.NAME}
    if len(set(mapping.values())) != len(mapping) or names & set(mapping.values()):
        raise ValueError('Renaming would collide with an existing identifier')
    offsets, total = [], 0
    for line in code.splitlines(keepends=True):
        offsets.append(total)
        total += len(line)
    edits = [(offsets[t.start[0] - 1] + t.start[1],
              offsets[t.end[0] - 1] + t.end[1], mapping[t.string])
             for t in tokens if t.type == tokenize.NAME and t.string in mapping]
    for start, end, replacement in reversed(edits):
        code = code[:start] + replacement + code[end:]
    return code


def transformed(code, mapping):
    result = rename_identifiers(code, mapping)
    restored = rename_identifiers(result, {v: k for k, v in mapping.items()})
    if restored != code:
        raise ValueError('Owner-name transformation is not reversible')
    if ast.dump(ast.parse(textwrap.dedent(restored))) != ast.dump(ast.parse(textwrap.dedent(code))):
        raise ValueError('Restored source AST differs')
    return result


def build():
    if digest(AUDIT.read_bytes()) != AUDIT_SHA256:
        raise ValueError('Pinned source audit differs')
    audit = json.loads(AUDIT.read_bytes())
    for fact in audit['source_facts'].values():
        if digest(fact['code'].encode()) != fact['excerpt_sha256']:
            raise ValueError('Source excerpt digest differs')
    prior = previous.verify()
    metadata = copy.deepcopy(prior['annotation-packet-annotator-01.json'])
    profile = copy.deepcopy(metadata['cases'][0]['state']['architecture_profile'])
    metadata.pop('cases')
    metadata['study_kind'] = 'source_expression_annotation'
    metadata['annotation_prompt_sha256'] = digest(PROMPT)
    rubric = prior['rubric.json']
    focal = {'target_id': 'probe-a', 'source_family': 'bdd-step-item',
             'target': {'language': 'Python', 'code': 'not step.valid',
                        'syntax_kind': 'UnaryOp', 'scope': 'exact expression only'},
             'base_facts': audit['focal_fact_names'],
             'additional_facts': audit['focal_additional_fact_names'],
             'owner_renames': FOCAL_RENAMES}
    targets = [focal, *audit['controls']]
    cases, bindings = {}, []
    for target in targets:
        for condition in CONDITIONS:
            fact_names = target['base_facts'] + (target['additional_facts'] if condition['additional_context'] else [])
            fragments, origins = [], []
            for number, name in enumerate(fact_names, 1):
                original = audit['source_facts'][name]['code']
                code = transformed(original, target['owner_renames']) if condition['neutral_owner_names'] else original
                fragments.append({'fragment_id': f'fragment-{number:02d}', 'code': code})
                origins.append({'fragment_id': f'fragment-{number:02d}', 'source_fact': name,
                                'kind': 'source_derived_NAME_token_rewrite' if condition['neutral_owner_names'] else 'verbatim_source',
                                'supplied_code_sha256': digest(code.encode())})
            state = {'architecture_profile': profile, 'target': target['target'],
                     'bounded_context': {'fragments': fragments, 'truncated': False,
                                         'limitations': 'Only the supplied exact fragments are evidence. Unlisted dependencies and contracts are not proved. Judge each case from its own evidence.'}}
            case = {'case_id': target['target_id'], 'state_sha256': digest(canonical(state)),
                    'state': state, 'rubric_sha256': metadata['rubric_sha256']}
            case['task_sha256'] = task_digest(case, metadata)
            cases[(target['target_id'], condition['cell'])] = case
            bindings.append({'case_id': case['case_id'], **condition,
                             'state_sha256': case['state_sha256'], 'task_sha256': case['task_sha256'],
                             'owner_renames': target['owner_renames'] if condition['neutral_owner_names'] else {},
                             'fragments': origins})
    outputs = {'rubric.json': rubric, 'annotation-prompt.txt': PROMPT,
               'upstream-LICENSE.txt': prior['upstream-LICENSE.txt']}
    assignments = []
    for context_offset in range(4):
        for order_offset in range(4):
            slot = f'annotator-{len(assignments) + 1:02d}'
            selections = [(targets[(position + order_offset) % 4]['target_id'],
                           CONDITIONS[((position + order_offset) % 4 + context_offset) % 4]['cell'])
                          for position in range(4)]
            packet = {**metadata, 'cases': [cases[selection] for selection in selections]}
            packet_name, template_name = f'packet-{slot}.json', f'template-{slot}.json'
            outputs[packet_name] = packet
            outputs[template_name] = {'status': 'blank_not_reference', 'annotations': [
                {**{k: case[k] for k in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256')},
                 'opportunity': None, 'concern_kind': None,
                 'rationales': {'opportunity': '', 'concern_kind': ''},
                 'evidence_quotes': [], 'uncertainties': []} for case in packet['cases']]}
            assignments.append({'slot': slot, 'packet': packet_name, 'template': template_name,
                                'agent_task': None, 'directory': None, 'annotation_output': None,
                                'cases': [{'case_id': cid, 'cell': cell, 'position': i + 1}
                                          for i, (cid, cell) in enumerate(selections)]})
    outputs['source-mapping.json'] = {
        'status': 'integrator_only_not_for_annotation', 'source_revision': audit['source_revision'],
        'source_audit_sha256': AUDIT_SHA256, 'targets': targets, 'bindings': bindings}
    outputs['dispatch-plan.json'] = {
        'status': 'prepared_not_dispatched', 'fresh_contexts_planned': 16,
        'targets_per_context': 4, 'case_annotations_planned': 64,
        'contexts_per_target_cell': 4, 'assignments': assignments,
        'provider_requests': 0, 'metric_effect': 'none'}
    outputs['study-plan.json'] = {
        'status': 'pre_registered_diagnostic_not_gold', 'source_revision': audit['source_revision'],
        'conditions': list(CONDITIONS), 'focal_target': 'probe-a', 'formatting_control': 'probe-d',
        'factor_definitions': {
            'additional_context': 'BDD: TextInput/ScenarioInput/BDDContext and text/entry conversion definitions. Other targets: their previously frozen dependency bundles. No adopted requirement is added.',
            'neutral_owner_names': 'Only selected owner class/function and registry NAME tokens change. Exact target expressions, domain fields, string rule addresses and the Specification marker remain unchanged.'},
        'assignment': 'Sixteen fresh contexts; each sees all four targets and conditions once. Four contexts per target-cell. Target-position and condition-position counts are each four. One view per target per context.',
        'hypotheses': {
            'H_ownership': {'criterion': 'All sixteen focal opportunity labels are excluded, including neutral-name cells.',
                            'failure': 'Any other focal opportunity label triggers ownership-evidence review; this does not prove an internal model cause.'},
            'H_names': {'criterion': 'For the focal target, the concern-kind label histograms match between original and neutral owner names at each fixed context level (four judgments per cell).',
                        'failure': 'Any histogram difference records a name-associated difference requiring follow-up; sampling variation remains possible and small samples do not establish causal bias or significance.'},
            'H_definition': {'criterion': 'None of the eight extended-context focal rationales asserts that the operational nonblank validity criterion is unavailable or that strip rewrites the stored source value. Unresolved domain purpose is allowed. Inspect cited evidence, not just labels.',
                             'failure': 'A conflicting claim is an operational interpretation failure. policy, mechanics and unknown are not assigned gold labels for this hypothesis.'},
            'H_local_control': {'criterion': 'All sixteen newline-control annotations are excluded/mechanics, with both context levels and naming modes.',
                                'source': 'Authored development expectation from the locally visible newline append; not independent annotation or human gold.',
                                'failure': 'Any deviation triggers review for local-role recognition or blanket abstention.'}},
        'reporting': ['Report per-target and per-cell raw distributions and decisive coverage independently on each axis.',
                      'Review rationale support separately from exact quote provenance.',
                      'Report target-cell repetition, operational interpretation conflicts and all failed prospective criteria.',
                      'Do not pool heterogeneous context additions as a universal treatment effect.'],
        'limits': ['Owner renaming is partial; domain field names, rule addresses, type names and string literals remain.',
                   'Four related study targets are not a representative codebase sample; labels are descriptive.',
                   'Distinct helper families avoid direct TextInput-definition leakage; cross-case priming remains possible.',
                   'Reversible NAME-token renaming checks syntax and spelling preservation, not a proof of arbitrary Python runtime equivalence.',
                   'The prompt and task identities differ from previous runs; this is not an unchanged-input repeat.',
                   'A nonblank-text definition does not by itself establish domain purpose.'],
        'annotation_started': False, 'human_gold': False,
        'participants': 'Fresh independent annotation contexts, not a Jev/Luna provider protocol. Fixed Choice answers alone cannot satisfy rationale checks.',
        'author_expectations_visible_in_packets': False,
        'reference_frozen_for_provider_scoring': False, 'provider_requests': 0, 'metric_effect': 'none'}
    inputs = [AUDIT, previous.RUN / 'preparation-receipt.json',
              ROOT / 'runs/2026-10-13-bdd-step-item-adjudication/adjudication.json']
    outputs['preparation-receipt.json'] = {
        'status': 'prepared_not_dispatched',
        'input_file_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in inputs},
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {name: digest(encoded(value)) for name, value in outputs.items()},
        'task_identity': 'state_questions_instructions_rubric_bytes_annotation_prompt_digest',
        'distinct_tasks': 16, 'fresh_contexts_planned': 16, 'case_annotations_planned': 64,
        'provider_requests': 0, 'metric_effect': 'none'}
    return outputs


def verify(run=RUN):
    outputs = build()
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Saved definition/owner-name preparation differs: ' + name)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        outputs = build()
        if any((args.run / name).exists() for name in outputs):
            raise ValueError('Refusing to overwrite frozen preparation')
        args.run.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            with (args.run / name).open('xb') as output:
                output.write(encoded(value))
    else:
        verify(args.run)
    print(json.dumps({'distinct_tasks': 16, 'fresh_contexts_planned': 16,
                      'case_annotations_planned': 64, 'annotation_started': False,
                      'provider_requests': 0}))


if __name__ == '__main__':
    main()
