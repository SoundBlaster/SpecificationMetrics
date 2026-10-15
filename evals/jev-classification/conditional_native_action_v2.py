"""Source-bound repair of v1; preserve the unexecuted v1 package and producer."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

import conditional_native_action_v1 as old
from decision_choice_contract_v2 import ChoiceContractError

ROOT = old.ROOT
RUN = ROOT / 'runs/2026-10-15-conditional-native-action-preparation-v2'
SOURCE = ROOT / 'runs/2026-10-15-conditional-native-source-binding-v2/source.json'
SOURCE_SHA256 = 'd7c826e8a2736b8b27d657f6877aa3eaccb098bccc81d88789fa0365b1c086db'
REVISION = '51c8d93cc385569864b3cd7f5040d4b3e0820a1b'
STUDY = 'specmetrics.conditional-native-action/v2'
require, shape, tree = old.require, old.shape, old.tree
canonical, digest = old.canonical, old.digest
encoded = old.previous.source.rules.encoded


def sources():
    raw = SOURCE.read_bytes()
    require(digest(raw) == SOURCE_SHA256, 'pinned source snapshot differs')
    record = json.loads(raw)
    require(record['revision'] == REVISION, 'source revision differs')
    files = {}
    for row in record['files']:
        code = row['code'].encode()
        require(row['path'] not in files and digest(code) == row['sha256'], 'source identity/hash differs')
        require(hashlib.sha1(b'blob ' + str(len(code)).encode() + b'\0' + code).hexdigest() == row['git_blob_sha1'],
                'Git blob identity differs')
        files[row['path']] = row['code']
    return raw, files


def bind_witness(case, files):
    """Establish containment in contiguous source, not a free-standing method snippet."""
    result = old.witness(case)
    fragments = {f['fragment_id']: f['code'] for f in case['state']['bounded_context']['fragments']}
    modules = {p: tree(code) for p, code in files.items()}
    policy_path, values_path, composition_path = ('tools/native_bdd/' + n for n in
                                                ('policy.py', 'values_spec.py', 'composition.py'))
    def direct(nodes, kind, name):
        found = [n for n in nodes if isinstance(n, kind) and n.name == name]
        require(len(found) == 1, 'expected unique direct declaration: ' + name)
        return found[0]
    policy = direct(modules[policy_path].body, ast.ClassDef, 'BDDPolicy')
    method = direct(policy.body, ast.FunctionDef, '_evaluate')
    owner = direct(modules[values_path].body, ast.ClassDef, 'BDDScenarioValuesSpec')
    evaluate = direct(modules[composition_path].body, ast.FunctionDef, 'evaluate')
    require(shape(method) == shape(tree(fragments['fragment-03']).body[0]),
            'fragment-03 is not BDDPolicy._evaluate in pinned source')
    base_fragment = tree(fragments['fragment-02']).body[0]
    require([shape(n) for n in base_fragment.bases] == [shape(n) for n in policy.bases]
            and [shape(n) for n in base_fragment.body] == [shape(n) for n in policy.body[:len(base_fragment.body)]],
            'fragment-02 is not the pinned BDDPolicy prefix')
    require(shape(owner) == shape(tree(fragments['fragment-01']).body[0]), 'owner fragment/source differ')
    require(any(shape(n) == shape(tree(fragments['fragment-04']).body[0]) for n in modules[composition_path].body),
            'membership fragment/source differ')
    require(any(shape(n) == shape(tree(fragments['fragment-05']).body[0]) for n in evaluate.body),
            'consumer fragment not in pinned evaluate function')
    bindings = []
    for fragment, path, symbol, node in (
            ('fragment-01', values_path, 'BDDScenarioValuesSpec', owner),
            ('fragment-02', policy_path, 'BDDPolicy', policy),
            ('fragment-03', policy_path, 'BDDPolicy._evaluate', method),
            ('fragment-05', composition_path, 'evaluate', evaluate)):
        bindings.append(dict(fragment_id=fragment, path=path, defining_symbol=symbol,
                             source_sha256=digest(files[path].encode()),
                             span=[node.lineno, node.col_offset, node.end_lineno, node.end_col_offset]))
    result.update(source_revision=REVISION, source_snapshot_sha256=SOURCE_SHA256,
                  source_bindings=bindings,
                  proof_scope='contiguous pinned modules bind fragments to direct class/function declarations; not runtime execution')
    return result


def build():
    prior = old.verify()
    source_raw, files = sources()
    cases = json.loads(old.previous.source.verify()['packet.json'])['cases']
    bdd = next(c for c in cases if c['case_id'] == old.BDD)
    witness = bind_witness(bdd, files)
    manifest = copy.deepcopy(json.loads(prior['manifest.json']))
    manifest.update(study=STUDY, supersedes_for_live=old.STUDY,
                    source_binding_sha256=SOURCE_SHA256,
                    repair_protocol_sha256=digest((ROOT / 'conditional-native-action-v2.md').read_bytes()))
    manifest['diagnostic_producer_sha256']['conditional_native_action_v2.py'] = digest(Path(__file__).read_bytes())
    manifest['input_file_sha256'] = {str((old.RUN / n).relative_to(ROOT)): digest(v) for n, v in prior.items()}
    manifest['input_file_sha256'][str(SOURCE.relative_to(ROOT))] = digest(source_raw)
    for request in manifest['requests']:
        request['request_id'] += '-v2'
        if request['arm'] == 'ownership_witness':
            body = json.loads(request['wire_json'])
            key = 'state' if request['provider'] == 'jev-coreinfra' else 'input'
            state = json.loads(body[key])
            state['diagnostic_bindings']['ownership_witness'] = witness
            body[key] = canonical(state).decode()
            wire = canonical(body)
            require(len(canonical(state)) <= 16 * 1024 and len(wire) <= 64 * 1024, 'oversized repaired wire')
            request.update(wire_json=wire.decode(), wire_sha256=digest(wire),
                           wire_state_sha256=digest(canonical(state)))
        request['diagnostic_task_sha256'] = digest(canonical(dict(
            study=STUDY, prior_task_sha256=request['diagnostic_task_sha256'],
            wire_state_sha256=request['wire_state_sha256'], questions_sha256=request['questions_sha256'],
            source_binding_sha256=SOURCE_SHA256)))
    artifacts = {n: prior[n] for n in ('premises.json', 'protocol.md')}
    artifacts.update({'manifest.json': encoded(manifest), 'ownership-witness.json': encoded(witness),
                      'source.json': source_raw, 'repair.md': (ROOT / 'conditional-native-action-v2.md').read_bytes(),
                      'README.md': b'# Conditional action v2: source-bound live preparation\n\n18 requests / at most 54 attempts. v1 is retained unexecuted and superseded for live.\nBaseline/conditioned wires and H1/H2 criteria are unchanged; BDD witness now binds\nfragment-03 to BDDPolicy._evaluate in contiguous pinned source.\nSee repair.md, protocol.md and source.json. No inference during preparation.\n'})
    artifacts['preparation-receipt.json'] = encoded(dict(
        study=STUDY, status='source_bound_prepared_offline', planned_requests=18, max_network_attempts=54,
        provider_requests=0, artifact_file_sha256={n: digest(v) for n, v in artifacts.items()},
        diagnostic_producer_sha256=manifest['diagnostic_producer_sha256'],
        input_file_sha256=manifest['input_file_sha256'], metric_effect='none'))
    artifacts['SHA256SUMS'] = ''.join(digest(v) + '  ' + n + '\n' for n, v in sorted(artifacts.items())).encode()
    return artifacts


def verify(run=RUN):
    artifacts = build()
    require({p.name for p in run.iterdir()} == set(artifacts), 'v2 file set differs')
    for name, value in artifacts.items():
        require((run / name).read_bytes() == value, 'v2 preparation differs: ' + name)
    return artifacts


def write(run):
    artifacts = build()
    run.mkdir(parents=True, exist_ok=False)
    for name, value in artifacts.items():
        with (run / name).open('xb') as stream:
            stream.write(value)


def stage(destination, preparation=RUN):
    artifacts = verify(preparation)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / 'manifest.json').open('xb') as stream:
        stream.write(artifacts['manifest.json'])
    return old.previous.transport.execute(destination, live=False)


def inspect(run, preparation=RUN):
    artifacts = verify(preparation)
    require((run / 'manifest.json').read_bytes() == artifacts['manifest.json'], 'v2 execution manifest differs')
    expected = {r['request_id']: r for r in json.loads(artifacts['manifest.json'])['requests']}
    premises = json.loads(artifacts['premises.json'])['roles']
    path = run / 'responses.jsonl'
    snapshot = path.read_bytes() if path.exists() else None
    rows, seen = [], set()
    for raw in snapshot.splitlines() if snapshot is not None else []:
        item = old.previous.transport.decode(raw)
        require(isinstance(item, dict), 'invalid response row')
        rid = item.get('request_id')
        require(isinstance(rid, str) and rid in expected and rid not in seen, 'unknown/duplicate response')
        request = expected[rid]
        require(item.get('protocol') == old.previous.PROTOCOL and item.get('wire_sha256') == request['wire_sha256'],
                'response wire binding differs')
        require(item.get('status') in {'json_received', 'http_error', 'response_decode_error', 'transport_error',
                                      'response_too_large'}, 'invalid transport status')
        seen.add(rid)
        row = dict(request_id=rid, case_id=request['case_id'], provider=request['provider'], arm=request['arm'],
                   transport_status=item['status'], native_status='not_evaluated', projection_status='not_evaluated',
                   prediction=None, premise_echo_matches=None, action_violations_against_development_premises=None,
                   bdd_reuse_diagnostic=None)
        if item['status'] == 'json_received':
            require(item.get('http_status') == 200 and isinstance(item.get('response'), dict), 'invalid JSON receipt')
            try:
                prediction = old.native.parse_response(canonical(item['response']), provider=request['provider'],
                                                       model=request['requested_model'])
                labels, anchors = prediction['labels'], premises[request['case_id']]
                row.update(native_status='valid', prediction=prediction,
                           projection_status=('consistent_native_projection' if prediction['tuple_consistent']
                                              else 'inconsistent_native_projection'),
                           action_violations_against_development_premises=old.native.tuple_violations(
                               dict(anchors, recommendation=labels['recommendation'])))
                if request['diagnostic_premises'] is not None:
                    row['premise_echo_matches'] = all(labels[k] == v for k, v in anchors.items())
                if request['case_id'] == old.BDD:
                    row['bdd_reuse_diagnostic'] = ('reuse_selected' if labels['recommendation'] == 'reuse_specification'
                                                   else 'existing_specification_not_reused')
            except ChoiceContractError as error:
                row.update(native_status='invalid', projection_status='native_invalid', rejection_code=error.code)
        rows.append(row)
    return dict(study=STUDY, status='source_bound_native_diagnostic_not_accuracy_scored', rows=rows,
                requests_without_response_rows=[rid for rid in expected if rid not in seen],
                response_file_sha256=digest(snapshot) if snapshot is not None else None,
                execution_inferred_from_missing_rows=False, transport_ledger_verified=False,
                full_v4_1_annotation=False, provider_scoring_enabled=False, metric_effect='none')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write', action='store_true')
    group.add_argument('--stage', type=Path)
    group.add_argument('--inspect', type=Path)
    args = parser.parse_args()
    if args.stage:
        result = stage(args.stage, args.run)
    elif args.inspect:
        result = inspect(args.inspect, args.run)
    else:
        write(args.run) if args.write else verify(args.run)
        result = dict(study=STUDY, prepared=True, planned_requests=18, max_network_attempts=54, inference=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
