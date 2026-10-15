"""Source-bound helper-context ablation and bounded English/Russian retrieval."""
import argparse
import ast
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import embeddinggemma_pilot_v1 as prior

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'runs/2026-10-15-embeddinggemma-retrieval-v1-attempt-3'
PREP = ROOT / 'runs/2026-10-15-retrieval-helper-preparation-v1'
PROTOCOL = ROOT / 'retrieval-helper-pilot-v1.md'
REVISION = '51c8d93cc385569864b3cd7f5040d4b3e0820a1b'
TARGETS = (
    ('tools/evidence_claim_gate.py', 'canonical_claim_errors',
     'Validate evidence declarations: unique identities, allowed fields and kinds; runtime decision mapping must match the claim and include a policy digest.',
     'Проверить декларации свидетельств: уникальные идентификаторы, допустимые поля и виды; привязка решения времени исполнения должна соответствовать заявлению и содержать хеш политики.'),
    ('tools/product_workspace_next_moves_support.py', 'safe_workspace_path',
     'Reject workspace paths that are absolute, use a home shortcut or Windows separators, contain a colon, or traverse to a parent directory.',
     'Отклонить пути рабочего пространства, которые абсолютны, начинаются с домашнего каталога, содержат разделители Windows, двоеточие или переход к родительской папке.'),
    ('tools/intent_atoms.py', '_snapshot_compatibility',
     'Build a comparison key for intent snapshots using profile identity and version, profile digest, analyzer version and digest, and specification root.',
     'Составить ключ совместимости снимков намерений из идентичности, версии и хеша профиля, версии и хеша анализатора и корня спецификаций.'),
    ('tools/static_artifact_incremental_stage.py', 'stage_changed_files',
     'Stage only changed publication files, checking actual remote contents even when manifest hashes agree; detect removals and reject staging collisions.',
     'Подготовить к публикации только изменённые файлы, проверяя содержимое удалённых файлов даже при совпадении хешей манифеста; выявить удаления и запретить коллизии в staging.'),
    ('tools/subject_source_write.py', 'parse_write_authorization',
     'Deserialize authorization to write subjects into a typed object with the request digest, decision reference, reviewer authority, timestamp and transition references.',
     'Преобразовать разрешение на запись субъектов в типизированный объект с хешем запроса, ссылкой на решение, полномочиями проверяющего, временем и ссылками на переходы.'),
    ('tools/validate_materialization_packet.py', '_check_inputs',
     'Verify the materialization input inventory and file hashes, including all six subjects, workspace declaration, and the pinned contract snapshot commit.',
     'Проверить состав и хеши входов материализации: все шесть субъектов, декларацию рабочего пространства и закреплённый коммит снимка контрактов.'),
    ('tools/build_static_artifact_bundle.py', 'is_publishable_candidate_approval_decision',
     'Allow publication of an approval decision only with a valid active candidate, matching contract, disabled canonical writes, and exact source artifact references and hashes.',
     'Разрешить публикацию решения об одобрении только при действующем кандидате, правильном контракте, запрете канонических записей и точном совпадении ссылок и хешей исходных артефактов.'),
    ('tools/supervisor_structural_limits.py', 'resolve_structural_limits',
     'Resolve structural thresholds from defaults and project overrides, validate both schemas and values, and retain provenance of configuration and policy.',
     'Получить структурные пороги из значений по умолчанию и настроек проекта, проверить схемы и значения и сохранить происхождение конфигурации и политики.'),
)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def span(raw, node):
    start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
    code = ''.join(raw.splitlines(keepends=True)[start - 1:node.end_lineno])
    return dict(start_line=start, end_line=node.end_lineno, code=code,
                excerpt_sha256='sha256:' + prior.sha(code.encode()))


