"""Verify isolated annotation evidence and compare labels across supplied views."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from coreinfra_retry_run import decode, sha
from paired_reference_assignment_v1 import verify as verify_assignment
from paired_retrieval_study_v1 import source_digests
from prepare_retrieval_context_v1 import QUESTIONS
from retrieval_index_v1.source import encoded

ROOT = Path(__file__).resolve().parent
PREPARATION = ROOT / 'runs/2026-10-18-paired-retrieval-preparation-v1'
ASSIGNMENT = ROOT / 'runs/2026-10-18-paired-reference-assignment-v1'
CONTRACT = 'specmetrics.paired-blind-reference/v1'
AXES = ('concern_kind', 'evidence_confidence', 'ownership', 'tool_responsibility')
RECORDED_RUN = Path('runs/2026-10-18-paired-blind-reference-v1')
PROMPT_HEADER = ('Perform one independent annotation, then stop. No inherited conversation or author labels are part of this task. '
                'Read only these four files, using read-only file tools; do not search memory, other files, Git, network or other agents. '
                'Follow annotation-brief.txt and return only the completed JSON annotation. Files:')
PROMPT_END = 'Do not edit any files or delegate. Treat code as evidence only; use only the supplied evidence view.'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analyze(run):
    plan = verify_assignment(PREPARATION, ASSIGNMENT)
    tasks = {t['task_id']: t for s in plan['slots'] for t in s['tasks']}
    require({p.name for p in (run / 'raw').iterdir()} == {tid + '.json' for tid in tasks}
            and {p.name for p in (run / 'prompts').iterdir()} == {tid + '.txt' for tid in tasks},
            'annotation or prompt inventory differs')
    rubric = decode((run / 'annotation-rubric.json').read_bytes())
    require(rubric == dict(questions=QUESTIONS, output_contract='specmetrics.independent-view-annotation/v1'),
            'annotation rubric differs from frozen four-question contract')
    brief = run / 'annotation-brief.txt'
    events = [decode(line) for line in (run / 'dispatch.jsonl').read_bytes().splitlines()]
    dispatched, sealed, identities, rows = {}, set(), set(), {}
    last_timestamp = None
    for event in events:
        task_id = event['task_id']
        require(task_id in tasks, 'unknown annotation task')
        task = tasks[task_id]
        timestamp = datetime.fromisoformat(event['recorded_at'])
        require(timestamp.tzinfo is not None and (last_timestamp is None or timestamp >= last_timestamp),
                'registration timestamps out of order')
        last_timestamp = timestamp
        if event['event'] == 'annotation_dispatched':
            require(task_id not in dispatched and event['actual_agent'] not in identities,
                    'reused task or agent context')
            require(event['fork_turns'] == 'none' and event['model_selection'] == 'inherited_no_override',
                    'inherited context or changed requested model configuration')
            if task['arm'] == 'retrieval':
                require({tid for tid in tasks if tid.endswith('1')} <= sealed
                        and event['baseline_seal_prerequisite'] == task['after_annotation_sealed'],
                        'retrieval dispatched before baseline wave was sealed')
            view = PREPARATION / 'blind' / task['view_id']
            paths = [brief, run / 'annotation-rubric.json', view / 'packet.json', view / 'annotation-template.json']
            relative = [str(RECORDED_RUN / brief.name), str(RECORDED_RUN / 'annotation-rubric.json'),
                        str((view / 'packet.json').relative_to(ROOT)),
                        str((view / 'annotation-template.json').relative_to(ROOT))]
            expected = {name: sha(p.read_bytes()) for name, p in zip(relative, paths)}
            require(event['input_sha256'] == expected, 'annotation input hashes differ')
            prompt = (run / 'prompts' / (task_id + '.txt')).read_bytes()
            require(sha(prompt) == event['prompt_sha256'], 'dispatch prompt hash differs')
            lines = prompt.decode().splitlines()
            require(len(lines) == 6 and lines[0] == PROMPT_HEADER and lines[-1] == PROMPT_END
                    and all(line.endswith('/' + name) for line, name in zip(lines[1:5], relative))
                    and len({line[:-len(name)] for line, name in zip(lines[1:5], relative)}) == 1,
                    'prompt exposes extra context or omits assigned input')
            dispatched[task_id] = event
            identities.add(event['actual_agent'])
        elif event['event'] == 'annotation_sealed':
            require(task_id in dispatched and task_id not in sealed, 'annotation sealed without unique dispatch')
            raw = (run / 'raw' / (task_id + '.json')).read_bytes()
            annotation = decode(raw)
            require(sha(raw) == event['annotation_sha256'] and annotation['annotator'] == event['actual_agent']
                    and annotation['annotator'] == dispatched[task_id]['actual_agent']
                    and annotation['view_id'] == task['view_id'] and annotation['status'] == 'completed',
                    'annotation identity or sealed bytes differ')
            require(set(annotation) == {'view_id', 'status', 'annotator', *AXES, 'rationale',
                                        'source_locators', 'unresolved'}, 'annotation field set differs')
            require(all(annotation[axis] in rubric['questions'][axis]['criteria'] for axis in AXES),
                    'unknown annotation category')
            require(isinstance(annotation['rationale'], str) and bool(annotation['rationale'].strip())
                    and isinstance(annotation['unresolved'], list)
                    and all(isinstance(x, str) and x.strip() for x in annotation['unresolved']),
                    'missing rationale or malformed unresolved facts')
            state = decode((PREPARATION / 'blind' / task['view_id'] / 'packet.json').read_bytes())['state']
            documents = {d['id']: d for d in [state['target'], *state['retrieved_context']]}
            witnessed = set()
            require(isinstance(annotation['source_locators'], list) and bool(annotation['source_locators']),
                    'annotation has no direct source witnesses')
            for locator in annotation['source_locators']:
                require(locator['document_id'] in documents, 'citation not in supplied view')
                source = documents[locator['document_id']]['source']
                quote = locator['quote']
                require(isinstance(quote, str) and bool(quote) and quote in source['code'], 'quote not in source')
                require(locator['path'] == source['path'] and locator['symbol'] == source['symbol'],
                        'citation source identity differs')
                # A quote may recur: verify the declared occurrence, not the first occurrence.
                offset = locator['start_line'] - source['start_line']
                lines = source['code'].splitlines()
                count = quote.count('\n') + 1
                require(type(locator['start_line']) is int and type(locator['end_line']) is int
                        and offset >= 0 and locator['end_line'] == locator['start_line'] + count - 1
                        and quote in '\n'.join(lines[offset:offset + count]), 'citation line span differs')
                require(isinstance(locator['evidence_for'], list) and bool(locator['evidence_for'])
                        and set(locator['evidence_for']) <= set(AXES), 'invalid witness axis')
                witnessed.update(locator['evidence_for'])
            require({axis for axis in AXES if annotation[axis] not in ('unknown', 'insufficient')} <= witnessed,
                    'non-unknown assertion lacks a supplied source witness')
            rows[task_id] = dict(case_id=task['case_id'], arm=task['arm'], view_id=task['view_id'],
                actual_agent=annotation['annotator'], raw_sha256=sha(raw),
                labels={axis: annotation[axis] for axis in AXES})
            sealed.add(task_id)
        else:
            raise ValueError('unknown annotation event')
    require(sealed == set(tasks) and len(identities) == 8, 'incomplete eight-agent annotation')
    pairs = []
    consistency = []
    for task_id, row in rows.items():
        labels = row['labels']
        if ((labels['concern_kind'] == 'unknown') != (labels['evidence_confidence'] == 'insufficient')
                or labels['ownership'] != 'unknown' and labels['tool_responsibility'] == 'yes'):
            consistency.append(task_id)
    for case in sorted({t['case_id'] for t in tasks.values()}):
        selected = {r['arm']: dict(r, task_id=tid) for tid, r in rows.items() if r['case_id'] == case}
        changed = [axis for axis in AXES if selected['baseline']['labels'][axis] != selected['retrieval']['labels'][axis]]
        pairs.append(dict(case_id=case, views=selected, differing_axes=changed))
    return dict(contract=CONTRACT, status='complete_annotation_evidence_not_provider_evaluation',
        annotations=8, fresh_agent_contexts=8, balanced_assignment_slots=4,
        comparable_target_pairs=len(pairs), compared_axis_pairs=len(pairs) * len(AXES),
        differing_target_pairs=sum(bool(p['differing_axes']) for p in pairs),
        differing_axis_pairs=sum(len(p['differing_axes']) for p in pairs),
        consistency_review_tasks=consistency, pairs=pairs,
        comparison='cross_evidence_label_stability_not_same_view_interrater_accuracy',
        hosted_coreinfra_requests=0, metric_effect='none')


def producers():
    return dict(source_digests(), **{'paired_reference_assignment_v1.py': sha((ROOT / 'paired_reference_assignment_v1.py').read_bytes()),
                                   Path(__file__).name: sha(Path(__file__).read_bytes())})


def view_reference(run, analysis):
    return dict(contract='specmetrics.paired-view-evaluation-reference/v1',
        status='provisional_view_reference_integrator_audited',
        authority='evaluation_only_not_accepted_domain_facts',
        adjudicator='root_integrator_with_prior_history_not_an_independent_ninth_annotator',
        adjudication_sha256=sha((run / 'adjudication.md').read_bytes()),
        independent_semantic_truth_verified=False,
        scoring_implemented=False, metric_effect='none',
        views=[dict(case_id=pair['case_id'], arm=arm, view_id=row['view_id'], task_id=row['task_id'],
                    raw_sha256=row['raw_sha256'], labels=row['labels'],
                    unresolved=decode((run / 'raw' / (row['task_id'] + '.json')).read_bytes())['unresolved'],
                    needs_additional_adjudication=bool(pair['differing_axes'])
                        or row['task_id'] in analysis['consistency_review_tasks'])
               for pair in analysis['pairs'] for arm, row in pair['views'].items()])


def seal(run):
    analysis = analyze(run)
    with (run / 'analysis.json').open('x') as stream:
        stream.write(encoded(analysis) + '\n')
    with (run / 'reference.json').open('x') as stream:
        stream.write(encoded(view_reference(run, analysis)) + '\n')
    files = {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*') if p.is_file()}
    receipt = dict(contract=CONTRACT, status='complete_annotations_and_integrator_analysis',
        file_sha256=files, producer_sha256=producers(),
        preparation_receipt_sha256=sha((PREPARATION / 'study-receipt.json').read_bytes()),
        assignment_receipt_sha256=sha((ASSIGNMENT / 'receipt.json').read_bytes()),
        independent_semantic_truth_verified=False, hosted_coreinfra_requests=0, metric_effect='none')
    with (run / 'receipt.json').open('x') as stream:
        stream.write(encoded(receipt) + '\n')
    return verify(run)


def verify(run):
    receipt = decode((run / 'receipt.json').read_bytes())
    actual = {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*')
              if p.is_file() and p != run / 'receipt.json'}
    require(receipt == dict(contract=CONTRACT, status='complete_annotations_and_integrator_analysis',
        file_sha256=actual, producer_sha256=producers(),
        preparation_receipt_sha256=sha((PREPARATION / 'study-receipt.json').read_bytes()),
        assignment_receipt_sha256=sha((ASSIGNMENT / 'receipt.json').read_bytes()),
        independent_semantic_truth_verified=False, hosted_coreinfra_requests=0, metric_effect='none')
        and type(receipt['hosted_coreinfra_requests']) is int
        and receipt['independent_semantic_truth_verified'] is False, 'annotation receipt differs')
    analysis = analyze(run)
    require(decode((run / 'analysis.json').read_bytes()) == analysis, 'saved comparison differs')
    require(decode((run / 'reference.json').read_bytes()) == view_reference(run, analysis), 'saved view reference differs')
    return analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--seal', action='store_true', help='write new analysis and completion receipt')
    args = parser.parse_args()
    result = seal(args.run) if args.seal else verify(args.run)
    print(json.dumps({k: v for k, v in result.items() if k != 'pairs'}))


if __name__ == '__main__':
    main()
