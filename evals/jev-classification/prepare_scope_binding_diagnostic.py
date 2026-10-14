"""Freeze scope/document diagnostic packets offline; no dispatch or scoring."""
import argparse
import ast
import copy
import json
from pathlib import Path

import prepare_manifest_contract_balanced as prior
from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest

ROOT = prior.ROOT
EVIDENCE = ROOT / 'runs/2026-10-14-scope-binding-evidence-v3'
RUN = ROOT / 'runs/2026-10-14-scope-binding-preparation-v3'
BINDING_SHA = 'de10021246249f98efa72096e9b1adb4a08b1b82c66b4e99b053890369d4ec79'
encoded = prior.encoded
CONDITIONS = (
    {'cell': '01', 'unit': 'shared_definition', 'documents': False},
    {'cell': '02', 'unit': 'shared_definition', 'documents': True},
    {'cell': '03', 'unit': 'bound_application', 'documents': False},
    {'cell': '04', 'unit': 'bound_application', 'documents': True},
)
SCOPE_INSTRUCTION = (
    'Respect state.evaluation_scope.unit. For shared_definition, judge the exact '
    'expression as part of its shared definition across the supplied uses. For '
    'bound_application, judge that SAME exact expression for the selected static '
    'argument/receiver binding at the recorded callsite, not the call expression '
    'or the whole caller. Other uses are context, not authority to transfer their '
    'role to this application. Both units receive identical code and binding '
    'facts. Binding metadata establishes a possible static association, not runtime '
    'execution, domain purpose, Specification ownership or a desired label. '
    'State the selected unit and evidence for each judgment in both rationales. '
)
PROMPT = SCOPE_INSTRUCTION + prior.PROMPT


def ast_key(node):
    """Canonical AST fields, independent of ast.dump empty-field formatting."""
    def fields(value):
        if isinstance(value, ast.AST):
            return {'node': type(value).__name__, 'fields': {
                name: fields(item) for name, item in ast.iter_fields(value)
                if item is not None and item != []}}
        if isinstance(value, list):
            return [fields(item) for item in value]
        return value
    return canonical(fields(node))


def resolve_symbol(tree, symbol):
    for name in symbol.split('.'):
        matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name]
        if len(matches) != 1:
            raise ValueError('Source symbol is ambiguous or missing: ' + symbol)
        tree = matches[0]
    return tree


def anchored_node(sources, anchor):
    source = sources[anchor['path']]['content']
    matches = [n for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.expr, ast.stmt))
               and [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset] == anchor['span']]
    matches = [n for n in matches if ast.get_source_segment(source, n) == anchor['code']
               and digest(ast_key(n)) == anchor['ast_sha256']]
    if len(matches) != 1:
        raise ValueError('AST anchor differs: ' + anchor['path'])
    return matches[0]


def verify_binding(sources, binding, target):
    definition, application = binding['definition'], binding['application']
    node = anchored_node(sources, definition)
    expected = ast_key(ast.parse(target['code'], mode='eval').body)
    if ast_key(node) != expected:
        raise ValueError('Exact target differs from definition anchor')
    def_tree = ast.parse(sources[definition['path']]['content'])
    function = resolve_symbol(def_tree, definition['symbol'])
    if not any(getattr(n, 'lineno', None) == node.lineno and getattr(n, 'col_offset', None) == node.col_offset
               and ast_key(n) == expected for n in ast.walk(function)):
        raise ValueError('Target is outside its declared definition')
    call = anchored_node(sources, application)
    if not isinstance(call, ast.Call) or not call.args:
        raise ValueError('Application must anchor a real argument-bearing call')
    call_source = sources[application['path']]['content']
    caller = resolve_symbol(ast.parse(call_source), application['enclosing_symbol'])
    if not any(isinstance(n, ast.Call) and n.lineno == call.lineno and n.col_offset == call.col_offset
               for n in ast.walk(caller)):
        raise ValueError('Call is outside its declared caller')
    argument = application['argument_binding']
    parameters = [a.arg for a in function.args.posonlyargs + function.args.args if a.arg != 'self']
    if (not parameters or argument['parameter'] != parameters[0]
            or argument['expression'] != ast.get_source_segment(call_source, call.args[0])):
        raise ValueError('Static argument binding differs')
    receiver = application.get('receiver_binding')
    if receiver:
        declaration = anchored_node(sources, receiver['membership_witness'])
        if (not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name)
                or call.func.value.id != receiver['receiver'] or call.func.attr != function.name
                or not isinstance(declaration, ast.Assign) or not isinstance(declaration.value, ast.Tuple)
                or not any(isinstance(n, ast.Name) and n.id == receiver['container'] for n in declaration.targets)
                or receiver['selected_member'] not in [ast.unparse(n) for n in declaration.value.elts]
                or receiver['selected_member'] != definition['symbol'].split('.')[0] + '()'):
            raise ValueError('Static receiver membership differs')
        if not any(isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                   and n.target.id == receiver['receiver'] and isinstance(n.iter, ast.Name)
                   and n.iter.id == receiver['container']
                   and any(isinstance(c, ast.Call) and c.lineno == call.lineno for c in ast.walk(n))
                   for n in ast.walk(caller)):
            raise ValueError('Receiver iteration differs')
    elif not isinstance(call.func, ast.Name) or call.func.id != function.name:
        raise ValueError('Direct call does not select the definition')


