"""Validate scenario annotation evidence; never infer or correct semantic labels."""
import argparse
import json
from pathlib import Path

from question_grouping import canonical, digest

RUN = Path(__file__).parent / 'runs/2026-10-13-contrastive-preparation'
AXES = ('opportunity', 'concern_kind')


def validate(packet, reference):
    if reference.get('schema_version') != 1 or reference.get('status') != 'independent_model_annotation_not_human_gold':
        raise ValueError('Unexpected annotation authority')
    isolation = reference.get('isolation', {})
    if isolation.get('context_inheritance') != 'none' or isolation.get('other_sources_used') is not False:
        raise ValueError('Independent input scope not declared')
    inputs = isolation.get('inputs_read')
    if (not isinstance(inputs, list) or len(inputs) != 2 or any(not isinstance(p, str) for p in inputs)
            or {Path(p).name for p in inputs} != {'case-packet.json', 'annotation-template.json'}):
        raise ValueError('Unexpected declared annotation inputs')
    cases = {c['case_id']: c for c in packet['cases']}
    rows = reference['annotations']
    if len(cases) != len(packet['cases']) or len(rows) != len(cases) or {r['case_id'] for r in rows} != set(cases):
        raise ValueError('Expected exactly one annotation for each case')
    for row in rows:
        case = cases[row['case_id']]
        state = case['state']
        if row['state_sha256'] != case['state_sha256'] or row['state_sha256'] != digest(canonical(state)):
            raise ValueError('Annotation task state mismatch')
        for axis in AXES:
            if not isinstance(row[axis], str) or row[axis] not in packet['questions'][axis]['criteria']:
                raise ValueError('Unknown rubric label')
            rationale = row['rationale'][axis]
            if not isinstance(rationale, str) or not rationale.strip():
                raise ValueError('Each axis needs a rationale')
        context = state['bounded_context']
        sources = {'target': state['target']['code'], 'limitations': context['limitations'],
                   **{f['fragment_id']: f['code'] for f in context['fragments']}}
        if 'scenario_contract' in context:
            sources['scenario_contract'] = context['scenario_contract']
        evidence = row['evidence_quotes']
        if not isinstance(evidence, list) or not evidence:
            raise ValueError('Expected exact case-local evidence quotes')
        supported = set()
        for item in evidence:
            quote, axes = item['quote'], item['supports_axes']
            if (item['location'] not in sources or not isinstance(quote, str) or not quote.strip()
                    or quote not in sources[item['location']]):
                raise ValueError('Evidence quote absent from this case/location')
            if (not isinstance(axes, list) or not axes or any(a not in AXES for a in axes)
                    or len(set(axes)) != len(axes)):
                raise ValueError('Invalid evidence axis coverage')
            supported.update(axes)
        if supported != set(AXES):
            raise ValueError('Evidence must support both axes')
        if not isinstance(row['uncertainties'], list) or any(not isinstance(u, str) or not u.strip() for u in row['uncertainties']):
            raise ValueError('Expected explicit uncertainty strings')
    return {'annotated_cases': len(rows), 'packet_sha256': digest(canonical(packet)),
            'authority': 'independent_model_annotation_not_human_gold',
            'structural_evidence_validation': 'passed',
            'semantic_correctness_verified': False,
            'isolation_validation': 'self_report_and_assignment_scope_not_filesystem_enforcement'}


def compare(packet, reference, proposals, mapping):
    validation = validate(packet, reference)
    ids = {r['case_id'] for r in reference['annotations']}
    if (len(proposals['annotations']) != len(ids) or {r['case_id'] for r in proposals['annotations']} != ids
            or len(mapping['cases']) != len(ids) or {r['case_id'] for r in mapping['cases']} != ids):
        raise ValueError('Comparison inputs must cover the exact same cases')
    proposed = {r['case_id']: r for r in proposals['annotations']}
    mapped = {r['case_id']: r for r in mapping['cases']}
    for row in reference['annotations']:
        if proposed[row['case_id']]['state_sha256'] != row['state_sha256'] or mapped[row['case_id']]['state_sha256'] != row['state_sha256']:
            raise ValueError('Stale proposal or mapping state')
    disagreements = []
    for row in reference['annotations']:
        changed = [axis for axis in AXES if row[axis] != proposed[row['case_id']][axis]]
        if changed:
            disagreements.append({'case_id': row['case_id'], 'pair_id': mapped[row['case_id']]['pair_id'],
                                  'axes': changed, 'proposal': {a: proposed[row['case_id']][a] for a in AXES},
                                  'independent': {a: row[a] for a in AXES}})
    return {'validation': validation,
            'proposal_agreement': {a: {'matched': sum(r[a] == proposed[r['case_id']][a] for r in reference['annotations']),
                                      'total': len(ids)} for a in AXES},
            'disagreements': disagreements,
            'uncertainties': [{'case_id': r['case_id'], 'original_uncertainties': r['uncertainties']}
                              for r in reference['annotations'] if r['uncertainties']],
            'label_overrides': [], 'jev_luna_requests': 0,
            'interpretation': 'Agreement with author hypotheses is not provider accuracy, human gold or automatic semantic approval.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    args = parser.parse_args()
    def read(name):
        return json.loads((args.run / name).read_text())
    result = compare(read('case-packet.json'), read('independent-annotations.json'),
                     read('author-proposals.json'), read('source-mapping.json'))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
