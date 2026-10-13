"""Prepare balanced annotation deliveries from frozen context states; offline."""
import argparse
import json
from pathlib import Path

from prepare_context_evidence import MODES, RUN as SOURCE, build as original_preparation
from question_grouping import canonical, digest

RUN = SOURCE.parent / '2026-10-13-balanced-context-reference'


def build(source=SOURCE):
    # Retain the earlier producer/receipt and validate them before redistribution.
    for name, expected in original_preparation(source).items():
        if canonical(json.loads((source / name).read_text())) != canonical(expected):
            raise ValueError('Original frozen preparation differs: ' + name)
    def read(name):
        return json.loads((source / name).read_text())
    packet = read('case-packet.json')
    mapping = read('source-mapping.json')
    template = read('annotation-template.json')
    target_ids = sorted({m['target_id'] for m in mapping['cases']})
    if len(target_ids) != 6:
        raise ValueError('Expected six source targets')
    mapped = []
    for item in mapping['cases']:
        slot = (MODES.index(item['evidence_mode']) - target_ids.index(item['target_id'])) % 3 + 1
        mapped.append({**item, 'annotation_packet': f'annotation-packet-{slot:02d}.json'})
    outputs = {'source-mapping.json': {**mapping, 'cases': mapped}}
    for slot in (1, 2, 3):
        name = f'annotation-packet-{slot:02d}.json'
        members = [m for m in mapped if m['annotation_packet'] == name]
        if (len(members) != 6 or len({m['target_id'] for m in members}) != 6
                or any(sum(m['evidence_mode'] == mode for m in members) != 2 for mode in MODES)):
            raise ValueError('Each annotator must see six distinct targets and two cases per mode')
        ids = {m['case_id'] for m in members}
        outputs[name] = {**packet, 'cases': [c for c in packet['cases'] if c['case_id'] in ids]}
        outputs[f'annotation-template-{slot:02d}.json'] = {
            **template, 'annotations': [r for r in template['annotations'] if r['case_id'] in ids]}
    if len({c['case_id'] for n, p in outputs.items() if n.startswith('annotation-packet') for c in p['cases']}) != 18:
        raise ValueError('Balanced delivery lost or duplicated source states')
    outputs['balanced-preparation-receipt.json'] = {
        'status': 'balanced_delivery_prepared_annotation_pending',
        'design': 'cyclic_three_by_three_all_modes_twice_per_annotator_one_view_per_target',
        'causal_inference_claimed': False, 'new_jev_luna_requests': 0, 'metric_effect': 'none',
        'source_directory': source.name,
        'source_file_sha256': {n: digest((source / n).read_bytes()) for n in
                               ('case-packet.json', 'source-mapping.json', 'annotation-template.json', 'preparation-receipt.json')},
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_sha256': {n: digest(canonical(v)) for n, v in outputs.items()}}
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true', help='Create new deliveries; never overwrite')
    args = parser.parse_args()
    outputs = build()
    if args.write and any((args.run / name).exists() for name in outputs):
        raise ValueError('Refusing to overwrite balanced deliveries')
    if args.write:
        args.run.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        if args.write:
            with (args.run / name).open('x') as out:
                json.dump(value, out, indent=2); out.write('\n')
        elif canonical(json.loads((args.run / name).read_text())) != canonical(value):
            raise ValueError('Saved balanced delivery differs: ' + name)
    print(json.dumps({'annotation_cases': 18, 'targets_per_annotator': 6,
                      'cases_per_mode_per_annotator': 2, 'jev_luna_requests': 0}))


if __name__ == '__main__':
    main()
