#!/usr/bin/env python3
"""Prepare real-source context interventions offline; no labels or inference."""
import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import random
import re
import subprocess

from prepare_decision_reference import fragment
from question_grouping import canonical, digest

ROOT = Path(__file__).parent
RUN = ROOT / 'runs/2026-10-13-context-evidence-preparation'
PROFILE = ROOT / 'runs/2026-10-12-expression-reference'
MODES = ('expression_only', 'containing_declaration', 'evidence_bundle')
OUTPUTS = ('case-packet.json', 'source-mapping.json', 'annotation-template.json', 'preparation-receipt.json')


def pinned_path(path):
    p = PurePosixPath(path)
    if p.is_absolute() or '..' in p.parts or str(p) != path or not path.endswith('.py'):
        raise ValueError('Expected a relative Python source path')
    return path


def declaration(tree, symbol):
    if symbol.startswith('import:'):
        name = symbol[7:]
        matches = [n for n in tree.body if
                   isinstance(n, ast.Import) and any(a.name == name for a in n.names)
                   or isinstance(n, ast.ImportFrom) and n.module == name]
    else:
        nodes = tree.body
        matches = []
        for part in symbol.split('.'):
            matches = [n for n in nodes if getattr(n, 'name', None) == part
                       or isinstance(n, (ast.Assign, ast.AnnAssign)) and
                       any(isinstance(t, ast.Name) and t.id == part for t in
                           (n.targets if isinstance(n, ast.Assign) else [n.target]))]
            if len(matches) != 1:
                raise ValueError('Supporting declaration is missing or ambiguous: ' + symbol)
            nodes = getattr(matches[0], 'body', [])
    if len(matches) != 1:
        raise ValueError('Supporting declaration is missing or ambiguous: ' + symbol)
    return matches[0]


def node_span(raw, node):
    lines = raw.splitlines(keepends=True)
    return {'start_byte': sum(map(len, lines[:node.lineno - 1])) + node.col_offset,
            'end_byte': sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset,
            'start_line': node.lineno, 'end_line': node.end_lineno}


def collect(selectors, read_source):
    revision = selectors['revision']
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Expected full Git SHA')
    cases = selectors['targets']
    if len(cases) != 6 or len({c['target_id'] for c in cases}) != 6:
        raise ValueError('Expected six unique natural targets')
    cache = {}

    def source(path):
        path = pinned_path(path)
        if path not in cache:
            cache[path] = read_source(revision, path)
        return cache[path]

    def quote(path, symbol):
        raw = source(path); node = declaration(ast.parse(raw.decode()), symbol)
        start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
        return {'path': path, 'revision': revision, 'file_sha256': digest(raw), 'symbol': symbol,
                **fragment(raw, start, node.end_lineno, 'exact_source_declaration')}

    targets = []
    for selection in cases:
        path, scope = selection['path'], selection['scope']
        raw = source(path); text = raw.decode(); tree = ast.parse(text)
        owner = declaration(tree, scope)
        matches = [n for n in ast.walk(owner) if isinstance(n, ast.expr)
                   and ast.get_source_segment(text, n) == selection['expression']]
        if len(matches) != 1:
            raise ValueError('Target must resolve to exactly one complete expression in scope')
        node = matches[0]; span = node_span(raw, node)
        code = raw[span['start_byte']:span['end_byte']].decode()
        primary = quote(path, scope)
        bundle = [quote(s['path'], s['symbol']) for s in selection['support']]
        if not any(f['path'] == path and f['start_byte'] <= span['start_byte'] < span['end_byte'] <= f['end_byte'] for f in bundle):
            bundle.insert(0, primary)
        if len({(f['path'], f['start_byte'], f['end_byte']) for f in bundle}) != len(bundle):
            raise ValueError('Duplicate supporting fragment')
        targets.append({'target_id': selection['target_id'], 'path': path, 'revision': revision,
                        'file_sha256': digest(raw), 'scope': scope, 'expression': code,
                        'expression_sha256': digest(code.encode()), 'syntax_kind': type(node).__name__,
                        'span': span, 'declaration': primary, 'bundle': bundle})
    return {'schema_version': 1, 'repository': selectors['repository'], 'revision': revision,
            'origin': 'exact_production_source_not_authored_counterfactuals', 'targets': targets}


