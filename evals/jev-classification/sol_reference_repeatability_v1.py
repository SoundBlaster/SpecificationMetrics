"""Replay the authorized Sol 6.1 Medium annotation cohort and source witnesses."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from coreinfra_retry_run import decode, sha
from paired_blind_reference_v1 import AXES, PREPARATION, require
from paired_reference_repeatability_v1 import (
    ANNOTATIONS, ROOT, agreement, producers as preparation_producers, verify as verify_plan,
)
from retrieval_index_v1.source import encoded

CONTRACT = 'specmetrics.sol-reference-repeatability/v1'
PREPARED = ROOT / 'runs/2026-10-18-paired-reference-repeatability-v1'
RUN = ROOT / 'runs/2026-10-18-sol61-medium-repeatability-v1'
CAPTURE = 'delivered_final_json_values_transcribed_formatting_normalized_not_provider_wire'


def expected_configuration():
    return dict(contract='specmetrics.annotation-model-configuration/v1', requested_model='gpt-6.1-sol',
        reasoning_effort='medium', fork_turns='none', model_override_explicit=True,
        decoding_parameters=None, seed=None, backend_revision=None,
        runtime_attestation='not_exposed_by_spawn_tool',
        shared_filesystem_isolation='instruction_bounded_not_os_sandbox',
        brief_sha256=sha((ANNOTATIONS / 'annotation-brief.txt').read_bytes()),
        rubric_sha256=sha((ANNOTATIONS / 'annotation-rubric.json').read_bytes()),
        prompt_policy='exact_frozen_prepared_task_prompt_no_added_labels_or_parent_history')


def validate_annotation(annotation, task, agent, rubric):
    require(set(annotation) == {'view_id', 'status', 'annotator', *AXES, 'rationale', 'source_locators', 'unresolved'},
            'annotation field set differs')
    require(annotation['view_id'] == task['view_id'] and annotation['annotator'] == agent
            and annotation['status'] == 'completed', 'annotation context/view identity differs')
    require(all(annotation[a] in rubric[a]['criteria'] for a in AXES), 'unknown annotation category')
    require(isinstance(annotation['rationale'], str) and bool(annotation['rationale'].strip())
            and isinstance(annotation['unresolved'], list)
            and all(isinstance(x, str) and x.strip() for x in annotation['unresolved']), 'malformed annotation explanation')
    state = decode((PREPARATION / 'blind' / task['view_id'] / 'packet.json').read_bytes())['state']
    documents = {d['id']: d for d in [state['target'], *state['retrieved_context']]}
    require(isinstance(annotation['source_locators'], list) and bool(annotation['source_locators']), 'missing source witnesses')
    witnessed = set()
    for locator in annotation['source_locators']:
        require(set(locator) == {'document_id', 'path', 'symbol', 'start_line', 'end_line', 'quote', 'evidence_for'},
                'source locator field set differs')
        require(locator['document_id'] in documents, 'citation outside supplied view')
        source = documents[locator['document_id']]['source']
        quote = locator['quote']
        require(isinstance(quote, str) and bool(quote) and quote in source['code'], 'quote not in supplied source')
        require(locator['path'] == source['path'] and locator['symbol'] == source['symbol'], 'citation identity differs')
        require(type(locator['start_line']) is int and type(locator['end_line']) is int, 'citation line types differ')
        offset = locator['start_line'] - source['start_line']
        count = quote.count('\n') + 1
        require(offset >= 0 and locator['end_line'] == locator['start_line'] + count - 1
                and quote in '\n'.join(source['code'].splitlines()[offset:offset + count]), 'citation span differs')
        require(isinstance(locator['evidence_for'], list) and bool(locator['evidence_for'])
                and set(locator['evidence_for']) <= set(AXES), 'invalid witness axes')
        witnessed.update(locator['evidence_for'])
    require({a for a in AXES if annotation[a] not in ('unknown', 'insufficient')} <= witnessed,
            'non-unknown label lacks supplied source witness')
    return ((annotation['concern_kind'] == 'unknown') != (annotation['evidence_confidence'] == 'insufficient')
            or annotation['ownership'] != 'unknown' and annotation['tool_responsibility'] == 'yes')


def analyze(run):
    plan = verify_plan(PREPARED)
    config_raw = (run / 'configuration.json').read_bytes()
    configuration = expected_configuration()
    require(config_raw == (encoded(configuration) + '\n').encode(), 'requested configuration differs')
    config_sha = sha(encoded(configuration).encode())
    start = decode((run / 'run-start.json').read_bytes())
    started = datetime.fromisoformat(start['started_at'])
    require(started.tzinfo is not None, 'run start lacks timezone')
    require(all(type(start[k]) is int for k in ('max_contexts', 'automatic_retries', 'hosted_coreinfra_requests')),
            'execution budget counter types differ')
    require(start == dict(contract='specmetrics.annotation-repeatability-execution/v1', status='running',
        started_at=start['started_at'],
        authorization='user explicitly authorized 24 fresh context-free Sol 6.1 Medium repeats then disagreement analysis; top line strong-model comparator',
        configuration_sha256=config_sha, configuration_file_sha256=sha(config_raw),
        preparation_receipt_sha256=sha((PREPARED / 'receipt.json').read_bytes()),
        planned_tasks=[t['task_id'] for t in plan['tasks']],
        source_head='64ade481f8afc32fcb4f3b87ff833caf2c22e870', max_contexts=24, automatic_retries=0,
        hosted_coreinfra_requests=0, reference_authority='model_specific_top_line_not_semantic_truth'), 'execution binding differs')
    tasks = {t['task_id']: t for t in plan['tasks']}
    require({p.name for p in (run / 'raw').iterdir()} == {tid + '.json' for tid in tasks}, 'raw output inventory differs')
    rubric = decode((ANNOTATIONS / 'annotation-rubric.json').read_bytes())['questions']
    historical = decode((ANNOTATIONS / 'reference.json').read_bytes())['views']
    prior_agents = {r['actual_agent'] for pair in decode((ANNOTATIONS / 'analysis.json').read_bytes())['pairs'] for r in pair['views'].values()}
    dispatched, sealed, identities, rows, consistency = {}, set(), set(), [], []
    last_time = started
    for event in map(decode, (run / 'dispatch.jsonl').read_bytes().splitlines()):
        tid = event['task_id']
        require(tid in tasks, 'unplanned annotation task')
        timestamp = datetime.fromisoformat(event['recorded_at'])
        require(timestamp.tzinfo is not None and timestamp >= last_time, 'registration timestamps out of order')
        last_time = timestamp
        task = tasks[tid]
        agent = event['actual_agent']
        if event['event'] == 'dispatch_registered':
            require(tid not in dispatched and agent not in identities | prior_agents,
                    'reused annotation task or exposed execution context')
            require(agent == '/root/' + tid.replace('-', '_', 1), 'unexpected execution identity')
            require(tid == plan['tasks'][len(dispatched)]['task_id'], 'dispatch order differs from frozen interleaving')
            require(event == dict(event='dispatch_registered', task_id=tid, actual_agent=agent,
                requested_model='gpt-6.1-sol', reasoning_effort='medium', fork_turns='none',
                configuration_sha256=config_sha, prompt_sha256=task['prompt_sha256'], input_sha256=task['input_sha256'],
                recorded_at=event['recorded_at'], timestamp_semantics='registration_after_tool_response_not_exact_spawn_time'),
                'dispatch configuration/prompt/input binding differs')
            dispatched[tid] = event
            identities.add(agent)
        elif event['event'] == 'annotation_sealed':
            require(tid in dispatched and tid not in sealed and agent == dispatched[tid]['actual_agent'], 'unbound/repeated seal')
            raw = (run / 'raw' / (tid + '.json')).read_bytes()
            require(event == dict(event='annotation_sealed', task_id=tid, actual_agent=agent,
                annotation_sha256=sha(raw), capture=CAPTURE, recorded_at=event['recorded_at']), 'sealed annotation bytes differ')
            annotation = decode(raw)
            if validate_annotation(annotation, task, agent, rubric):
                consistency.append(tid)
            rows.append(dict(task_id=tid, execution_id=agent, configuration_sha256=config_sha,
                input_sha256=task['input_sha256'], labels={a: annotation[a] for a in AXES}))
            sealed.add(tid)
        else:
            raise ValueError('unknown execution event')
    require(sealed == set(tasks) and len(identities) == 24, 'incomplete 24-context execution')
    diagnostic = agreement(plan, rows, config_sha)
    old_by_view = {r['view_id']: r for r in historical}
    comparisons = []
    for view in diagnostic['per_view']:
        old = old_by_view[view['view_id']]
        consensus = {a: values[0] if len(values) == 1 else None for a, values in view['distinct_labels'].items()}
        historical_changes = [a for a in AXES if consensus[a] != old['labels'][a]]
        comparisons.append(dict(view_id=view['view_id'], case_id=old['case_id'], arm=old['arm'], labels=consensus,
            differing_from_historical=historical_changes,
            needs_adjudication=bool(view['differing_axes'] or historical_changes)
                or any(r['task_id'] in consistency for r in rows if tasks[r['task_id']]['view_id'] == view['view_id'])))
    return dict(contract=CONTRACT, status='complete_source_checked_repeatability', requested_configuration=configuration,
        configuration_sha256=config_sha, annotations=24, diagnostic=diagnostic,
        source_witnesses_verified=True, consistency_review_tasks=consistency, historical_comparison=comparisons,
        historical_comparison_authority='descriptive_label_comparison_not_accuracy',
        top_line_status='provisional_strong_model_comparator_requires_adjudication' if consistency or any(v['needs_adjudication'] for v in comparisons)
            else 'source_auditable_strong_model_comparator',
        independent_semantic_truth_verified=False, runtime_configuration_attested=False,
        transcript_capture=CAPTURE, actual_hidden_reads_audited=False,
        paired_quality_scoring_allowed=False, hosted_coreinfra_requests=0, metric_effect='none')


def producers():
    return dict(preparation_producers(), **{Path(__file__).name: sha(Path(__file__).read_bytes())})


def top_line(analysis, run):
    return dict(contract='specmetrics.strong-model-top-line/v1', requested_model='gpt-6.1-sol', reasoning_effort='medium',
        status=analysis['top_line_status'], authority='evaluation_comparator_not_accepted_domain_facts_or_mathematical_upper_bound',
        configuration_sha256=analysis['configuration_sha256'], observations_per_view=3,
        source_witnesses_verified=True, same_view_primary_stable=analysis['diagnostic']['primary_stable_in_pilot'],
        adjudication_sha256=sha((run / 'adjudication.md').read_bytes()),
        adjudicator='history_aware_root_integrator_not_independent_semantic_truth',
        independent_semantic_truth_verified=False, paired_quality_scoring_allowed=False,
        views=analysis['historical_comparison'])


def seal(run):
    analysis = analyze(run)
    for name, value in [('analysis.json', analysis), ('top-line.json', top_line(analysis, run))]:
        with (run / name).open('x') as stream:
            stream.write(encoded(value) + '\n')
    files = {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*') if p.is_file()}
    receipt = dict(contract=CONTRACT, status='complete', file_sha256=files, producer_sha256=producers(),
        preparation_receipt_sha256=sha((PREPARED / 'receipt.json').read_bytes()), hosted_coreinfra_requests=0,
        independent_semantic_truth_verified=False, paired_quality_scoring_allowed=False)
    with (run / 'receipt.json').open('x') as stream:
        stream.write(encoded(receipt) + '\n')
    return verify(run)


def verify(run):
    files = {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*') if p.is_file() and p != run / 'receipt.json'}
    expected = dict(contract=CONTRACT, status='complete', file_sha256=files, producer_sha256=producers(),
        preparation_receipt_sha256=sha((PREPARED / 'receipt.json').read_bytes()), hosted_coreinfra_requests=0,
        independent_semantic_truth_verified=False, paired_quality_scoring_allowed=False)
    require(encoded(decode((run / 'receipt.json').read_bytes())) == encoded(expected), 'completion receipt differs')
    analysis = analyze(run)
    require(decode((run / 'analysis.json').read_bytes()) == analysis, 'saved repeatability differs')
    require(decode((run / 'top-line.json').read_bytes()) == top_line(analysis, run), 'saved top line differs')
    return analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    result = seal(args.run) if args.seal else verify(args.run)
    print(json.dumps(dict(status=result['status'], annotations=result['annotations'],
        primary_stable=result['diagnostic']['primary_stable_in_pilot'],
        per_axis=result['diagnostic']['per_axis'], consistency_review_tasks=result['consistency_review_tasks'],
        top_line_status=result['top_line_status'])))


if __name__ == '__main__':
    main()
