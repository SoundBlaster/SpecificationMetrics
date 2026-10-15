"""Reconstruct the declared Python retrieval scope from one immutable Git tree."""
import ast
import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path

import retrieval_helper_pilot_v1 as extraction


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def snapshot(repo, repository_id, revision='HEAD', includes=('tools/*.py',), excludes=()):
    if not repository_id.strip() or not includes:
        raise ValueError('repository identity and explicit include scope are required')
    commit = git(repo, 'rev-parse', '--verify', '--end-of-options', revision + '^{commit}').decode().strip()
    tree = git(repo, 'rev-parse', commit + '^{tree}').decode().strip()
    documents, files, skipped = [], [], 0
    # NUL framing preserves spaces/newlines; symlinks/submodules are never followed.
    for entry in git(repo, 'ls-tree', '-rz', commit).split(b'\0'):
        if not entry:
            continue
        header, raw_path = entry.split(b'\t', 1)
        mode, kind, blob = header.decode().split()
        path = raw_path.decode('utf-8')
        if not path.endswith('.py') or not any(fnmatch.fnmatchcase(path, p) for p in includes):
            continue
        if any(fnmatch.fnmatchcase(path, p) for p in excludes):
            continue
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('unsupported source entry: ' + path)
        raw = git(repo, 'cat-file', 'blob', blob).decode('utf-8')
        nodes = ast.parse(raw, filename=path).body
        files.append(dict(path=path, blob=blob, sha256=digest(raw)))
        for node in nodes:
            symbol = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = node.name
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                       and c.func.id == 'PredicateSpec' for c in ast.walk(node)):
                    symbol = node.targets[0].id
            if symbol is None:
                continue
            if not 4 <= node.end_lineno - node.lineno + 1 <= 100:
                skipped += 1
                continue
            doc = extraction.expand(extraction.document(path + '::' + symbol, path, symbol, commit, raw, node), raw)
            documents.append(doc)
    if len({d['id'] for d in documents}) != len(documents):
        raise ValueError('ambiguous declaration IDs; refuse silent overwriting')
    return dict(contract='specmetrics.retrieval-source-snapshot/v1', repository_id=repository_id,
                revision=commit, tree=tree, includes=sorted(set(includes)), excludes=sorted(set(excludes)),
                extraction='top_level_functions_or_PredicateSpec_assignments_4_to_100_lines_one_local_helper_hop',
                extraction_sha256=digest(Path(extraction.__file__).read_text()),
                collector_sha256=digest(Path(__file__).read_text()),
                files=files, documents=sorted(documents, key=lambda d: d['id']),
                length_filtered_declarations=skipped, semantic_coverage='partial',
                authority='ranked_candidates_only', working_tree='not_indexed')