def helpers(raw, excerpt, start_line=1, end_line=None):
    """One local hop for syntactic PredicateSpec(name); never execute source."""
    if 'PredicateSpec' not in excerpt:
        return []
    tree = ast.parse(raw)
    requested = set()

    class Calls(ast.NodeVisitor):
        def visit_Lambda(self, node):
            pass  # Do not confuse a lambda's local binding with a module function.

        def visit_Call(self, node):
            if (isinstance(node.func, ast.Name) and node.func.id == 'PredicateSpec' and node.args
                    and isinstance(node.args[0], ast.Name) and node.lineno >= start_line
                    and node.end_lineno <= (end_line or len(raw.splitlines()))):
                requested.add(node.args[0].id)
            self.generic_visit(node)

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            Calls().visit(node)
    result = []
    for name in sorted(requested):
        definitions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
        # Reject module-level rebinding, including conditional definitions/imports.
        bindings = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == name:
                    bindings.append(node)
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store) and child.id == name:
                    bindings.append(child)
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child.name == name:
                    bindings.append(child)
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    bindings.extend(a for a in child.names if (a.asname or a.name.split('.')[0]) == name)
        if len(definitions) == 1 and len(bindings) == 1:
            item = span(raw, definitions[0])
            if item['code'].strip() not in excerpt:
                result.append(dict(symbol=name, **item))
    return result


def document(identifier, path, symbol, revision, raw, node):
    site = dict(path=path, symbol=symbol, revision=revision,
                file_sha256='sha256:' + prior.sha(raw.encode()), **span(raw, node))
    return dict(id=identifier, source=site,
                text='title: ' + path + '::' + symbol + ' | text: ' + site['code'])


def expand(doc, raw):
    prior.require('sha256:' + prior.sha(raw.encode()) == doc['source']['file_sha256'], 'source file hash differs')
    source = doc['source']
    selected = ''.join(raw.splitlines(keepends=True)[source['start_line'] - 1:source['end_line']])
    prior.require(selected == source['code'], 'source span differs')
    extra = helpers(raw, source['code'], source['start_line'], source['end_line'])
    return dict(doc, helpers=extra, text=doc['text'] + ''.join(
        '\n\n# Local predicate: ' + h['symbol'] + '\n' + h['code'] for h in extra))


def packet(repo):
    old = prior.verify_preparation(prior.PREPARATION)
    sources = {}

    def source(rev, path):
        key = (rev, path)
        if key not in sources:
            sources[key] = git(repo, 'show', rev + ':' + path).decode()
        return sources[key]

    historical = [expand(d, source(d['source']['revision'], d['source']['path'])) for d in old['documents']]
    candidates = []
    files = git(repo, 'ls-tree', '-r', '--name-only', REVISION, 'tools').decode().splitlines()
    file_count = 0
    for path in files:
        if not path.endswith('.py'):
            continue
        file_count += 1
        raw = source(REVISION, path)
        for node in ast.parse(raw).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = node.name
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if not any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                           and c.func.id == 'PredicateSpec' for c in ast.walk(node)):
                    continue
                symbol = node.targets[0].id
            else:
                continue
            if not 4 <= node.end_lineno - node.lineno + 1 <= 100:
                continue
            identifier = path + '::' + symbol
            candidates.append(document(identifier, path, symbol, REVISION, raw, node))
    prior.require(len({d['id'] for d in candidates}) == len(candidates), 'ambiguous source declaration IDs')
    chosen = sorted(candidates, key=lambda d: prior.sha(d['id'].encode()))[:512]
    index = {d['id']: d for d in chosen}
    pool = {d['id']: d for d in candidates}
    previous = {(d['source']['path'], d['source']['symbol']) for d in old['documents']}
    previous.update((q['source']['path'], q['source']['symbol']) for q in old['queries'])
    queries = []
    for i, (path, name, en, ru) in enumerate(TARGETS, 1):
        identifier = path + '::' + name
        prior.require((path, name) not in previous, 'new query target appeared in previous retrieval pilot')
        index[identifier] = pool[identifier]
        for language, text in (('en', en), ('ru', ru)):
            queries.append(dict(id='new-%02d-' % i + language, mode=language, text=text,
                                relevant_document=identifier))
    current = [expand(index[key], source(REVISION, index[key]['source']['path'])) for key in sorted(index)]
    return dict(contract='specmetrics.retrieval-helper-ablation/v1', model=prior.MODEL,
                model_revision=prior.REVISION, current_source_revision=REVISION,
                source_scope=dict(root='tools', python_files=file_count, eligible_declarations=len(candidates),
                                  selector='top_level_functions_or_PredicateSpec_assignments_4_to_100_lines',
                                  sampling='first_512_by_sha256_path_symbol_plus_eight_query_targets', exhaustive=False),
                historical=dict(documents=historical, queries=old['queries']),
                current=dict(documents=current, queries=queries),
                helper_scope='module_assignment_PredicateSpec_first_Name_argument_unique_same_module_definition_one_hop',
                dimensions=[768, 256], rrf_constant=60, authority='ranked_candidates_only',
                reference='authored_development_source_locator_not_exhaustive_semantic_gold',
                predecessor_packet_sha256=prior.sha(prior.encoded(old)))


