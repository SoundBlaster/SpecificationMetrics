"""Check isolated annotation evidence offline; compare views without relabelling."""
import argparse
import json
from pathlib import Path

from prepare_context_evidence import MODES, RUN
from question_grouping import canonical, digest

AXES = ('opportunity', 'concern_kind')


def validate(packet, annotations, assignment):
    if annotations.get('status') != 'independently_annotated_not_adjudicated':
        raise ValueError('Unexpected annotation authority')
    isolation = annotations.get('isolation_report', {})
    expected_inputs = [assignment['directory'] + '/' + name for name in ('packet.json', 'template.json')]
    if (isolation.get('other_inputs_read') is not False
            or isolation.get('input_files') != expected_inputs
            or assignment.get('context_inheritance') != 'none'):
        raise ValueError('Independent input scope not declared')
    cases = {c['case_id']: c for c in packet['cases']}
    rows = annotations['annotations']
    if (len(cases) != 6 or len(packet['cases']) != 6 or len(rows) != 6
            or {r['case_id'] for r in rows} != set(cases)):
        raise ValueError('Expected exactly six unique case annotations')
    for row in rows:
        case = cases[row['case_id']]
        state = case['state']
        if row['state_sha256'] != case['state_sha256'] or case['state_sha256'] != digest(canonical(state)):
            raise ValueError('Annotation state hash mismatch')
        for axis in AXES:
            if not isinstance(row[axis], str) or row[axis] not in packet['questions'][axis]['criteria']:
                raise ValueError('Unknown rubric label')
            reason = row['rationales'][axis]
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError('Both axes need explicit rationales')
        sources = [state['target']['code'], *[f['code'] for f in state['bounded_context']['fragments']]]
        evidence = row['evidence_quotes']
        if not isinstance(evidence, list) or not evidence:
            raise ValueError('Evidence is required for both axes')
        covered = set()
        for item in evidence:
            quote = item['quote']
            if (item['axis'] not in AXES or not isinstance(quote, str) or not quote.strip()
                    or not any(quote in code for code in sources)):
                raise ValueError('Evidence must quote code from this case and name its axis')
            covered.add(item['axis'])
        if covered != set(AXES):
            raise ValueError('Evidence is required for both axes')
        uncertainties = row['uncertainties']
        if not isinstance(uncertainties, list) or any(not isinstance(u, str) or not u.strip() for u in uncertainties):
            raise ValueError('Expected uncertainty strings')
        if (row['opportunity'] == 'needs_review' or row['concern_kind'] == 'unknown') and not uncertainties:
            raise ValueError('Abstention must explain the missing evidence')
    return {'annotated_cases': len(rows), 'structural_evidence_validation': 'passed',
            'semantic_correctness_verified': False,
            'authority': 'independent_model_annotation_not_human_gold',
            'isolation_boundary': 'fresh_context_and_scoped_assignment_self_report_not_filesystem_enforcement'}


def compare_views(mapping, packets, annotations):
    rows = [r for doc in annotations for r in doc['annotations']]
    cases = [c for packet in packets for c in packet['cases']]
    ids = {c['case_id'] for c in cases}
    mapped = mapping['cases']
    if (len(rows) != 18 or len(cases) != 18 or len(ids) != 18 or len(mapped) != 18
            or {r['case_id'] for r in rows} != ids or {m['case_id'] for m in mapped} != ids):
        raise ValueError('Comparison must cover exactly 18 unique states')
    by_id = {r['case_id']: r for r in rows}
    by_case = {c['case_id']: c for c in cases}
    groups = {}
    for item in mapped:
        row, case = by_id[item['case_id']], by_case[item['case_id']]
        if item['state_sha256'] != row['state_sha256'] or item['state_sha256'] != digest(canonical(case['state'])):
            raise ValueError('Stale mapping or annotation')
        if item['expression_sha256'] != digest(case['state']['target']['code'].encode()):
            raise ValueError('Mapped expression hash mismatch')
        groups.setdefault(item['target_id'], []).append(item)
    if len(groups) != 6:
        raise ValueError('Expected six related target families')
    result = []
    for target_id, items in sorted(groups.items()):
        if (len(items) != 3 or {i['evidence_mode'] for i in items} != set(MODES)
                or len({i['expression_sha256'] for i in items}) != 1
                or len({by_case[i['case_id']]['state']['target']['code'] for i in items}) != 1):
            raise ValueError('Expected the same target in three distinct evidence views')
        views = [{**{k: i[k] for k in ('case_id', 'evidence_mode')},
                  **{a: by_id[i['case_id']][a] for a in AXES}}
                 for mode in MODES for i in items if i['evidence_mode'] == mode]
        result.append({'target_id': target_id, 'views': views,
                       'varying_axes': [a for a in AXES if len({v[a] for v in views}) > 1]})
    return {'target_families': result, 'label_overrides': [], 'jev_luna_requests': 0,
            'interpretation': 'View differences confound evidence and annotator. They are neither same-input disagreement nor a causal context effect.'}


def build(run=RUN):
    def read(name):
        return json.loads((run / name).read_text())
    assignments = read('annotation-assignments.json')['assignments']
    if len(assignments) != 3 or {a['slot'] for a in assignments} != {'01', '02', '03'}:
        raise ValueError('Expected three distinct annotation assignments')
    packets, annotations, validations = [], [], []
    for assignment in assignments:
        slot = assignment['slot']
        for alias, kind in [('packet.json', 'packet'), ('template.json', 'template')]:
            source = f'annotation-{kind}-{slot}.json'
            binding = assignment['files'][alias]
            if binding['source'] != source or binding['sha256'] != digest((run / source).read_bytes()):
                raise ValueError('Assigned input bytes differ from saved packet/template')
        packet = read(f'annotation-packet-{slot}.json')
        annotation = read(f'independent-annotations-{slot}.json')
        prompt = (run / 'annotation-prompt.txt').read_text().rstrip('\n').format(directory=assignment['directory'])
        if (assignment['dispatched_prompt_sha256'] != digest(prompt.encode())
                or assignment['output_sha256'] != digest((run / f'independent-annotations-{slot}.json').read_bytes())):
            raise ValueError('Dispatch prompt or raw output binding mismatch')
        validations.append(validate(packet, annotation, assignment))
        packets.append(packet); annotations.append(annotation)
    comparison = compare_views(read('source-mapping.json'), packets, annotations)
    inputs = ['annotation-assignments.json', 'source-mapping.json', 'annotation-prompt.txt'] + [
        f'{prefix}-{slot}.json' for slot in ('01', '02', '03')
        for prefix in ('annotation-packet', 'annotation-template', 'independent-annotations')]
    return {'status': 'independent_model_annotations_validated_integrator_review_separate',
            'input_file_sha256': {name: digest((run / name).read_bytes()) for name in inputs},
            'producer_sha256': digest(Path(__file__).read_bytes()),
            'validations': validations, 'comparison': comparison,
            'metric_effect': 'none', 'reference_frozen_for_provider_scoring': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    args = parser.parse_args()
    print(json.dumps(build(args.run), indent=2))


if __name__ == '__main__':
    main()
