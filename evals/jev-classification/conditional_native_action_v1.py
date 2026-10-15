"""Prepare/replay a conditional-action diagnostic offline; no live entry point."""
import argparse
import ast
import copy
from dataclasses import asdict
import json
from pathlib import Path
from textwrap import dedent

from decision_choice_contract_v2 import ChoiceContractError
import intent_first_native_v1 as native
import prepare_intent_first_native as previous
from question_grouping import canonical, digest

ROOT = previous.ROOT
RUN = ROOT / 'runs/2026-10-15-conditional-native-action-preparation-v1'
STUDY = 'specmetrics.conditional-native-action/v1'
ARMS = ('baseline', 'conditioned', 'ownership_witness')
BDD = 'target-03-cell03'
IMPLEMENTATIONS = ('conditional_native_action_v1.py',) + previous.IMPLEMENTATIONS
CONDITIONING = (
    'This controlled diagnostic additionally supplies state.diagnostic_bindings. '
    'The concern_kind and evidence_confidence there are fixed experimental premises, '
    'not categories you must independently infer or revise. Return those premises '
    'unchanged for their corresponding questions and condition recommendation on them. '
    'An optional ownership_witness summarizes only facts already present in the supplied '
    'code; use it when present. Its absence does not prove absence of a Specification. '
    'Apply the same architecture_profile and recommendation criteria. '
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tree(code):
    return ast.parse(dedent(code))


def shape(node):
    return ast.dump(node, include_attributes=False)


def witness(case):
    """Check this pinned BDD witness only, not a general Python ownership resolver."""
    state = case['state']
    require(case['case_id'] == BDD, 'witness belongs only to the pinned BDD case')
    fragments = {f['fragment_id']: f['code'] for f in state['bounded_context']['fragments']}
    owner = tree(fragments['fragment-01']).body[0]
    base = tree(fragments['fragment-02']).body[0]
    evaluate = tree(fragments['fragment-03']).body[0]
    membership = tree(fragments['fragment-04']).body[0]
    caller = tree(fragments['fragment-05']).body[0]
    require(isinstance(owner, ast.ClassDef) and owner.name == 'BDDScenarioValuesSpec'
            and len(owner.bases) == 1 and shape(owner.bases[0]) == shape(tree('BDDPolicy').body[0].value),
            'selected owner inheritance differs')
    require(isinstance(base, ast.ClassDef) and base.name == 'BDDPolicy' and len(base.bases) == 1
            and shape(base.bases[0]) == shape(tree('Specification[BDDContext]').body[0].value),
            'recognized Specification base differs')
    methods = {n.name: n for n in owner.body if isinstance(n, ast.FunctionDef)}
    require('findings' in methods and '_evaluate' not in methods, 'owner evaluation override differs')
    target = tree(state['target']['code']).body[0].value
    filters = [n for n in ast.walk(methods['findings']) if isinstance(n, ast.comprehension)]
    require(any(any(shape(test) == shape(target) for test in n.ifs) for n in filters),
            'selected target is not a findings filter')
    require(shape(methods['findings'].body[-1]) == shape(tree('return tuple(findings)').body[0]),
            'findings result differs')
    require(isinstance(evaluate, ast.FunctionDef) and evaluate.name == '_evaluate'
            and len(evaluate.body) == 1
            and shape(evaluate.body[0]) == shape(tree('return not self.findings(candidate)').body[0]),
            'findings-to-verdict evaluation path differs')
    scope = state['evaluation_scope']
    binding = scope['application_binding']
    require(scope['definition']['symbol'] == 'BDDScenarioValuesSpec.findings'
            and scope['definition']['code'] == state['target']['code'] == 'not step.valid'
            and binding['code'] == 'policy.findings(context)'
            and binding['receiver_binding']['selected_member'] == 'BDDScenarioValuesSpec()'
            and binding['receiver_binding']['membership_witness']['code'] == fragments['fragment-04'],
            'selected application binding differs')
    require(isinstance(membership, ast.Assign) and len(membership.targets) == 1
            and isinstance(membership.targets[0], ast.Name) and membership.targets[0].id == 'POLICIES'
            and isinstance(membership.value, ast.Tuple)
            and any(shape(n) == shape(tree('BDDScenarioValuesSpec()').body[0].value)
                    for n in membership.value.elts), 'selected member not in POLICIES')
    require(isinstance(caller, ast.For) and shape(caller.target) == shape(tree('for policy in POLICIES:\n pass').body[0].target)
            and isinstance(caller.iter, ast.Name) and caller.iter.id == 'POLICIES', 'caller receiver differs')
    calls = {shape(n) for n in ast.walk(caller) if isinstance(n, ast.Call)}
    require(all(shape(tree(c).body[0].value) in calls for c in
                ('policy.is_satisfied_by(context, recorder=recorder)', 'policy.findings(context)')),
            'consumer evaluation/diagnostic calls differ')
    quotes = [{'fragment_id': key, 'source_sha256': digest(fragments[key].encode()), 'quote': quote}
              for key, quote in (
                  ('fragment-01', 'class BDDScenarioValuesSpec(BDDPolicy):'),
                  ('fragment-02', 'class BDDPolicy(Specification[BDDContext]):'),
                  ('fragment-03', 'return not self.findings(candidate)'),
                  ('fragment-04', 'BDDScenarioValuesSpec(),'),
                  ('fragment-05', 'current_findings = policy.findings(context)'))]
    require(all(q['quote'] in fragments[q['fragment_id']] for q in quotes), 'non-source quote')
    return dict(status='established_in_supplied_context', declared_type='BDDScenarioValuesSpec',
                inheritance=['BDDScenarioValuesSpec', 'BDDPolicy', 'Specification[BDDContext]'],
                selected_method='BDDScenarioValuesSpec.findings',
                verdict_path='BDDPolicy._evaluate -> self.findings(candidate)',
                selected_application='policy.findings(context)', evidence=quotes,
                proof_scope='pinned supplied AST and binding only; no runtime execution or general import resolution')


def questions(arm):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    result = copy.deepcopy(native.QUESTIONS)
    if arm != 'baseline':
        for question in result.values():
            question['instructions'] = question['instructions'].replace(
                'bounded_context and evaluation_scope.', 'bounded_context, evaluation_scope and diagnostic_bindings.')
            question['instructions'] += CONDITIONING
    return result


def wire_body(provider, state, arm):
    body = native.wire_body(provider, canonical(state).decode())
    qs = questions(arm)
    if provider == 'jev-coreinfra':
        body['questions'] = qs
    else:
        body['questions'] = [dict(name=k, type=q['type'], instructions=q['instructions'],
                                 choices=[dict(value=v, description=t) for v, t in sorted(q['criteria'].items())])
                             for k, q in sorted(qs.items())]
    return body


def build():
    previous_files = previous.verify()
    source_files = previous.source.verify()
    protocol_bytes = (ROOT / 'conditional-native-action.md').read_bytes()
    cases = json.loads(source_files['packet.json'])['cases']
    examples = {r['case_id']: r for r in json.loads(source_files['integrator-examples.json'])['annotations']}
    previous_requests = {(r['case_id'], r['provider']): r
                         for r in json.loads(previous_files['manifest.json'])['requests']}
    premises = {c['case_id']: {k: examples[c['case_id']][k]
                              for k in ('concern_kind', 'evidence_confidence')} for c in cases}
    # Actions are deliberately absent from model-visible diagnostic bindings.
    bdd_witness = witness(next(c for c in cases if c['case_id'] == BDD))
    requests = []
    for index, case in enumerate(cases):
        for provider_index, provider in enumerate(native.PROVIDERS):
            arms = list(ARMS if case['case_id'] == BDD else ARMS[:2])
            offset = (index + provider_index) % len(arms)
            for arm in arms[offset:] + arms[:offset]:
                state = copy.deepcopy(case['state'])
                if arm != 'baseline':
                    state['diagnostic_bindings'] = dict(
                        status='fixed_development_premises_not_independent_model_findings',
                        **premises[case['case_id']])
                    if arm == 'ownership_witness':
                        state['diagnostic_bindings']['ownership_witness'] = bdd_witness
                wire = canonical(wire_body(provider, state, arm))
                require(len(canonical(state)) <= 16 * 1024 and len(wire) <= 64 * 1024,
                        'oversized state/wire; never truncate')
                prior = previous_requests[case['case_id'], provider]
                if arm == 'baseline':
                    require(wire.decode() == prior['wire_json'], 'baseline wire drift')
                task = dict(study=STUDY, source_task_sha256=case['task_sha256'], arm=arm,
                            wire_state_sha256=digest(canonical(state)), questions_sha256=digest(canonical(questions(arm))))
                requests.append(dict(request_id=case['case_id'] + '-' + arm + '-' + provider,
                                     case_id=case['case_id'], arm=arm, provider=provider,
                                     source_task_sha256=case['task_sha256'], source_state_sha256=case['state_sha256'],
                                     scope_binding_sha256=case['scope_binding_sha256'],
                                     diagnostic_task_sha256=digest(canonical(task)),
                                     diagnostic_premises=premises[case['case_id']] if arm != 'baseline' else None,
                                     ownership_witness_visible=arm == 'ownership_witness',
                                     wire_state_sha256=task['wire_state_sha256'], questions_sha256=task['questions_sha256'],
                                     requested_model=prior['requested_model'], endpoint=prior['endpoint'],
                                     wire_json=wire.decode(), wire_sha256=digest(wire)))
    require(len(requests) == 18, 'expected 8 baseline + 8 conditioned + 2 BDD witness requests')
    manifest = dict(protocol=previous.PROTOCOL, study=STUDY, semantic_status='unscored',
                    status='prepared_offline_not_live_authorized', retry_policy=asdict(previous.RetryPolicy()),
                    producer_digests=previous.transport.producer_digests(),
                    diagnostic_producer_sha256={n: digest((ROOT / n).read_bytes()) for n in IMPLEMENTATIONS},
                    input_file_sha256={str((previous.RUN / n).relative_to(ROOT)): digest(v)
                                       for n, v in previous_files.items()},
                    requests=requests, planned_requests=18, max_network_attempts=54,
                    native_validation_policy=native.POLICY, full_v4_1_annotation=False,
                    diagnostic_protocol_sha256=digest(protocol_bytes),
                    human_gold=False, provider_scoring_enabled=False, metric_effect='none',
                    live_authorization='Separate explicit approval of 18 requests / at most 54 attempts; no semantic retries.')
    files = {'manifest.json': previous.source.rules.encoded(manifest),
             'premises.json': previous.source.rules.encoded(dict(
                 status='known_development_premises_not_gold', roles=premises,
                 source=str(previous.source.RUN.relative_to(ROOT) / 'integrator-examples.json'),
                 source_sha256=digest(source_files['integrator-examples.json']),
                 interpretation='Supplied experimental role/support premises, not measured classification accuracy.')),
             'ownership-witness.json': previous.source.rules.encoded(bdd_witness),
             'protocol.md': protocol_bytes,
             'README.md': (
                 '# Conditional native action diagnostic v1\n\n'
                 'Prepared offline: 18 requests / at most 54 network attempts; no inference.\n'
                 'Eight byte-identical fresh baseline wires, eight conditioned role/support\n'
                 'wires, two BDD-only wires with an explicit source-derived ownership witness.\n'
                 'All arms retain three Choice questions. Premises are known development\n'
                 'fixtures, not independent predictions or blind gold. No expected action\n'
                 'labels enter a wire. The witness adds visibility, not new source facts.\n\n'
                 'See [protocol and decision criteria](../../conditional-native-action.md).\n'
                 'Exact preregistered protocol bytes are also retained in protocol.md and bound in manifest.\n'
                 'This package is not live authorization; no scoring or production S/U change.\n'
             ).encode()}
    files['preparation-receipt.json'] = previous.source.rules.encoded(dict(
        study=STUDY, status='prepared_offline_no_inference', planned_requests=18, max_network_attempts=54,
        provider_requests=0, artifact_file_sha256={n: digest(v) for n, v in files.items()},
        diagnostic_producer_sha256=manifest['diagnostic_producer_sha256'],
        input_file_sha256=manifest['input_file_sha256'], human_gold=False, metric_effect='none'))
    files['SHA256SUMS'] = ''.join(digest(v) + '  ' + n + '\n' for n, v in sorted(files.items())).encode()
    return files


def verify(run=RUN):
    files = build()
    require({p.name for p in run.iterdir()} == set(files), 'diagnostic file set differs')
    for name, value in files.items():
        require((run / name).read_bytes() == value, 'diagnostic preparation differs: ' + name)
    return files


def write(run):
    files = build()
    run.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (run / name).open('xb') as stream:
            stream.write(value)


def stage(destination, preparation=RUN):
    files = verify(preparation)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / 'manifest.json').open('xb') as stream:
        stream.write(files['manifest.json'])
    return previous.transport.execute(destination, live=False)