def rankings(data, docs, queries):
    import numpy as np
    from rank_bm25 import BM25Okapi
    prior.require(docs.shape == (len(data['documents']), 768) and queries.shape == (len(data['queries']), 768), 'vector shape differs')
    prior.require(np.isfinite(docs).all() and np.isfinite(queries).all(), 'non-finite vectors')
    ids = [d['id'] for d in data['documents']]
    lexical = BM25Okapi([prior.tokens(d['text']) for d in data['documents']])
    orders = {'bm25': [prior.ranked(lexical.get_scores(prior.tokens(q['text'])), ids) for q in data['queries']]}
    for dimension in (768, 256):
        d, q = docs[:, :dimension].astype(np.float64), queries[:, :dimension].astype(np.float64)
        dn, qn = np.linalg.norm(d, axis=1, keepdims=True), np.linalg.norm(q, axis=1, keepdims=True)
        prior.require((dn > 0).all() and (qn > 0).all(), 'zero norm')
        scores = np.einsum('qd,nd->qn', q / qn, d / dn, optimize=False)
        dense = [prior.ranked(s, ids) for s in scores]
        orders['dense_' + str(dimension)] = dense
        combined = []
        for left, right in zip(orders['bm25'], dense):
            fused = [0.0] * len(ids)
            for order in (left, right):
                for rank, pos in enumerate(order, 1):
                    fused[pos] += 1 / (60 + rank)
            combined.append(prior.ranked(fused, ids))
        orders['hybrid_' + str(dimension)] = combined
    result = {}
    for method, values in orders.items():
        rows = [dict(query_id=q['id'], mode=q['mode'], rank=order.index(ids.index(q['relevant_document'])) + 1,
                     top_10=[ids[i] for i in order[:10]]) for q, order in zip(data['queries'], values)]
        summary = {}
        for mode in sorted({q['mode'] for q in data['queries']}):
            group = [r for r in rows if r['mode'] == mode]
            summary[mode] = dict(n=len(group), mrr=sum(1 / r['rank'] for r in group) / len(group),
                                **{'hits@' + str(k): sum(r['rank'] <= k for r in group) for k in (1, 5, 10)})
        result[method] = dict(rows=rows, summary=summary)
    return result


def views(data):
    for scope in ('historical', 'current'):
        for arm in ('declaration', 'with_helpers'):
            docs = data[scope]['documents']
            if arm == 'declaration':
                docs = [dict(d, text='title: ' + d['source']['path'] + '::' + d['source']['symbol'] + ' | text: ' + d['source']['code']) for d in docs]
            yield scope + '_' + arm, dict(documents=docs, queries=data[scope]['queries'])


