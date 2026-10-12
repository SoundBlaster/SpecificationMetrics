#!/usr/bin/env python3
"""Prepare contrastive cases and a logical schedule offline; no live runner."""
import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import random
import re
import subprocess

from question_grouping import canonical, digest

ROOT = Path(__file__).parent
RUN = ROOT / 'runs/2026-10-13-contrastive-preparation'
REFERENCE = ROOT / 'runs/2026-10-12-expression-reference'
PROVIDERS = ('jev-coreinfra', 'luna-decision-coreinfra')
OUTPUTS = ('case-packet.json', 'source-mapping.json', 'author-proposals.json',
           'annotation-template.json', 'logical-schedule.json', 'preparation-receipt.json')


def expression_span(code, expression):
    raw = code.encode('utf-8')
    matches = [n for n in ast.walk(ast.parse(code))
               if isinstance(n, ast.expr) and ast.get_source_segment(code, n) == expression]
    if len(matches) != 1:
        raise ValueError('Target must resolve to exactly one complete AST expression')
    node = matches[0]
    lines = raw.splitlines(keepends=True)
    start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
    end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
    if raw[start:end] != expression.encode('utf-8'):
        raise ValueError('Target byte mismatch')
    return {'start_byte': start, 'end_byte': end,
            'start_line': node.lineno, 'end_line': node.end_lineno}


def verify_source_evidence(sources, read_source=None):
    if {s['pair_id'] for s in sources} != {f'pair-{n:02d}' for n in range(1, 5)} or len(sources) != 4:
        raise ValueError('Expected exactly four historical ancestors')
    for source in sources:
        path = PurePosixPath(source['path'])
        if not re.fullmatch('[0-9a-f]{40}', source['revision']) or path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid pinned Git source')
        quote = source['quote'].encode('utf-8')
        span = source['span']
        if digest(quote) != source['quote_sha256'] or span['end_byte'] - span['start_byte'] != len(quote):
            raise ValueError('Historical quote digest/span mismatch')
        selected = source['selected_source_expression']
        if selected is not None and selected not in source['quote']:
            raise ValueError('Historical expression absent from quote')
        if read_source is not None:
            raw = read_source(source['revision'], source['path'])
            if digest(raw) != source['file_sha256'] or raw[span['start_byte']:span['end_byte']] != quote:
                raise ValueError('Pinned historical source changed')