def inspect(run, preparation=RUN):
    files = verify(preparation)
    require((run / 'manifest.json').read_bytes() == files['manifest.json'], 'execution manifest differs')
    expected = {r['request_id']: r for r in json.loads(files['manifest.json'])['requests']}
    premises = json.loads(files['premises.json'])['roles']
    path = run / 'responses.jsonl'
    snapshot = path.read_bytes() if path.exists() else None
    rows, seen = [], set()
    for raw in snapshot.splitlines() if snapshot is not None else []:
        item = previous.transport.decode(raw)
        require(isinstance(item, dict), 'invalid response row')
        rid = item.get('request_id')
        require(isinstance(rid, str) and rid in expected and rid not in seen, 'unknown/duplicate identity')
        request = expected[rid]
        require(item.get('protocol') == previous.PROTOCOL and item.get('wire_sha256') == request['wire_sha256'],
                'response wire binding differs')
        require(item.get('status') in {'json_received', 'http_error', 'response_decode_error',
                                      'transport_error', 'response_too_large'}, 'invalid transport status')
        seen.add(rid)
        row = dict(request_id=rid, case_id=request['case_id'], provider=request['provider'], arm=request['arm'],
                   transport_status=item['status'], native_status='not_evaluated', projection_status='not_evaluated',
                   prediction=None, premise_echo_matches=None, action_violations_against_development_premises=None,
                   bdd_reuse_diagnostic=None)
        if item['status'] == 'json_received':
            require(item.get('http_status') == 200 and isinstance(item.get('response'), dict), 'invalid received JSON')
            try:
                prediction = native.parse_response(canonical(item['response']), provider=request['provider'],
                                                   model=request['requested_model'])
                row.update(native_status='valid', prediction=prediction,
                           projection_status=('consistent_native_projection' if prediction['tuple_consistent']
                                              else 'inconsistent_native_projection'))
                labels = prediction['labels']
                anchors = premises[request['case_id']]
                row['action_violations_against_development_premises'] = native.tuple_violations(dict(
                    anchors, recommendation=labels['recommendation']))
                if request['diagnostic_premises'] is not None:
                    row['premise_echo_matches'] = all(labels[k] == v for k, v in anchors.items())
                if request['case_id'] == BDD:
                    row['bdd_reuse_diagnostic'] = ('reuse_selected' if labels['recommendation'] == 'reuse_specification'
                                                   else 'existing_specification_not_reused')
            except ChoiceContractError as error:
                row.update(native_status='invalid', projection_status='native_invalid', rejection_code=error.code)
        rows.append(row)
    return dict(status='native_diagnostic_rows_not_accuracy_scored', rows=rows,
                requests_without_response_rows=[rid for rid in expected if rid not in seen],
                response_file_sha256=digest(snapshot) if snapshot is not None else None,
                execution_inferred_from_missing_rows=False, transport_ledger_verified=False,
                full_v4_1_annotation=False, provider_scoring_enabled=False, metric_effect='none')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN, help='frozen preparation directory')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--write', action='store_true')
    action.add_argument('--stage', type=Path, help='NEW execution directory, offline only')
    action.add_argument('--inspect', type=Path, help='decode existing rows without requests')
    args = parser.parse_args()
    if args.stage:
        result = stage(args.stage, args.run)
    elif args.inspect:
        result = inspect(args.inspect, args.run)
    else:
        write(args.run) if args.write else verify(args.run)
        result = dict(status='prepared_offline_no_inference', planned_requests=18,
                      max_network_attempts=54, inference=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