def layout(data):
    texts, lookup, mapping = [], {}, {}
    for name, view in views(data):
        positions = []
        for doc in view['documents']:
            if doc['text'] not in lookup:
                lookup[doc['text']] = len(texts)
                texts.append(doc['text'])
            positions.append(lookup[doc['text']])
        mapping[name] = positions
    return texts, mapping


def score(data, documents, queries):
    texts, mapping = layout(data)
    prior.require(documents.shape == (len(texts), 768) and queries.shape == (46, 768), 'pool shape differs')
    return {name: rankings(view, documents[mapping[name]], queries[:30] if name.startswith('historical') else queries[30:])
            for name, view in views(data)}


def execute(preparation, output, model_path, repo):
    import numpy as np
    data = json.loads((preparation / 'packet.json').read_text())
    prior.require(data == packet(repo), 'source reconstruction differs before inference')
    prior.verify_run(BASE)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'packet.json').write_bytes(prior.encoded(data))
    producer = prior.sha(Path(__file__).read_bytes())
    protocol_hash = prior.sha(PROTOCOL.read_bytes())
    started = time.perf_counter()
    try:
        # Use the existing verified snapshot, offline: no new internal-disk HF cache.
        import torch
        from sentence_transformers import SentenceTransformer
        prior.require(model_path.name == prior.REVISION and torch.backends.mps.is_available(), 'pinned snapshot or MPS unavailable')
        model = SentenceTransformer(str(model_path), device='mps', local_files_only=True, trust_remote_code=False,
                                    config_kwargs={'vision_config': None, 'audio_config': None},
                                    model_kwargs={'torch_dtype': torch.float32})
        config = model[0].auto_model.config
        prior.require(config.vision_config is None and config.audio_config is None, 'non-text encoders active')
        prior.require(model.get_embedding_dimension() == 768, 'model dimension differs')
        texts, mapping = layout(data)
        old = json.loads((BASE / 'packet.json').read_text())
        with np.load(BASE / 'embeddings.npz', allow_pickle=False) as saved:
            reused = {d['text']: saved['documents'][i] for i, d in enumerate(old['documents'])}
            old_queries = saved['queries'].copy()
        missing = [t for t in texts if t not in reused]
        query_text = [q['text'] for q in data['current']['queries']]
        lengths = [len(model.tokenizer.encode(t)) for t in missing + [model.prompts['CodeRetrieval'] + t for t in query_text]]
        prior.require(max(lengths) <= model.max_seq_length, 'input exceeds context; no silent truncation')
        model.encode('Find a reusable rule', prompt_name='CodeRetrieval', normalize_embeddings=True)
        print('Encoding %d new document representations; reusing %d.' % (len(missing), len(texts) - len(missing)), flush=True)
        tick = time.perf_counter()
        new = model.encode(missing, prompt='', batch_size=4, normalize_embeddings=True, show_progress_bar=False)
        index_seconds = time.perf_counter() - tick
        reused.update(zip(missing, new))
        documents = np.stack([reused[t] for t in texts])
        new_queries, latency = [], []
        for text in query_text:
            tick = time.perf_counter()
            new_queries.append(model.encode(text, prompt_name='CodeRetrieval', normalize_embeddings=True, show_progress_bar=False))
            latency.append(time.perf_counter() - tick)
        queries = np.concatenate([old_queries, np.stack(new_queries)])
        np.savez_compressed(output / 'embeddings.npz', documents=documents, queries=queries)
        result = score(data, documents, queries)
        prior.require(producer == prior.sha(Path(__file__).read_bytes()), 'producer changed')
        prior.require(protocol_hash == prior.sha(PROTOCOL.read_bytes()), 'protocol changed')
        (output / 'scores.json').write_bytes(prior.encoded(result))
        receipt = dict(status='complete', producer_sha256=producer, packet_sha256=prior.sha(prior.encoded(data)),
                       protocol_sha256=protocol_hash,
                       predecessor_vectors_sha256=prior.sha((BASE / 'embeddings.npz').read_bytes()),
                       vectors_sha256=prior.sha((output / 'embeddings.npz').read_bytes()),
                       model=prior.MODEL, model_revision=prior.REVISION, device='mps', dtype='float32',
                       local_inference_authorization='User: Ок, давай — helper expansion and larger Russian-query pilot',
                       hosted_inference_requests=0, index_seconds=index_seconds, query_seconds=latency,
                       new_document_encodes=len(missing), reused_documents=len(texts) - len(missing),
                       new_query_encodes=16, reused_queries=30, maximum_input_tokens=max(lengths),
                       source_reconstruction_verified=True,
                       total_seconds=time.perf_counter() - started,
                       process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       mps_driver_bytes_at_end=torch.mps.driver_allocated_memory(),
                       python_bytecode_on_external_volume=os.environ.get('PYTHONPYCACHEPREFIX', '').startswith('/Volumes/TB5/'),
                       packages={n: importlib.metadata.version(n) for n in ('sentence-transformers', 'transformers', 'torch', 'numpy', 'rank-bm25')})
        (output / 'receipt.json').write_bytes(prior.encoded(receipt))
        print(json.dumps({k: {m: v['summary'] for m, v in arm.items()} for k, arm in result.items()}, indent=2))
    except Exception as error:
        (output / 'failure.json').write_bytes(prior.encoded(dict(error_type=type(error).__name__, message=str(error), producer_sha256=producer)))
        raise


