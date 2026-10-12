#!/usr/bin/env python3
"""Revalidate exact construction targets, then route recorded answers offline."""
import argparse
import ast
import json
from pathlib import Path
import subprocess

from coreinfra_retry_run import decode
from matched_expression_plan import ROOT, REFERENCE, inspect_results
from ownership_gate import construction_evidence, route
from prepare_decision_reference import build as rebuild_packet
from question_grouping import canonical, digest
from score_matched_expressions import score


def exact_construction(raw, site, expression_span):
    """Positive only for the whole assigned call, never for a nested predicate."""
    evidence = construction_evidence(raw, site)
    if evidence['status'] == 'direct_specification_construction':
        module = ast.parse(raw.decode())
        target = next(n for n in module.body if n.lineno == site['start_line'] and n.end_lineno == site['end_line'])
        value = target.value
        lines = raw.splitlines(keepends=True)
        start = sum(map(len, lines[:value.lineno - 1])) + value.col_offset
        end = sum(map(len, lines[:value.end_lineno - 1])) + value.end_col_offset
        if (start, end) != (expression_span['start_byte'], expression_span['end_byte']):
            evidence = {**evidence, 'status': 'unknown', 'resolved_constructor': None}
    return evidence


def build(source_repo, run):
    native = inspect_results(run)
    raw_score = score(run)
    saved_packet = decode((REFERENCE / 'reference-packet.json').read_bytes())
    saved_mapping = decode((REFERENCE / 'source-mapping.json').read_bytes())
    cache = {}
    def read_source(revision, path):
        key = (revision, path)
        if key not in cache:
            cache[key] = subprocess.check_output(['git', '-C', str(source_repo), 'show', revision + ':' + path])
        return cache[key]
    packet, mapping = rebuild_packet(decode((REFERENCE / 'context-selectors.json').read_bytes()),
                                    decode((REFERENCE / 'rubric.json').read_bytes()), read_source)
    if packet != saved_packet or mapping != saved_mapping:
        raise ValueError('Historical source/target/context mapping differs from frozen packet')
    corpus = {c['description']: c['metadata']['source']['site'] for c in decode((ROOT / 'corpus/cases.json').read_bytes())}
    proofs = {}
    for case in mapping['cases']:
        site = corpus[case['source_candidate_id']]
        raw = read_source(site['revision'], site['path'])
        evidence = exact_construction(raw, site, case['expression_span'])
        if evidence != case['construction_evidence']:
            raise ValueError('Recomputed exact construction differs from saved evidence')
        proofs[case['case_id']] = {**evidence, 'target_id': case['target_id'],
                                  'state_sha256': case['state_sha256'], 'expression_sha256': case['expression_sha256']}
    reference = {r['case_id']: r for r in decode((REFERENCE / 'independent-annotations.json').read_bytes())['annotations']}
    routed = []
    callback_calls = 0
    for row in native['rows']:
        if row['native_status'] != 'valid':
            continue  # Failures remain unavailable; no new model invocation.
        raw_labels = {axis: answer['choice'] for axis, answer in row['prediction']['answers'].items()}
        def recorded():
            nonlocal callback_calls
            callback_calls += 1
            return raw_labels['opportunity']
        decision = route(proofs[row['case_id']], recorded)
        routed.append({'request_id': row['request_id'], 'case_id': row['case_id'], 'provider': row['provider'],
                       'repeat': row['repeat'], 'origin': decision['origin'], 'raw_labels': raw_labels,
                       'effective_labels': {**raw_labels, 'opportunity': decision['opportunity']}})
    summaries = []
    for provider in raw_score['providers']:
        repeats = []
        for repeat in (1, 2):
            rows = [r for r in routed if r['provider'] == provider['provider'] and r['repeat'] == repeat]
            eligible = [cid for cid, r in reference.items() if r['opportunity'] == 'eligible']
            false_positives = [r['case_id'] for r in rows if reference[r['case_id']]['opportunity'] == 'excluded'
                               and r['effective_labels']['opportunity'] == 'eligible']
            matched = {axis: sum(r['effective_labels'][axis] == reference[r['case_id']][axis] for r in rows)
                       for axis in ('opportunity', 'concern_kind')}
            recall = sum(r['case_id'] in eligible and r['effective_labels']['opportunity'] == 'eligible' for r in rows)
            repeats.append({'repeat': repeat, 'native_valid': len(rows), 'planned': 8, 'matched': matched,
                            'eligible_recall': {'recovered': recall, 'planned': len(eligible)},
                            'false_positive_ids': false_positives,
                            'repeat_criteria_passed': len(rows) == 8 and min(matched.values()) >= 7
                                                      and not false_positives and recall == len(eligible)})
        summaries.append({'provider': provider['provider'], 'repeats': repeats})
    return {'schema_version': 1, 'study_kind': 'exact_expression_construction_recorded_replay',
            'new_inference_requests': 0, 'metric_effect': 'none', 'planned_requests': 32,
            'native_valid': native['native_valid'], 'evidence': proofs, 'routes': routed,
            'recorded_semantic_callback_calls': callback_calls, 'summaries': summaries,
            'raw_provider_score': raw_score['providers'],
            'input_sha256': {'packet': digest(canonical(packet)), 'mapping': digest(canonical(mapping)),
                             'responses': digest((run / 'responses.jsonl').read_bytes()),
                             'reference': digest((REFERENCE / 'independent-annotations.json').read_bytes()),
                             'manifest': digest((run / 'manifest.json').read_bytes())},
            'implementation_sha256': {name: digest((ROOT / name).read_bytes()) for name in
                ('replay_expression_construction.py', 'ownership_gate.py', 'prepare_decision_reference.py',
                 'matched_expression_plan.py', 'score_matched_expressions.py')},
            'limits': 'Offline composition over previously paid answers, not a fresh end-to-end live study. Positive proof assumes ordinary static Python bindings and trusted specification_core constructor semantics; not runtime identity/liveness. Exact whole construction only. Unknown is not unowned. Concern-kind and all raw probabilities/confidence remain unchanged. Model reference, eight development cases, no human gold or S/U changes.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-repo', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source_repo, args.run)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2); out.write('\n')
    print(json.dumps({'positive_ids': [cid for cid, e in result['evidence'].items() if e['status'] != 'unknown'],
                      'new_inference_requests': 0, 'summaries': result['summaries']}, indent=2))


if __name__ == '__main__':
    main()