def build():
    previous = prior.verify()
    catalog = json.loads((prior.EVIDENCE / 'evidence-bundles.json').read_text())
    binding_path = EVIDENCE / 'source-bindings.json'
    if digest(binding_path.read_bytes()) != BINDING_SHA:
        raise ValueError('Scope binding catalog differs')
    evidence = json.loads(binding_path.read_text())
    if evidence['source_revision'] != catalog['source_revision'] or evidence['catalog_sha256'] != prior.CATALOG_SHA:
        raise ValueError('Binding source identity differs')
    known = {f['origin']['path']: f['origin']['file_sha256'] for t in catalog['targets']
             for group in ('base_fragments', 'consumer_fragments') for f in t[group]}
    for path, source in evidence['sources'].items():
        if digest(source['content'].encode()) != source['sha256'] or source['sha256'] != known.get(path):
            raise ValueError('Pinned source snapshot differs: ' + path)
    bindings = {b['case_id']: b for b in evidence['bindings']}
    if len(bindings) != 4 or set(bindings) != {t['case_id'] for t in catalog['targets']}:
        raise ValueError('Expected four distinct-family static bindings')
    rubric = json.loads(previous['rubric.json'])
    rubric.update(id='specification_metrics.expression-fit.v3-scope-diagnostic', version=3,
                  supersedes=rubric['id'], status='proposal_prepared_not_annotated_not_production',
                  scope='Exact-expression definition/application scope diagnostic; no metric or scoring-reference effect.')
    for question in rubric['questions'].values():
        question['instructions'] = SCOPE_INSTRUCTION + question['instructions']
    metadata = copy.deepcopy(previous['packet-annotator-01.json'])
    del metadata['cases']
    metadata.update(study_kind='scope_binding_diagnostic', questions=rubric['questions'], rubric_id=rubric['id'],
                    rubric_sha256=digest(encoded(rubric)), questions_sha256=digest(canonical(rubric['questions'])),
                    annotation_prompt_sha256=digest(PROMPT.encode()))
    outputs = {'rubric.json': encoded(rubric), 'annotation-prompt.txt': PROMPT.encode(),
               'upstream-LICENSE.txt': (EVIDENCE / 'upstream-LICENSE.txt').read_bytes()}
    cases, mapping = {}, []
    profile = previous['packet-annotator-01.json']['cases'][0]['state']['architecture_profile']
    limits = previous['packet-annotator-01.json']['cases'][0]['state']['bounded_context']
    for target in catalog['targets']:
        binding = bindings[target['case_id']]
        verify_binding(evidence['sources'], binding, target['target'])
        for condition in CONDITIONS:
            selected = target['base_fragments'] + target['consumer_fragments']
            if condition['documents']:
                selected += target['document_fragments']
            fragments = [{'fragment_id': f'fragment-{i:02d}',
                          **{k: copy.deepcopy(f[k]) for k in ('kind', 'code', 'text', 'authority', 'language') if k in f}}
                         for i, f in enumerate(selected, 1)]
            state = {'architecture_profile': copy.deepcopy(profile), 'target': copy.deepcopy(target['target']),
                     'evaluation_scope': {'unit': condition['unit'], 'definition': binding['definition'],
                                          'application_binding': binding['application']},
                     'bounded_context': {**copy.deepcopy(limits), 'fragments': fragments}}
            case = {'case_id': target['case_id'], 'state': state, 'state_sha256': digest(canonical(state)),
                    'rubric_sha256': metadata['rubric_sha256']}
            case['task_sha256'] = task_digest(case, metadata)
            cases[target['case_id'], condition['cell']] = case
            mapping.append({'case_id': target['case_id'], 'family': target['family'], **condition,
                            'state_sha256': case['state_sha256'], 'task_sha256': case['task_sha256'],
                            'fragments': [{'fragment_id': f'fragment-{i:02d}', **f['origin']}
                                          for i, f in enumerate(selected, 1)]})
    assignments = copy.deepcopy(previous['dispatch-plan.json']['assignments'])
    for assignment in assignments:
        slot = assignment['slot']
        packet = {**metadata, 'cases': [cases[c['case_id'], c['cell']] for c in assignment['cases']]}
        blanks = [{**{k: c[k] for k in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256')},
                   'opportunity': None, 'concern_kind': None, 'rationales': {a: '' for a in rubric['questions']},
                   'evidence_quotes': [], 'uncertainties': []} for c in packet['cases']]
        outputs['packet-' + slot + '.json'] = packet
        outputs['template-' + slot + '.json'] = {'status': 'blank_not_reference', 'annotations': blanks}
    outputs['dispatch-plan.json'] = {'status': 'prepared_not_dispatched', 'version': 3,
                                    'fresh_contexts_planned': 12, 'case_annotations_planned': 48,
                                    'targets_per_context': 4, 'contexts_per_target_cell': 3,
                                    'conditions': CONDITIONS, 'assignments': assignments,
                                    'dispatch_ready': False,
                                    'remaining_work': ['Scope-aware actual-file handoff and retained-attempt replay',
                                                       'Protocol review and explicit run authorization'],
                                    'provider_requests': 0, 'metric_effect': 'none'}
    outputs['source-mapping.json'] = {'status': 'integrator_only_not_for_annotation',
                                     'source_revision': catalog['source_revision'], 'conditions': mapping}
    outputs['study-plan.json'] = {
        'status': 'prospective_protocol_prepared_not_dispatched', 'version': 3,
        'factors': ['shared_definition_vs_bound_application', 'documents_absent_vs_present'],
        'held_fixed': ['exact_expression', 'code_fragments', 'all_consumers', 'all_static_binding_facts',
                       'architecture_profile', 'label_sets_and_eligibility_tie_rules'],
        'focal_target': 'target-01', 'control_targets': ['target-02', 'target-03', 'target-04'],
        'units': {'shared_definition': 'Exact expression as part of its shared definition across supplied uses.',
                  'bound_application': 'Same exact expression at the selected static binding; not the call or whole caller.'},
        'counts': {'contexts': 12, 'annotations': 48, 'source_targets': 4, 'target_cells': 16, 'repetitions': 3},
        'comparisons': ['01_vs_03_and_02_vs_04_scope_within_each_target',
                        '01_vs_02_and_03_vs_04_documents_within_each_target'],
        'reporting': ['Per-axis histograms, decisive coverage denominator 3 per target-cell, every disagreement.',
                      'Do not pool distinct targets into a common treatment effect.',
                      'V2 comparison is descriptive: consumers are fixed here and rubric version changes.',
                      'Bindings are evidence contexts, not extra production opportunities or Specifications.'],
        'prospective_manual_checks': {
            'scope_fidelity': 'Every rationale identifies its assigned unit and keeps exact-expression boundaries.',
            'role_witness': 'Record source-backed role evidence; metadata and missing documents alone settle no label.',
            'ownership': 'Same-decision ownership is checked separately from concern_kind.',
            'traceability': 'Actual-file checks, exact identities, both axes, own-case quotes and all raw attempts.'},
        'hypothesis_limits': ['If application scope retains disagreement, scope alone does not resolve evidence sufficiency.',
                              'If scope changes no judgments or reasons, this is evidence against its practical value here.',
                              'Agreement is not semantic truth or a human reference.',
                              'Target/cell and target/position and cell/position marginals are balanced; target-cell/position is NOT fully crossed.',
                              'No isolated order-effect estimate or causal model-mechanism claim is supported.',
                              'One view per dependency family per fresh context; common model bias and priming remain possible.'],
        'reference_frozen_for_provider_scoring': False, 'human_gold': False,
        'provider_requests': 0, 'metric_effect': 'none'}
    outputs['preparation-receipt.json'] = {
        'schema_version': 3, 'status': 'prepared_not_dispatched',
        'input_file_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in
                              (binding_path, prior.EVIDENCE / 'evidence-bundles.json',
                               prior.RUN / 'preparation-receipt.json', EVIDENCE / 'upstream-LICENSE.txt')},
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {name: digest(encoded(value)) for name, value in outputs.items()},
        'distinct_tasks': 16, 'fresh_contexts_planned': 12, 'case_annotations_planned': 48,
        'annotation_started': False, 'dispatch_ready': False,
        'provider_requests': 0, 'metric_effect': 'none', 'human_gold': False}
    return outputs


def verify(run=RUN):
    outputs = build()
    if {p.name for p in run.iterdir()} != set(outputs):
        raise ValueError('Scope preparation file set differs')
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Frozen scope preparation differs: ' + name)
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
    print(json.dumps({'status': 'prepared_not_dispatched', 'fresh_contexts_planned': 12,
                      'case_annotations_planned': 48, 'dispatch_ready': False,
                      'annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none'}))


if __name__ == '__main__':
    main()