def verify_sources(sources, read_source=None):
    if len(sources['targets']) != 6 or len({t['target_id'] for t in sources['targets']}) != 6:
        raise ValueError('Expected six unique source targets')
    for target in sources['targets']:
        if target['revision'] != sources['revision'] or not re.fullmatch('[0-9a-f]{40}', target['revision']):
            raise ValueError('Mixed or unpinned source revisions')
        pinned_path(target['path'])
        span = target['span']; code = target['expression'].encode()
        ast.parse(target['expression'], mode='eval')
        if digest(code) != target['expression_sha256'] or span['end_byte'] - span['start_byte'] != len(code):
            raise ValueError('Target hash/span mismatch')
        for f in [target['declaration'], *target['bundle']]:
            pinned_path(f['path'])
            if f['revision'] != target['revision'] or digest(f['code'].encode()) != f['sha256']:
                raise ValueError('Fragment revision/hash mismatch')
            if f['end_byte'] - f['start_byte'] != len(f['code'].encode()):
                raise ValueError('Fragment span mismatch')
            if read_source is not None:
                raw = read_source(f['revision'], f['path'])
                if digest(raw) != f['file_sha256'] or raw[f['start_byte']:f['end_byte']] != f['code'].encode():
                    raise ValueError('Pinned Git source mismatch')
        for group in ([target['declaration']], target['bundle']):
            if not any(f['path'] == target['path'] and f['file_sha256'] == target['file_sha256']
                       and f['start_byte'] <= span['start_byte'] < span['end_byte'] <= f['end_byte']
                       and f['code'].encode()[span['start_byte'] - f['start_byte']:span['end_byte'] - f['start_byte']] == code
                       for f in group):
                raise ValueError('Context does not contain the exact source target')


