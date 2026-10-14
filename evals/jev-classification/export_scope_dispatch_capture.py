"""Export selected dispatch/write evidence; never exports full private sessions.

Use only on operator-reviewed logs. Extracted writer calls contain source code;
this exporter does not redact secrets automatically. It never executes that code.
"""
import argparse
import json
from pathlib import Path
import re

from scope_dispatch_provenance import command_from_call, project_incoming, project_spawn, require, sha, validate_capture


META_KEYS = ('id', 'parent_thread_id', 'timestamp', 'agent_path', 'source')


def export(coordinator_log, session_directory, source_run, destination, unretained=False):
    coordinator_log, session_directory = Path(coordinator_log), Path(session_directory)
    source_run, destination = Path(source_run), Path(destination)
    require(not destination.exists(), 'Destination exists; do not overwrite capture')
    session_rows = []
    for path in session_directory.glob('*.jsonl'):
        with path.open('rb') as stream:
            first = stream.readline()
        event = json.loads(first)
        if event.get('type') == 'session_meta':
            meta = event['payload']
            session_rows.append((path, first, meta))
    coordinator_bytes = coordinator_log.read_bytes()
    lines = coordinator_bytes.splitlines(keepends=True)
    events = [json.loads(line) for line in lines]
    coordinator = events[0]['payload']
    replies = {}
    for i, event in enumerate(events):
        p = event.get('payload', {})
        if p.get('type') == 'function_call_output':
            require(p['call_id'] not in replies, 'Duplicate coordinator tool response')
            replies[p['call_id']] = i
    folders = {p.name: str(p.resolve()) for p in (source_run / 'delivery').glob('annotator-*') if p.is_dir()}
    pending = []
    for i, event in enumerate(events):
        payload = event.get('payload', {})
        if payload.get('type') != 'function_call' or payload.get('name') != 'spawn_agent':
            continue
        args = json.loads(payload['arguments'])
        if args.get('fork_turns') != 'none':
            continue
        j = replies[payload['call_id']]
        require(j > i, 'Tool result precedes spawn request')
        returned = json.loads(events[j]['payload']['output'])['task_name']
        candidates = [(p, first, meta) for p, first, meta in session_rows
                      if meta.get('agent_path') == returned and meta.get('parent_thread_id') == coordinator['id']]
        require(len(candidates) == 1, 'Actual returned task must identify exactly one child session')
        child_path, first, child = candidates[0]
        child_bytes = child_path.read_bytes()
        child_lines = child_bytes.splitlines(keepends=True)
        child_events = [json.loads(line) for line in child_lines]
        writers = []
        for k, child_event in enumerate(child_events):
            p = child_event.get('payload', {})
            if p.get('type') == 'custom_tool_call' and 'annotations.json' in p.get('input', ''):
                command = command_from_call(child_event)
                if re.search(r'write_text|writeFileSync|json\.dump', command):
                    writers.append(k)
        require(len(writers) == 1, 'Expected one child annotation writer; inspect deviations')
        k = writers[0]
        results = [n for n, e in enumerate(child_events) if e.get('payload', {}).get('type') == 'custom_tool_call_output'
                   and e['payload'].get('call_id') == child_events[k]['payload']['call_id']]
        require(len(results) == 1 and results[0] > k, 'Child writer result missing or ambiguous')
        command = command_from_call(child_events[k])
        slots = [slot for slot, folder in folders.items() if folder in command]
        require(len(slots) == 1, 'Child writer must identify exactly one assigned output folder')
        incoming = [n for n, e in enumerate(child_events) if e.get('payload', {}).get('type') == 'agent_message']
        require(len(incoming) == 1, 'Expected one initial task; inspect follow-up/context deviations')
        pending.append((slots[0], i, j, child_path, child_bytes, child, k, results[0], incoming[0]))
    require(len(pending) == len(folders) and len({r[0] for r in pending}) == len(folders),
            'Dispatch evidence does not cover each slot exactly once')
    destination.mkdir(parents=True, exist_ok=False)

    def save(name, path, raw, line_index, projection=None):
        line = raw.splitlines(keepends=True)[line_index]
        event = json.loads(line)
        if projection == 'meta':
            event = {'projection': 'session_meta_allowlist_v1',
                     'fields': {k: event['payload'].get(k) for k in META_KEYS}}
            retained = (json.dumps(event, indent=2) + '\n').encode()
        elif projection in ('spawn', 'incoming'):
            event = project_spawn(event) if projection == 'spawn' else project_incoming(event)
            retained = (json.dumps(event, indent=2) + '\n').encode()
        else:
            retained = line
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(retained)
        session_id = json.loads(raw.splitlines()[0])['payload']['id']
        return {'path': name, 'sha256': sha(retained), 'session_id': session_id,
                'source_file': path.name, 'source_file_sha256': sha(raw),
                'source_line': line_index + 1, 'source_line_sha256': sha(line)}

    coord_binding = save('evidence/coordinator-session.json', coordinator_log, coordinator_bytes, 0, 'meta')
    records = []
    for slot, i, j, child_path, child_bytes, child, k, m, incoming in pending:
        attempt = slot + '-attempt-01'
        raw_path = ('delivery/' + slot + '/annotations.json' if unretained
                    else 'raw-attempts/' + attempt + '/annotations.json')
        receipt_path = ('delivery/receipts/' + slot + '.json' if unretained
                        else 'attempt-receipts/' + attempt + '.json')
        records.append({'slot': slot, 'coordinator_session_id': coordinator['id'],
                        'attempt_stage': 'delivered_unretained' if unretained else 'retained_historical',
                        'child_session_id': child['id'],
                        'coordinator_session': coord_binding,
                        'spawn_call': save('evidence/' + slot + '/spawn-call.json', coordinator_log, coordinator_bytes, i, 'spawn'),
                        'spawn_result': save('evidence/' + slot + '/spawn-result.json', coordinator_log, coordinator_bytes, j),
                        'child_session': save('evidence/' + slot + '/child-session.json', child_path, child_bytes, 0, 'meta'),
                        'incoming_task': save('evidence/' + slot + '/incoming-task.json', child_path, child_bytes, incoming, 'incoming'),
                        'writer_call': save('evidence/' + slot + '/writer-call.json', child_path, child_bytes, k),
                        'writer_result': save('evidence/' + slot + '/writer-result.json', child_path, child_bytes, m),
                        'raw_path': raw_path, 'raw_output_sha256': sha((source_run / raw_path).read_bytes()),
                        'attempt_receipt_path': receipt_path})
    capture = {'schema': 'scope-dispatch-capture-v1', 'capture_kind': 'retrospective_unsigned_operator_extract',
               'full_private_logs_exported': False, 'runtime_identity_verified': False,
               'filesystem_isolation_verified': False, 'records': records}
    (destination / 'dispatch-capture.json').write_text(json.dumps(capture, indent=2) + '\n')
    # No ready receipt is emitted on failure. Leave partial evidence for diagnosis.
    results = validate_capture(destination, source_run)
    (destination / 'capture-complete.json').write_text(json.dumps({'verified_attempts': len(results)}, indent=2) + '\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coordinator-log', type=Path, required=True)
    parser.add_argument('--session-directory', type=Path, required=True)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--unretained', action='store_true', help='First retention from delivered output and blank receipt')
    args = parser.parse_args()
    print(json.dumps(export(args.coordinator_log, args.session_directory, args.source_run, args.destination,
                            args.unretained), indent=2))


if __name__ == '__main__':
    main()
