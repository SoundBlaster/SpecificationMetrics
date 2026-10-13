"""Compare same-input independent annotations; no voting or reference promotion."""
import json
from pathlib import Path

from prepare_balanced_context_reference import RUN, SOURCE
from question_grouping import canonical, digest
from validate_context_annotations import AXES, build


def compare(prior=SOURCE, current=RUN):
    # Structural validation is a prerequisite, not a semantic approval.
    receipts = [build(folder) for folder in (prior, current)]
    sets = []
    bindings = []
    for folder in (prior, current):
        rows = []
        inputs = []
        for slot in ('01', '02', '03'):
            name = f'independent-annotations-{slot}.json'
            raw = (folder / name).read_bytes()
            rows.extend(json.loads(raw)['annotations'])
            inputs.append({'file': folder.name + '/' + name, 'sha256': digest(raw)})
        sets.append({r['case_id']: r for r in rows})
        bindings.extend(inputs)
    if set(sets[0]) != set(sets[1]):
        raise ValueError('Reference rounds must cover the same exact states')
    pairs = []
    for cid in sorted(sets[0]):
        before, after = [s[cid] for s in sets]
        if before['state_sha256'] != after['state_sha256']:
            raise ValueError('Cannot treat changed evidence as a same-input repeat')
        pairs.append({'case_id': cid, 'state_sha256': before['state_sha256'],
                      'prior': {a: before[a] for a in AXES}, 'balanced': {a: after[a] for a in AXES},
                      'changed_axes': [a for a in AXES if before[a] != after[a]]})
    return {'status': 'same_input_annotation_comparison_not_provider_accuracy',
            'input_file_sha256': bindings, 'producer_sha256': digest(Path(__file__).read_bytes()),
            'validated_round_receipt_sha256': [digest(canonical(r)) for r in receipts],
            'cases': pairs,
            'agreement': {a: {'matched': sum(a not in p['changed_axes'] for p in pairs), 'total': len(pairs)} for a in AXES},
            'label_overrides': [], 'jev_luna_requests': 0,
            'interpretation': 'Same case state, profile and rubric; fresh annotators and packet composition differ. Agreement is descriptive reliability, not human gold, causal context effect or provider accuracy.'}


if __name__ == '__main__':
    print(json.dumps(compare(), indent=2))
