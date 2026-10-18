"""Assess requested LLM configuration balance without treating invocations as raters."""
import argparse
import json
from pathlib import Path

from coreinfra_retry_run import decode, sha
from paired_blind_reference_v1 import (
    PROMPT_END, PROMPT_HEADER, producers as annotation_producers, verify as verify_annotations,
)
from paired_reference_qualification_v1 import ANNOTATIONS, ROOT
from retrieval_index_v1.source import encoded

CONTRACT = 'specmetrics.paired-reference-qualification/v2'


def configuration_groups(observations):
    """Group controlled settings, never execution IDs or treatment-specific inputs."""
    groups = {}
    identities = set()
    for row in observations:
        if row['execution_id'] in identities or row['arm'] not in ('baseline', 'retrieval'):
            raise ValueError('reused execution context or unknown evidence mode')
        identities.add(row['execution_id'])
        config = row['requested_configuration']
        key = sha(encoded(config).encode())
        group = groups.setdefault(key, dict(requested_configuration=config,
            mode_counts={'baseline': 0, 'retrieval': 0}, execution_ids=[]))
        group['mode_counts'][row['arm']] += 1
        group['execution_ids'].append(row['execution_id'])
    for group in groups.values():
        counts = group['mode_counts']
        group['equal_mode_exposure'] = counts['baseline'] > 0 and counts['baseline'] == counts['retrieval']
        group['execution_ids'].sort()
    return groups


def historical_configurations(analysis):
    dispatch = {e['task_id']: e for e in
        map(decode, (ANNOTATIONS / 'dispatch.jsonl').read_bytes().splitlines())
        if e['event'] == 'annotation_dispatched'}
    observations = []
    for pair in analysis['pairs']:
        for arm, view in pair['views'].items():
            event = dispatch[view['task_id']]
            config = dict(selection=event['model_selection'], model=None, reasoning_effort=None,
                decoding_parameters=None, backend_revision=None, fork_turns=event['fork_turns'],
                brief_sha256=sha((ANNOTATIONS / 'annotation-brief.txt').read_bytes()),
                rubric_sha256=sha((ANNOTATIONS / 'annotation-rubric.json').read_bytes()),
                prompt_shape_sha256=sha(encoded([PROMPT_HEADER, 'four_assigned_input_paths', PROMPT_END]).encode()))
            observations.append(dict(execution_id=view['actual_agent'], arm=arm,
                requested_configuration=config))
    return configuration_groups(observations)


def qualify():
    analysis = verify_annotations(ANNOTATIONS)
    groups = historical_configurations(analysis)
    balanced = bool(groups) and all(g['equal_mode_exposure'] for g in groups.values())
    return dict(contract=CONTRACT, supersedes_interpretation='specmetrics.paired-reference-qualification/v1',
        status='requested_configuration_balanced_repeatability_pending' if balanced else 'requested_configuration_imbalanced',
        annotation_receipt_sha256=sha((ANNOTATIONS / 'receipt.json').read_bytes()),
        reference_sha256=sha((ANNOTATIONS / 'reference.json').read_bytes()), integrity_verified=True,
        execution_contexts=analysis['fresh_agent_contexts'], requested_configuration_groups=groups,
        requested_configuration_balanced=balanced, runtime_configuration_verified=False,
        runtime_configuration_status='not_exposed_by_historical_spawn_tool',
        agent_id_interpretation='execution_and_context_identity_not_stable_llm_rater_identity',
        identity_only_confound_rejection=False, repeatability_status='not_measured_same_view',
        cross_view_agreement_is_repeatability=False, independent_semantic_truth_verified=False,
        paired_quality_scoring_allowed=False,
        reasons=['actual_backend_configuration_unobserved', 'same_view_repeatability_not_measured',
                 'historical_baseline_first_wave_and_time_effects_unestimated',
                 'reference_remains_provisional_not_independent_semantic_truth'],
        diagnostic_labels_available=True, h3_transport_checks_independent_of_reference_design=True,
        historical_scoring_v1_unchanged=True, inference_authorized=False, metric_effect='none')


def producers():
    names = ['paired_reference_qualification_v1.py', Path(__file__).name]
    return dict(annotation_producers(), **{name: sha((ROOT / name).read_bytes()) for name in names})


def freeze(output):
    result = qualify()
    output.mkdir(parents=False, exist_ok=False)
    raw = (encoded(result) + '\n').encode()
    (output / 'qualification.json').write_bytes(raw)
    (output / 'receipt.json').write_text(encoded(dict(contract=CONTRACT,
        file_sha256={'qualification.json': sha(raw)}, producer_sha256=producers())) + '\n')
    return verify(output)


def verify(output):
    if {p.name for p in output.iterdir()} != {'qualification.json', 'receipt.json'}:
        raise ValueError('qualification file inventory differs')
    raw = (output / 'qualification.json').read_bytes()
    expected = dict(contract=CONTRACT, file_sha256={'qualification.json': sha(raw)}, producer_sha256=producers())
    if decode((output / 'receipt.json').read_bytes()) != expected or decode(raw) != qualify():
        raise ValueError('qualification differs from reconstructed configuration assessment')
    return decode(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    result = freeze(args.freeze) if args.freeze else verify(args.verify)
    print(json.dumps(dict(status=result['status'], requested_configuration_balanced=result['requested_configuration_balanced'],
        paired_quality_scoring_allowed=result['paired_quality_scoring_allowed'])))


if __name__ == '__main__':
    main()
