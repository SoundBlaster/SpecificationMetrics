"""Bind scope attempts to captured tool results and child-session output witnesses.

Reads data only: never executes retained shell, Python or JavaScript source.
Capture files are operator-retained, unsigned evidence, not runtime attestation.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import prepare_scope_binding_v3_1 as preparation
import validate_scope_binding_annotations as annotations


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def confined(root, name):
    require(isinstance(name, str), 'Expected relative artifact path')
    path = (root / name).resolve()
    require(not Path(name).is_absolute() and path.is_relative_to(root.resolve()),
            'Artifact path escapes its root')
    return path


def evidence(root, binding, session_id):
    require(binding.get('session_id') == session_id, 'Evidence belongs to a different session')
    path = confined(root, binding['path'])
    raw = path.read_bytes()
    require(sha(raw) == binding['sha256'], 'Captured evidence digest differs')
    return json.loads(raw)


def project_spawn(event):
    payload = event['payload']
    args = json.loads(payload['arguments'])
    message = args['message']
    representation = 'opaque_encrypted' if message.startswith('gAAAAA') else 'plaintext'
    return {'projection': 'spawn_request_allowlist_v1',
            'fields': {'type': payload['type'], 'name': payload['name'], 'call_id': payload['call_id'],
                       'arguments': {k: args.get(k) for k in ('task_name', 'fork_turns', 'model', 'reasoning_effort')},
                       'message_representation': representation,
                       'message_payload_sha256': sha(message.encode())}}


def project_incoming(event):
    payload = event['payload']
    encrypted = [b['encrypted_content'] for b in payload['content'] if b.get('type') == 'encrypted_content']
    require(payload.get('type') == 'agent_message' and len(encrypted) == 1,
            'Expected one captured encrypted incoming task')
    return {'projection': 'incoming_task_allowlist_v1',
            'fields': {'author': payload['author'], 'recipient': payload['recipient'],
                       'message_representation': 'opaque_encrypted',
                       'message_payload_sha256': sha(encrypted[0].encode())}}


def command_from_call(event):
    payload = event['payload']
    require(payload.get('type') == 'custom_tool_call' and payload.get('name') == 'exec',
            'Expected captured exec writer call')
    matches = re.findall(r'(?:"cmd"|cmd)\s*:\s*("(?:[^"\\]|\\.)*")', payload['input'])
    require(len(matches) == 1, 'Expected exactly one literal writer command')
    return json.loads(matches[0])


def literal_judgments(command):
    """Decode only annotation literals and two exact quote-constructor shapes."""
    if command.startswith("rtk proxy node <<'NODE'\n"):
        script = command.split('\n', 1)[1].rsplit('\nNODE', 1)[0]
        match = re.search(r'const judgments = (\{.*?\n\});', script, re.S)
        require(match is not None, 'Unsupported JavaScript judgment literal')
        tree = ast.parse(match[1], mode='eval')
        # These are object property names, never variable values or executable code.
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                node.keys = [ast.Constant(k.id) if isinstance(k, ast.Name) else k for k in node.keys]
        return ast.literal_eval(tree)
    require(command.startswith("rtk proxy python3 - <<'PY'\n"),
            'Unsupported writer command; retain a separately reviewed decoder')
    script = command.split('\n', 1)[1].rsplit('\nPY', 1)[0]
    tree = ast.parse(script)
    constructors = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ('quote', 'evidence'):
            names = [a.arg for a in node.args.args]
            require(len(names) == 3 and not node.args.defaults and not node.decorator_list
                    and len(node.body) == 1 and isinstance(node.body[0], ast.Return),
                    'Unsupported quote constructor')
            expected = ast.parse("{'axis': " + names[0] + ", 'fragment_id': " + names[1]
                                 + ", 'quote': " + names[2] + '}', mode='eval').body
            require(ast.dump(node.body[0].value) == ast.dump(expected), 'Quote constructor differs')
            constructors.add(node.name)
    candidates = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(
                isinstance(t, ast.Name) and t.id in ('judgments', 'results', 'answers') for t in node.targets):
            continue
        value = deepcopy(node.value)

        class Quotes(ast.NodeTransformer):
            def visit_Call(self, item):
                require(isinstance(item.func, ast.Name) and item.func.id in constructors
                        and len(item.args) == 3 and not item.keywords, 'Nonliteral judgment call')
                args = [ast.literal_eval(a) for a in item.args]
                require(all(isinstance(a, str) for a in args), 'Nonliteral quote arguments')
                return ast.parse(repr(dict(zip(('axis', 'fragment_id', 'quote'), args))), mode='eval').body

        candidates.append(ast.literal_eval(Quotes().visit(value)))
    require(len(candidates) == 1, 'Expected one annotation literal assembly')
    return candidates[0]


def successful_writer(event, result):
    call, reply = event['payload'], result['payload']
    require(reply.get('type') == 'custom_tool_call_output' and reply.get('call_id') == call['call_id'],
            'Writer result is not paired to writer call')
    outputs = []
    for block in reply.get('output', []):
        if block.get('type') == 'input_text':
            try:
                item = json.loads(block['text'])
            except ValueError:
                continue
            if isinstance(item, dict) and 'exit_code' in item:
                outputs.append(item)
    if outputs:
        require(len(outputs) == 1 and type(outputs[0]['exit_code']) is int
                and outputs[0]['exit_code'] == 0, 'Writer did not report successful completion')
        return True
    # One historical child printed only exec_command.output. Keep that weaker
    # evidence explicit; tool completion is not proof of the shell exit code.
    blocks = reply.get('output', [])
    require(bool(blocks) and blocks[0].get('text', '').startswith('Script completed\n'),
            'Writer tool call did not complete')
    return False


def validate_record(root, record, source):
    root, source = Path(root), Path(source)
    slot = record['slot']
    require(re.fullmatch(r'annotator-\d{2}', slot) is not None, 'Invalid slot')
    receipt = read(confined(source, record['attempt_receipt_path']))
    raw = confined(source, record['raw_path']).read_bytes()
    stage = record.get('attempt_stage', 'retained_historical')
    require(stage in ('retained_historical', 'delivered_unretained'), 'Unknown attempt stage')
    historical = stage == 'retained_historical'
    require(receipt['slot'] == slot and sha(raw) == record['raw_output_sha256'], 'Attempt/raw association differs')
    if historical:
        require(sha(raw) == receipt['raw_output_sha256'], 'Retained raw digest differs')
    else:
        require(all(receipt.get(k) is None for k in ('agent_task', 'context_inheritance', 'raw_output_sha256',
                                                     'requested_model', 'requested_reasoning_effort')),
                'First retention requires an original blank delivery receipt')
    packet = read(source / 'delivery' / slot / 'packet.json')
    template = read(source / 'delivery' / slot / 'template.json')
    planned = preparation.verify()
    assignment = next((a for a in planned['dispatch-plan.json']['assignments'] if a['slot'] == slot), None)
    require(assignment is not None, 'Unknown planned slot')
    for filename, artifact in (('packet.json', assignment['packet']), ('template.json', assignment['template'])):
        actual = (source / 'delivery' / slot / filename).read_bytes()
        require(actual == preparation.encoded(planned[artifact]), 'Frozen delivery input differs')
    require(receipt['cases'] == annotations.case_bindings(planned, assignment), 'Case assignment differs')
    coordinator_id = record['coordinator_session_id']
    coordinator = evidence(root, record['coordinator_session'], coordinator_id)
    require(coordinator.get('projection') == 'session_meta_allowlist_v1'
            and coordinator['fields']['id'] == coordinator_id, 'Coordinator session differs')
    for key in ('spawn_call', 'spawn_result'):
        require(all(record[key][field] == record['coordinator_session'][field]
                    for field in ('source_file', 'source_file_sha256')), 'Spawn event source session differs')
    for key in ('incoming_task', 'writer_call', 'writer_result'):
        require(all(record[key][field] == record['child_session'][field]
                    for field in ('source_file', 'source_file_sha256')), 'Child event source session differs')
    require(record['coordinator_session']['source_line'] == record['child_session']['source_line'] == 1
            and record['spawn_call']['source_line'] < record['spawn_result']['source_line']
            and record['incoming_task']['source_line'] < record['writer_call']['source_line']
            < record['writer_result']['source_line'], 'Captured source lifecycle order differs')
    call = evidence(root, record['spawn_call'], coordinator_id)
    reply = evidence(root, record['spawn_result'], coordinator_id)
    require(call.get('projection') == 'spawn_request_allowlist_v1', 'Missing captured spawn request')
    request, response = call['fields'], reply['payload']
    require(request.get('type') == 'function_call' and request.get('name') == 'spawn_agent',
            'Expected actual spawn tool call')
    require(response.get('type') == 'function_call_output'
            and request['call_id'] == response.get('call_id'), 'Spawn call/result mismatch')
    args, returned = request['arguments'], json.loads(response['output'])
    require(args.get('fork_turns') == 'none', 'Fresh context was not requested')
    if historical:
        require(args.get('model') == receipt['requested_model']
                and args.get('reasoning_effort') == receipt['requested_reasoning_effort'],
                'Requested model/effort differs')
    prompt = (source / 'delivery' / 'prompts' / (slot + '.txt')).read_bytes()
    require(sha(prompt) == receipt['dispatched_prompt_sha256'], 'Declared prompt file differs')
    task = returned.get('task_name')
    require(isinstance(task, str) and bool(task), 'Spawn response lacks actual task identity')
    if historical:
        require(task == receipt['agent_task'], 'Retained identity is not the returned tool identity')
    receipt.update(agent_task=task, context_inheritance=args['fork_turns'],
                   requested_model=args['model'], requested_reasoning_effort=args['reasoning_effort'],
                   raw_output_sha256=sha(raw))
    session = evidence(root, record['child_session'], record['child_session_id'])
    require(session.get('projection') == 'session_meta_allowlist_v1', 'Missing child session evidence')
    meta = session['fields']
    require(meta['agent_path'] == task and meta['parent_thread_id'] == record['coordinator_session_id'],
            'Child session/task/parent association differs')
    require(meta['source']['subagent']['thread_spawn']['agent_path'] == task
            and meta['source']['subagent']['thread_spawn']['parent_thread_id'] == meta['parent_thread_id'],
            'Child session spawn source differs')
    require(isinstance(meta['id'], str) and bool(meta['id'])
            and meta['id'] == record['child_session_id'] and meta['id'] != coordinator_id,
            'Missing or reused parent session identity')
    incoming = evidence(root, record['incoming_task'], meta['id'])
    require(incoming.get('projection') == 'incoming_task_allowlist_v1', 'Missing incoming task evidence')
    delivery = incoming['fields']
    require(delivery['author'] == coordinator['fields']['agent_path']
            and delivery['recipient'] == task, 'Incoming task routing differs')
    require(delivery['message_payload_sha256'] == request['message_payload_sha256']
            and delivery['message_representation'] == request['message_representation'],
            'Incoming task payload differs from spawn request')
    plaintext_verified = request['message_representation'] == 'plaintext'
    if plaintext_verified:
        require(request['message_payload_sha256'] == sha(prompt), 'Actual plaintext prompt differs')
    writer = evidence(root, record['writer_call'], meta['id'])
    writer_result = evidence(root, record['writer_result'], meta['id'])
    exit_code_verified = successful_writer(writer, writer_result)
    command = command_from_call(writer)
    directory = receipt['directory']
    require(directory in command and 'annotations.json' in command,
            'Writer does not reference this delivery/output')
    judgments = literal_judgments(command)
    expected = deepcopy(template)
    if isinstance(judgments, dict):
        require(set(judgments) == {r['case_id'] for r in expected['annotations']}, 'Writer case set differs')
        judgments = [judgments[r['case_id']] for r in expected['annotations']]
    require(isinstance(judgments, list) and len(judgments) == len(expected['annotations']),
            'Writer judgment count differs')
    for row, judgment in zip(expected['annotations'], judgments):
        judgment = deepcopy(judgment)
        if 'quotes' in judgment:
            judgment['evidence_quotes'] = [dict(zip(('axis', 'fragment_id', 'quote'), q))
                                          for q in judgment.pop('quotes')]
        require(set(judgment) == {'opportunity', 'concern_kind', 'rationales', 'evidence_quotes', 'uncertainties'},
                'Writer judgment fields differ')
        row.update(judgment)
    expected['status'] = 'independently_annotated_not_adjudicated'
    expected['isolation_report'] = {'input_files': [directory + '/packet.json', directory + '/template.json'],
                                  'other_inputs_read': False}
    require(json.loads(raw) == expected, 'Raw answer differs from child writer literals/template')
    annotations.validate_annotation(packet, template, json.loads(raw), receipt)
    return {'slot': slot, 'agent_task': task, 'child_session_id': meta['id'],
            'spawn_call_id': request['call_id'], 'raw_output_sha256': sha(raw),
            'requested_model': args['model'], 'requested_reasoning_effort': args['reasoning_effort'],
            'context_inheritance': args['fork_turns'], 'writer_literals_match_raw': True,
            'writer_exit_code_verified': exit_code_verified,
            'prompt_plaintext_verified': plaintext_verified,
            'runtime_model_identity_verified': False, 'filesystem_isolation_verified': False}


def validate_capture(root, source):
    root, source = Path(root), Path(source)
    capture = read(root / 'dispatch-capture.json')
    require(capture.get('schema') == 'scope-dispatch-capture-v1', 'Unsupported dispatch capture')
    records = capture['records']
    require(isinstance(records, list) and bool(records), 'Missing dispatch records')
    results = [validate_record(root, r, source) for r in records]
    for key in ('slot', 'agent_task', 'child_session_id', 'spawn_call_id'):
        require(len({r[key] for r in results}) == len(results), 'Reused dispatch identity: ' + key)
    expected_slots = {a['slot'] for a in preparation.verify()['dispatch-plan.json']['assignments']}
    require({r['slot'] for r in results} == expected_slots, 'Dispatch slot coverage is incomplete')
    return results


def verify_repair(root, source, results):
    root, source = Path(root), Path(source)
    receipt = read(root / 'provenance-repair.json')
    require(receipt['schema'] == 'scope-dispatch-provenance-repair-v1', 'Unknown repair receipt')
    require(receipt['dispatch_capture_sha256'] == sha((root / 'dispatch-capture.json').read_bytes()),
            'Repair capture binding differs')
    require(receipt['verified_contexts'] == len(results) == 12, 'Repair context count differs')
    for name, digest in receipt['historical_file_sha256'].items():
        require(sha(confined(source, name).read_bytes()) == digest, 'Historical run bytes changed')
    for line in (source / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(sha(confined(source, name).read_bytes()) == digest, 'Historical artifact changed: ' + name)
    for name, digest in receipt['implementation_file_sha256'].items():
        require(sha(confined(Path(__file__).parent, name).read_bytes()) == digest, 'Repair implementation differs')
    audit = read(root / 'source-verification.json')
    require(audit['attempts'] == results and audit['source_audit']['original_source_records_rechecked'] == 73,
            'Retained source audit differs')
    manifest = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(name not in manifest, 'Duplicate repair manifest entry')
        require(sha(confined(root, name).read_bytes()) == digest, 'Repair artifact digest differs')
        manifest[name] = digest
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != root / 'SHA256SUMS'}
    require(set(manifest) == actual, 'Repair inventory differs')
    return {'repair_inventory_verified': True, 'historical_run_unchanged': True,
            'plaintext_prompt_verified': False, 'runtime_identity_verified': False,
            'filesystem_isolation_verified': False}


def recheck_source_logs(root, source_logs):
    """Optional local check of exact source lines; no full session is exported."""
    root, source_logs = Path(root), Path(source_logs)
    capture = read(root / 'dispatch-capture.json')
    seen = set()
    count = 0
    for record in capture['records']:
        for key in ('coordinator_session', 'spawn_call', 'spawn_result', 'child_session', 'incoming_task',
                    'writer_call', 'writer_result'):
            binding = record[key]
            if binding['path'] in seen:
                continue
            seen.add(binding['path'])
            original = confined(source_logs, binding['source_file'])
            raw = original.read_bytes()
            require(sha(raw) == binding['source_file_sha256'], 'Original session digest differs')
            require(json.loads(raw.splitlines()[0])['payload']['id'] == binding['session_id'],
                    'Original event belongs to a different session')
            line = raw.splitlines(keepends=True)[binding['source_line'] - 1]
            require(sha(line) == binding['source_line_sha256'], 'Original source line differs')
            retained = evidence(root, binding, binding['session_id'])
            actual = json.loads(line)
            if retained.get('projection') == 'spawn_request_allowlist_v1':
                require(project_spawn(actual) == retained, 'Spawn request projection differs')
            elif retained.get('projection') == 'incoming_task_allowlist_v1':
                require(project_incoming(actual) == retained, 'Incoming task projection differs')
            elif retained.get('projection') == 'session_meta_allowlist_v1':
                fields = {k: actual['payload'].get(k) for k in retained['fields']}
                require(actual['type'] == 'session_meta' and fields == retained['fields'],
                        'Session metadata projection differs')
            else:
                require(retained == actual, 'Captured event differs from original')
            count += 1
    return {'original_source_records_rechecked': count, 'unsigned_operator_capture': True}


def retain(root, source, slot, destination):
    """New retention path: identity comes from captured tool output, never a slot."""
    root, source, destination = Path(root), Path(source), Path(destination)
    results = validate_capture(root, source)
    selected = [r for r in results if r['slot'] == slot]
    require(len(selected) == 1, 'Exactly one captured attempt required for slot')
    capture = read(root / 'dispatch-capture.json')
    record = next(r for r in capture['records'] if r['slot'] == slot)
    raw = confined(source, record['raw_path']).read_bytes()
    receipt = read(confined(source, record['attempt_receipt_path']))
    receipt.update(**{key: selected[0][key] for key in
                      ('agent_task', 'context_inheritance', 'requested_model', 'requested_reasoning_effort')},
                   raw_output_sha256=sha(raw))
    annotations.validate_attempt(preparation.RUN, receipt, raw)  # Original declared paths, before writing.
    receipt.update(agent_task=selected[0]['agent_task'], child_session_id=selected[0]['child_session_id'],
                   spawn_call_id=selected[0]['spawn_call_id'],
                   dispatch_capture_sha256=sha((root / 'dispatch-capture.json').read_bytes()),
                   identity_source='captured_spawn_result_and_child_session_not_slot',
                   raw_output_path=str(destination.resolve() / 'annotations.json'),
                   original_output_path=str(confined(source, record['raw_path'])),
                   runtime_model_identity_verified=False)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'annotations.json').write_bytes(raw)
    receipt_bytes = (json.dumps(receipt, indent=2) + '\n').encode()
    (destination / 'attempt-receipt.json').write_bytes(receipt_bytes)
    # Ready marker comes last; interrupted directories are incomplete, never resumable.
    marker = {**selected[0], 'receipt_sha256': sha(receipt_bytes)}
    (destination / 'retention-complete.json').write_text(json.dumps(marker, indent=2) + '\n')
    return selected[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--retain-slot')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--source-logs', type=Path)
    parser.add_argument('--verify-repair', action='store_true')
    args = parser.parse_args()
    if bool(args.retain_slot) != bool(args.destination):
        parser.error('--retain-slot and --destination must be used together')
    if args.retain_slot and (args.verify_repair or args.source_logs):
        parser.error('Run source/repair replay separately before retention')
    result = (retain(args.capture, args.source_run, args.retain_slot, args.destination)
              if args.retain_slot else validate_capture(args.capture, args.source_run))
    if args.verify_repair:
        require(not args.retain_slot, 'Repair replay is read-only')
        result = {'attempts': result, 'repair_audit': verify_repair(args.capture, args.source_run, result)}
    if args.source_logs:
        result = {'attempts': result, 'source_audit': recheck_source_logs(args.capture, args.source_logs)}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