def build(run=RUN, read_source=None):
    scenarios = json.loads((run / 'scenarios.json').read_text())
    plan = json.loads((run / 'study-plan.json').read_text())
    if (plan['corpus']['total_cases'], plan['design']['repeats'],
        plan['design']['planned_logical_requests'], plan['design']['max_attempts_per_request'],
        plan['design']['max_network_attempts']) != (12, 2, 48, 3, 144):
        raise ValueError('Plan differs from bounded preparation design')
    if tuple(p['id'] for p in plan['providers']) != PROVIDERS:
        raise ValueError('Plan provider inventory differs')
    sources = json.loads((run / 'source-evidence.json').read_text())['sources']
    verify_source_evidence(sources, read_source)
    pairs = scenarios['pairs']
    if len(pairs) != 4 or {p['pair_id'] for p in pairs} != {s['pair_id'] for s in sources}:
        raise ValueError('Expected exactly four contrastive pairs')
    profile = json.loads((REFERENCE / 'reference-packet.json').read_text())['cases'][0]['state']['architecture_profile']
    rubric = json.loads((REFERENCE / 'rubric.json').read_text())
    drafts = []
    for pair in pairs:
        for role in ('mechanics', 'policy', 'withheld'):
            if role == 'withheld':
                context = {'fragments': [], 'truncated': False,
                           'limitations': 'Input meanings, containing implementation, scenario contract and effects intentionally withheld. Do not infer them.'}
                span = None
            else:
                scenario = pair[role]
                span = expression_span(scenario['code'], pair['expression'])
                context = {'scenario_contract': scenario['contract'],
                           'fragments': [{'fragment_id': 'context-01', 'code': scenario['code']}],
                           'truncated': False,
                           'limitations': 'Authored self-contained diagnostic scenario derived from a historical expression shape. The supplied contract defines this scenario, not canonical SpecGraph intent. Only the exact expression is a classification target.'}
            state = {'architecture_profile': profile,
                     'target': {'language': 'Python', 'code': pair['expression'],
                                'syntax_kind': 'boolean_operator', 'scope': 'exact expression only'},
                     'bounded_context': context}
            if len(canonical(state)) > 16 * 1024:
                raise ValueError('State budget exceeded; never truncate')
            drafts.append((pair, role, span, state))
    random.Random(20261013).shuffle(drafts)
    packet = {'schema_version': 1, 'study_kind': 'contrastive_scenario_annotation_packet',
              'instructions': 'Judge each exact expression independently under the supplied architecture profile and rubric. The supplied scenario contract and code are evidence. Do not infer omitted inputs or effects. Cite exact supplied text for both axes. No author proposals or provider predictions are supplied.',
              'questions': rubric['questions'], 'cases': []}
    mapping, proposals, template = [], [], []
    for index, (pair, role, span, state) in enumerate(drafts, 1):
        cid = f'case-{index:02d}'
        state_hash = digest(canonical(state))
        packet['cases'].append({'case_id': cid, 'state': state, 'state_sha256': state_hash})
        mapping.append({'case_id': cid, 'pair_id': pair['pair_id'], 'stratum': role,
                        'state_sha256': state_hash, 'target_sha256': digest(pair['expression'].encode()),
                        'authored_span': span, 'derivation': pair['derivation'],
                        'historical_ancestor': next(s for s in sources if s['pair_id'] == pair['pair_id'])})
        opportunity, concern = {'policy': ('eligible', 'policy'), 'mechanics': ('excluded', 'mechanics'),
                                'withheld': ('needs_review', 'unknown')}[role]
        proposals.append({'case_id': cid, 'state_sha256': state_hash,
                          'opportunity': opportunity, 'concern_kind': concern,
                          'basis': 'Scenario author hypothesis; not an independent reference or human gold.'})
        template.append({'case_id': cid, 'state_sha256': state_hash,
                         'opportunity': None, 'concern_kind': None, 'evidence_quotes': []})
    schedule = []
    for repeat in (1, 2):
        ordered = list(packet['cases'])
        random.Random(20261013 + repeat).shuffle(ordered)
        for case in ordered:
            case_number = int(case['case_id'].split('-')[1])
            providers = PROVIDERS if (case_number + repeat) % 2 else tuple(reversed(PROVIDERS))
            for provider in providers:
                schedule.append({'request_id': f'r{repeat}-{case["case_id"]}-{provider}',
                                 'case_id': case['case_id'], 'repeat': repeat, 'provider': provider,
                                 'state_sha256': case['state_sha256']})
    artifacts = {'case-packet.json': packet,
                 'source-mapping.json': {'schema_version': 1, 'cases': mapping,
                                         'origin': 'authored_counterfactuals_not_production_source_targets'},
                 'author-proposals.json': {'status': 'nonblind_author_hypotheses_not_reference',
                                          'independent': False, 'prior_labels_transferred': False,
                                          'annotations': proposals},
                 'annotation-template.json': {'status': 'blank_not_reference', 'annotations': template},
                 'logical-schedule.json': {'status': 'logical_order_only_not_executable_native_wires',
                                           'planned_cases': 12, 'repeats': 2, 'planned_logical_requests': 48,
                                           'max_attempts_per_request': 3, 'max_network_attempts': 144,
                                           'requests': schedule}}
    artifacts['preparation-receipt.json'] = {
        'status': 'prepared_reference_pending_native_wires_pending', 'new_inference_requests': 0,
        'production_metric_effect': 'none', 'reference_status': 'awaiting_fresh_independent_annotation',
        'input_sha256': {name: digest((run / name).read_bytes()) for name in
                         ('scenarios.json', 'source-evidence.json', 'study-plan.json')},
        'shared_input_sha256': {'rubric': digest((REFERENCE / 'rubric.json').read_bytes()),
                               'architecture_profile': digest(canonical(profile))},
        'implementation_sha256': {name: digest((ROOT / name).read_bytes()) for name in
                                  ('prepare_contrastive_pairs.py', 'question_grouping.py')},
        'artifact_sha256': {name: digest(canonical(value)) for name, value in artifacts.items()},
        'inventory': [{'case_id': c['case_id'], 'state_bytes': len(canonical(c['state']))}
                      for c in packet['cases']]}
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--source-repo', type=Path, help='Optionally verify full pinned historical Git files')
    parser.add_argument('--write', action='store_true', help='Create new artifacts; default is offline comparison')
    args = parser.parse_args()
    def read_source(revision, path):
        return subprocess.check_output(['git', '-C', str(args.source_repo), 'show', revision + ':' + path])
    artifacts = build(args.run, read_source if args.source_repo else None)
    if args.write and any((args.run / name).exists() for name in OUTPUTS):
        raise ValueError('Refusing to overwrite preparation artifacts')
    for name, value in artifacts.items():
        if args.write:
            with (args.run / name).open('x') as out:
                json.dump(value, out, indent=2); out.write('\n')
        elif json.loads((args.run / name).read_text()) != value:
            raise ValueError('Preparation artifact differs: ' + name)
    print(json.dumps({'cases': 12, 'planned_logical_requests': 48, 'new_inference_requests': 0,
                      'full_historical_sources_verified': bool(args.source_repo),
                      'status': 'prepared_reference_pending_native_wires_pending'}))


if __name__ == '__main__':
    main()