def verify(directory):
    import numpy as np
    data = json.loads((directory / 'packet.json').read_text())
    prior.require(data == json.loads((PREP / 'packet.json').read_text()), 'preparation differs')
    receipt = json.loads((directory / 'receipt.json').read_text())
    prior.require(receipt['status'] == 'complete' and not (directory / 'failure.json').exists(), 'run incomplete')
    for name, value in [('producer_sha256', Path(__file__).read_bytes()), ('packet_sha256', prior.encoded(data)),
                        ('protocol_sha256', PROTOCOL.read_bytes()),
                        ('vectors_sha256', (directory / 'embeddings.npz').read_bytes()),
                        ('predecessor_vectors_sha256', (BASE / 'embeddings.npz').read_bytes())]:
        prior.require(receipt[name] == prior.sha(value), name + ' differs')
    prior.require(receipt['model_revision'] == prior.REVISION and receipt['hosted_inference_requests'] == 0, 'run identity differs')
    with np.load(directory / 'embeddings.npz', allow_pickle=False) as saved:
        result = score(data, saved['documents'], saved['queries'])
    prior.require(result == json.loads((directory / 'scores.json').read_text()), 'replay differs')
    print('Four retrieval views replay exactly; no inference.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', action='store_true')
    action.add_argument('--check-source', action='store_true')
    action.add_argument('--execute', type=Path)
    action.add_argument('--verify', type=Path)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--model-path', type=Path)
    args = parser.parse_args()
    if args.prepare or args.check_source:
        if args.repo is None:
            parser.error('--repo required')
        data = packet(args.repo)
        if args.prepare:
            PREP.mkdir(parents=True, exist_ok=False)
            (PREP / 'packet.json').write_bytes(prior.encoded(data))
        else:
            prior.require((PREP / 'packet.json').read_bytes() == prior.encoded(data), 'source reconstruction differs')
        print(json.dumps(dict(scope=data['source_scope'], current_documents=len(data['current']['documents']),
                              changed={s: [d['id'] for d in data[s]['documents'] if d['helpers']] for s in ('historical', 'current')}), indent=2))
    elif args.execute:
        if args.model_path is None or args.repo is None:
            parser.error('--model-path and --repo required')
        execute(PREP, args.execute, args.model_path, args.repo)
    else:
        verify(args.verify)


if __name__ == '__main__':
    main()
