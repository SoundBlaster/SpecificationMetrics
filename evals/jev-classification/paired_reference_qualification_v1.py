"""Qualify annotation design separately from byte/source-evidence integrity."""
import argparse
import json
from pathlib import Path

from coreinfra_retry_run import decode, sha
from paired_blind_reference_v1 import producers as annotation_producers, verify as verify_annotations
from retrieval_index_v1.source import encoded

ROOT = Path(__file__).resolve().parent
ANNOTATIONS = ROOT / 'runs/2026-10-18-paired-blind-reference-v1'
CONTRACT = 'specmetrics.paired-reference-qualification/v1'


def qualify():
    analysis = verify_annotations(ANNOTATIONS)
    groups = {}
    for pair in analysis['pairs']:
        for arm, view in pair['views'].items():
            groups.setdefault(view['actual_agent'], {'baseline': 0, 'retrieval': 0})[arm] += 1
    balanced = sum(counts == {'baseline': 1, 'retrieval': 1} for counts in groups.values())
    # This version qualifies the fixed eight-context run only. Its immutable
    # integrity verifier requires eight identities, so it cannot establish the
    # original four-participant crossover. No opt-in flag can waive that fact.
    return dict(contract=CONTRACT, status='diagnostic_annotations_only_not_paired_reference',
        annotation_receipt_sha256=sha((ANNOTATIONS / 'receipt.json').read_bytes()),
        reference_sha256=sha((ANNOTATIONS / 'reference.json').read_bytes()),
        integrity_verified=True, actual_annotators=len(groups), balanced_actual_annotators=balanced,
        actual_annotator_modes=groups, diagnostic_labels_available=True,
        paired_quality_scoring_allowed=False,
        reasons=['evidence_mode_confounded_with_actual_annotator_identity',
                 'logical_slots_do_not_establish_actual_participant_crossover'],
        replacement='new_versioned_balanced_reference_required_for_H1_H2',
        h3_transport_checks_independent_of_reference_design=True,
        inference_authorized=False, metric_effect='none')


def producers():
    return dict(annotation_producers(), **{Path(__file__).name: sha(Path(__file__).read_bytes())})


def freeze(output):
    output.mkdir(parents=False, exist_ok=False)
    raw = (encoded(qualify()) + '\n').encode()
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
        raise ValueError('qualification differs from reconstructed design assessment')
    return decode(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    result = freeze(args.freeze) if args.freeze else verify(args.verify)
    print(json.dumps(dict(status=result['status'], paired_quality_scoring_allowed=result['paired_quality_scoring_allowed'])))


if __name__ == '__main__':
    main()