def build(run=RUN, read_source=None):
    sources = json.loads((run / 'source-evidence.json').read_text())
    selectors = json.loads((run / 'selectors.json').read_text())
    verify_sources(sources, read_source)
    selected = {t['target_id']: (t['path'], t['scope'], t['expression']) for t in selectors['targets']}
    actual = {t['target_id']: (t['path'], t['scope'], t['expression']) for t in sources['targets']}
    if (sources['repository'] != selectors['repository'] or sources['revision'] != selectors['revision']
            or selected != actual or len(selected) != len(selectors['targets'])):
        raise ValueError('Selectors and source evidence disagree')
    if read_source is not None and canonical(collect(selectors, read_source)) != canonical(sources):
        raise ValueError('Source selectors no longer reproduce the evidence')
    profile = json.loads((PROFILE / 'reference-packet.json').read_text())['cases'][0]['state']['architecture_profile']
    rubric = json.loads((PROFILE / 'rubric.json').read_text())['questions']
    drafts = [(target, mode) for target in sources['targets'] for mode in MODES]
    random.Random(2026101301).shuffle(drafts)
    cases, mapping, template = [], [], []
    for index, (target, mode) in enumerate(drafts, 1):
        fragments = ([] if mode == 'expression_only' else [target['declaration']]
                     if mode == 'containing_declaration' else target['bundle'])
        if sum(len(f['code'].encode()) for f in fragments) > 8 * 1024:
            raise ValueError('Context exceeds 8 KiB; never truncate')
        state = {'architecture_profile': profile,
                 'target': {'language': 'Python', 'code': target['expression'],
                            'syntax_kind': target['syntax_kind'], 'scope': 'exact expression only'},
                 'bounded_context': {'fragments': [{'fragment_id': f'context-{n:02d}', 'code': f['code']}
                                                    for n, f in enumerate(fragments, 1)],
                                     'truncated': False,
                                     'limitations': 'Only the supplied exact source fragments are evidence. Unlisted dependencies, callers and runtime bindings are not proved. Less context does not automatically imply unknown; classify each axis from the evidence actually supplied.'}}
        wire = canonical(state)
        if len(wire) > 16 * 1024:
            raise ValueError('State exceeds 16 KiB; never truncate')
        cid = f'context-{index:02d}'; state_hash = digest(wire)
        cases.append({'case_id': cid, 'state_sha256': state_hash, 'state': state})
        mapping.append({'case_id': cid, 'target_id': target['target_id'], 'evidence_mode': mode,
                        'path': target['path'], 'revision': target['revision'], 'scope': target['scope'],
                        'span': target['span'], 'expression_sha256': target['expression_sha256'],
                        'state_sha256': state_hash, 'context_code_bytes': sum(len(f['code'].encode()) for f in fragments),
                        'state_bytes': len(wire)})
        template.append({'case_id': cid, 'state_sha256': state_hash, 'opportunity': None,
                         'concern_kind': None, 'evidence_quotes': [], 'uncertainties': []})
    outputs = {'case-packet.json': {'schema_version': 1, 'study_kind': 'natural_source_context_reference_preparation',
                    'instructions': 'Judge only the exact expression independently under the supplied profile/rubric. Cite supplied evidence for each axis and retain uncertainty. No author labels or provider predictions are supplied. Do not transfer a label from another evidence view.',
                    'questions': rubric, 'cases': cases},
               'source-mapping.json': {'schema_version': 1, 'cases': mapping},
               'annotation-template.json': {'status': 'blank_not_reference', 'annotations': template}}
    outputs['preparation-receipt.json'] = {
        'status': 'prepared_independent_annotation_pending_not_executable', 'new_inference_requests': 0,
        'metric_effect': 'none', 'prior_labels_transferred': False, 'expected_labels_assigned': False,
        'targets': 6, 'evidence_views_per_target': 3, 'annotation_cases': 18,
        'input_sha256': {name: digest((run / name).read_bytes()) for name in ('selectors.json', 'source-evidence.json')},
        'shared_input_sha256': {name: digest((PROFILE / name).read_bytes()) for name in ('reference-packet.json', 'rubric.json')},
        'producer_digests': {name: digest((ROOT / name).read_bytes()) for name in
                             ('prepare_context_evidence.py', 'prepare_decision_reference.py', 'question_grouping.py')},
        'artifact_sha256': {name: digest(canonical(value)) for name, value in outputs.items()}}
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--source-repo', type=Path, help='Verify full files against pinned Git source')
    parser.add_argument('--collect', action='store_true', help='Create source-evidence.json from pinned Git')
    parser.add_argument('--write', action='store_true', help='Create NEW preparation artifacts; default checks saved artifacts')
    args = parser.parse_args()
    if args.collect and args.source_repo is None:
        parser.error('--collect requires --source-repo')
    if args.collect and not args.write:
        parser.error('--collect requires --write')
    if args.write and any((args.run / name).exists() for name in OUTPUTS):
        raise ValueError('Refusing to overwrite preparation artifacts')

    def read_source(revision, path):
        return subprocess.check_output(['git', '-C', str(args.source_repo), 'show', revision + ':' + path])

    if args.collect:
        evidence = collect(json.loads((args.run / 'selectors.json').read_text()), read_source)
        with (args.run / 'source-evidence.json').open('x') as out:
            json.dump(evidence, out, indent=2); out.write('\n')
    artifacts = build(args.run, read_source if args.source_repo else None)
    for name, value in artifacts.items():
        if args.write:
            with (args.run / name).open('x') as out:
                json.dump(value, out, indent=2); out.write('\n')
        elif canonical(json.loads((args.run / name).read_text())) != canonical(value):
            raise ValueError('Saved preparation differs: ' + name)
    print(json.dumps({'targets': 6, 'annotation_cases': 18, 'inference': False,
                      'full_Git_sources_verified': bool(args.source_repo), 'reference_status': 'pending'}))


if __name__ == '__main__':
    main()
