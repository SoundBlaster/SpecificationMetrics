"""Bounded local historical-counterpart retrieval; no ownership or semantic gold claims."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PREPARATION = ROOT / 'runs/2026-10-15-embeddinggemma-preparation-v1'
MODEL = 'google/embeddinggemma-2'
REVISION = '914f7f89142e33e77833254d9c9b90c3cef7303b'
INTENTS = (
    'Determine whether a candidate can be approved after repair, is blocked, has not reached approval, or is unavailable.',
    'Determine the state of a candidate approval intent from its artifact and active requests.',
    'Determine whether an approval decision has materialized, is a dry run, failed, blocked, or is missing.',
    'Determine platform promotion lifecycle state from promotion and execution artifacts.',
    'Determine whether promotion has been requested, is blocked by errors, or has not been reached.',
    'Determine promotion execution state, respecting dry runs, failures, blocked status and created commits or reviews.',
    'Determine code review lifecycle state; a probe-only merged response must remain unknown.',
    'Determine publication state of the read model from the available lifecycle artifacts.',
    'Decide whether an original pre-SIB report is ready, blocked, or permitted because repair preview was used.',
    'Identify requirements whose acceptance criterion references are absent or do not resolve, so a placeholder can be proposed.',
    'Downgrade strong claims with low reliability and no evidence into hypotheses.',
    'Dispatch preview edits that append edges, add acceptance criteria, or replace claim types without canonical mutation.',
    'Choose candidate quality review state from resolved and unresolved ontology and candidate gaps.',
    'Allow a clean pre-SIB handoff to pass through when repair has no findings, actions or required context.',
    'Count ontology decisions with the accepted decision state.',
)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def packet():
    paths = [ROOT / 'corpus/cases.json', ROOT / 'corpus/selection.json']
    raw = {p.name: p.read_bytes() for p in paths}
    cases = json.loads(raw['cases.json'])
    selected = {c['id']: c for c in json.loads(raw['selection.json'])['cases']}
    index = {c['description']: c for c in cases}
    require(len(index) == len(cases) == 60, 'expected distinct 60-site historical corpus')
    documents = []
    for item in cases:
        if item['metadata']['role'] == 'historical_before':
            continue
        site = item['metadata']['source']['site']
        documents.append(dict(id=item['description'], source=site,
                              text='title: ' + site['path'] + '::' + site['symbol'] + ' | text: ' + site['code']))
    queries = []
    for i, intent in enumerate(INTENTS):
        before, after = 'sg-%03d' % (2 * i + 1), 'sg-%03d' % (2 * i + 2)
        b, a = index[before], index[after]
        require(b['metadata']['role'] == 'historical_before'
                and a['metadata']['role'] == 'historical_specification_control', 'pair roles differ')
        require(selected[before]['history']['refactor_commit'] == selected[after]['revision'], 'pair history differs')
        for mode, text in (('code', b['metadata']['source']['site']['code']), ('intent', intent)):
            queries.append(dict(id=before + '-' + mode, mode=mode, text=text, source=b['metadata']['source']['site'],
                                relevant_document=after, family_id=b['metadata']['family_id']))
    require(len(documents) == 45 and len(queries) == 30, 'bounded pilot size differs')
    require(not ({q['source']['excerpt_sha256'] for q in queries}
                 & {d['source']['excerpt_sha256'] for d in documents}), 'query source is present in index')
    return dict(contract='specmetrics.embeddinggemma-retrieval/v1', model=MODEL, revision=REVISION,
                modalities='text_code_only', dimensions=[768, 256], query_prompt='CodeRetrieval',
                document_prompt='explicit_title_text_no_additional_prefix',
                documents=documents, queries=queries,
                source_sha256={str(p.relative_to(ROOT)): sha(raw[p.name]) for p in paths},
                reference='historical_counterpart_not_semantic_equivalence_or_independent_gold',
                intent_queries='hand_authored_development_queries_from_known_before_sites',
                tuning=False, metric_effect='none')


def verify_preparation(directory):
    expected = encoded(packet())
    require((directory / 'packet.json').read_bytes() == expected, 'prepared corpus changed')
    return json.loads(expected)


def tokens(text):
    return re.findall(r'[a-z]+|[0-9]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', text).lower())


def ranked(scores, identifiers):
    return sorted(range(len(identifiers)), key=lambda i: (-float(scores[i]), identifiers[i]))


def summarize(rows):
    result = {}
    for mode in ('code', 'intent'):
        group = [r for r in rows if r['mode'] == mode]
        result[mode] = dict(queries=len(group), mrr=sum(1 / r['rank'] for r in group) / len(group),
                           **{'recall@' + str(k): sum(r['rank'] <= k for r in group) / len(group) for k in (1, 5, 10)})
    return result


def score(data, docs, queries):
    import numpy as np
    from rank_bm25 import BM25Okapi
    require(docs.shape == (45, 768) and queries.shape == (30, 768), 'embedding shape differs')
    require(np.isfinite(docs).all() and np.isfinite(queries).all(), 'non-finite embedding')
    identifiers = [d['id'] for d in data['documents']]
    baseline = BM25Okapi([tokens(d['text']) for d in data['documents']])
    lexical = [ranked(baseline.get_scores(tokens(q['text'])), identifiers) for q in data['queries']]
    rankings = {'bm25': lexical}
    for dim in data['dimensions']:
        d, q = docs[:, :dim].astype(np.float64), queries[:, :dim].astype(np.float64)
        dn, qn = np.linalg.norm(d, axis=1, keepdims=True), np.linalg.norm(q, axis=1, keepdims=True)
        require((dn > 0).all() and (qn > 0).all(), 'zero embedding norm')
        # Small frozen pilot: fixed-order float64 reduction avoids BLAS-specific
        # float32 behavior and makes saved-vector replay portable.
        similarities = np.einsum('qd,nd->qn', q / qn, d / dn, optimize=False)
        require(np.isfinite(similarities).all(), 'non-finite cosine similarity')
        dense = [ranked(row, identifiers) for row in similarities]
        rankings['dense_' + str(dim)] = dense
        hybrid = []
        for left, right in zip(lexical, dense):
            fused = [0.0] * len(identifiers)
            for order in (left, right):
                for rank, pos in enumerate(order, 1):
                    fused[pos] += 1 / (60 + rank)
            hybrid.append(ranked(fused, identifiers))
        rankings['hybrid_' + str(dim)] = hybrid
    output = {}
    for method, orders in rankings.items():
        rows = []
        for query, order in zip(data['queries'], orders):
            ids = [identifiers[i] for i in order]
            rows.append(dict(query_id=query['id'], mode=query['mode'], expected=query['relevant_document'],
                             rank=ids.index(query['relevant_document']) + 1, ranked_documents=ids))
        output[method] = dict(summary=summarize(rows), rows=rows)
    return output


def execute(preparation, destination, source_repo, device):
    data = verify_preparation(preparation)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'packet.json').write_bytes(encoded(data))
    (destination / 'authorization.json').write_bytes(encoded(dict(
        basis='User: Ок, делай — local EmbeddingGemma pilot', local_inference=True, hosted_inference=False,
        model=MODEL, revision=REVISION, documents=45, queries=30, warmup_inputs=1)))
    started = time.perf_counter()
    producer_hash = sha(Path(__file__).read_bytes())
    try:
        verified = subprocess.run([sys.executable, str(ROOT / 'build_specgraph_corpus.py'),
                                   '--repo', str(source_repo), '--check'], check=True, capture_output=True, text=True)
        (destination / 'source-verification.txt').write_text(verified.stdout)
        os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
        from huggingface_hub import snapshot_download
        import numpy as np
        import torch
        from sentence_transformers import SentenceTransformer
        require(device != 'mps' or torch.backends.mps.is_available(), 'MPS is unavailable; select CPU explicitly')
        print('Downloading pinned public model snapshot...', flush=True)
        download_started = time.perf_counter()
        snapshot = snapshot_download(MODEL, revision=REVISION, token=False)
        download_seconds = time.perf_counter() - download_started
        load_started = time.perf_counter()
        print('Loading text/code encoder on ' + device + '...', flush=True)
        model = SentenceTransformer(snapshot, device=device, trust_remote_code=False,
                                    config_kwargs={'vision_config': None, 'audio_config': None},
                                    model_kwargs={'torch_dtype': torch.float32})
        model.eval()
        require('CodeRetrieval' in model.prompts, 'model has no CodeRetrieval prompt')
        require(model.get_sentence_embedding_dimension() == 768, 'model output dimensions differ')
        require(model.max_seq_length >= 8192, 'unexpected model context window')
        config = model[0].auto_model.config
        require(getattr(config, 'vision_config', None) is None and getattr(config, 'audio_config', None) is None,
                'non-text encoders were not disabled')
        load_seconds = time.perf_counter() - load_started
        doc_text = [d['text'] for d in data['documents']]
        query_text = [q['text'] for q in data['queries']]
        prefix = model.prompts['CodeRetrieval']
        lengths = [len(model.tokenizer.encode(t)) for t in doc_text + [prefix + t for t in query_text]]
        require(max(lengths) <= model.max_seq_length, 'input exceeds context; never silently truncate')
        model.encode(['Find a reusable rule'], prompt_name='CodeRetrieval', normalize_embeddings=True)
        print('Encoding 45 documents and 30 queries...', flush=True)
        index_started = time.perf_counter()
        docs = model.encode(doc_text, prompt='', normalize_embeddings=True, batch_size=4, show_progress_bar=False)
        index_seconds = time.perf_counter() - index_started
        vectors, latency = [], []
        for query in query_text:
            tick = time.perf_counter()
            vectors.append(model.encode(query, prompt_name='CodeRetrieval', normalize_embeddings=True,
                                        show_progress_bar=False))
            latency.append(time.perf_counter() - tick)
        queries = np.stack(vectors)
        np.savez_compressed(destination / 'embeddings.npz', documents=docs, queries=queries)
        tick = time.perf_counter()
        scored = score(data, docs, queries)
        scoring_seconds = time.perf_counter() - tick
        require(producer_hash == sha(Path(__file__).read_bytes()), 'producer changed during execution')
        receipt = dict(status='completed_local_inference', model=MODEL, revision=REVISION, device=device,
                       dtype='float32', parameters=sum(p.numel() for p in model.parameters()),
                       active_config=dict(vision_config=getattr(model[0].auto_model.config, 'vision_config', None),
                                          audio_config=getattr(model[0].auto_model.config, 'audio_config', None)),
                       query_prefix=prefix, maximum_input_tokens=max(lengths),
                       document_input_tokens=lengths[:45], query_input_tokens=lengths[45:],
                       download_seconds=download_seconds, load_seconds=load_seconds,
                       index_seconds=index_seconds, query_seconds=latency, scoring_seconds=scoring_seconds,
                       total_seconds=time.perf_counter() - started,
                       process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
                       memory_scope='process lifetime RSS peak, excludes separate GPU/driver allocation',
                       mps_allocated_bytes_at_end=(torch.mps.current_allocated_memory() if device == 'mps' else None),
                       mps_driver_bytes_at_end=(torch.mps.driver_allocated_memory() if device == 'mps' else None),
                       platform=platform.platform(), python=platform.python_version(),
                       packages={n: importlib.metadata.version(n) for n in (
                           'sentence-transformers', 'transformers', 'torch', 'numpy', 'huggingface-hub', 'rank-bm25')},
                       producer_sha256=producer_hash, packet_sha256=sha(encoded(data)),
                       embeddings_sha256=sha((destination / 'embeddings.npz').read_bytes()),
                       hosted_inference_requests=0, metric_effect='none')
        (destination / 'packages.json').write_bytes(encoded({
            item.metadata['Name']: item.version for item in importlib.metadata.distributions()}))
        (destination / 'scores.json').write_bytes(encoded(scored))
        (destination / 'receipt.json').write_bytes(encoded(receipt))
        print(json.dumps(dict(status=receipt['status'], summaries={k:v['summary'] for k,v in scored.items()},
                              index_seconds=index_seconds, mean_query_seconds=sum(latency)/len(latency)), indent=2))
    except Exception as error:
        (destination / 'failure.json').write_bytes(encoded(dict(status='failed', error_type=type(error).__name__,
            message=str(error), producer_sha256=producer_hash, elapsed_seconds=time.perf_counter()-started)))
        raise


def verify_run(directory):
    import numpy as np
    data = json.loads((directory / 'packet.json').read_bytes())
    require(data == packet(), 'run packet differs from prepared source corpus')
    receipt = json.loads((directory / 'receipt.json').read_bytes())
    require(receipt['status'] == 'completed_local_inference', 'run is not complete')
    require(receipt['model'] == MODEL and receipt['revision'] == REVISION, 'run model identity differs')
    require(receipt['hosted_inference_requests'] == 0 and receipt['metric_effect'] == 'none', 'run authority differs')
    require(not (directory / 'failure.json').exists(), 'run contains failure record')
    require(receipt['packet_sha256'] == sha(encoded(data)), 'packet hash differs')
    require(receipt['embeddings_sha256'] == sha((directory / 'embeddings.npz').read_bytes()), 'embedding snapshot differs')
    require(receipt['producer_sha256'] == sha(Path(__file__).read_bytes()), 'execution producer changed')
    with np.load(directory / 'embeddings.npz', allow_pickle=False) as values:
        result = score(data, values['documents'], values['queries'])
    require(result == json.loads((directory / 'scores.json').read_bytes()), 'ranking replay differs')
    print('Verified local embedding/ranking replay: 30 queries, 45 documents; no inference.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, default=PREPARATION)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', action='store_true')
    action.add_argument('--execute', type=Path)
    action.add_argument('--verify', type=Path)
    parser.add_argument('--source-repo', type=Path)
    parser.add_argument('--device', choices=['cpu', 'mps'], default='mps')
    args = parser.parse_args()
    if args.prepare:
        args.preparation.mkdir(parents=True, exist_ok=False)
        (args.preparation / 'packet.json').write_bytes(encoded(packet()))
        print('Prepared 30 queries and 45 documents; no inference.')
    elif args.execute:
        parser.error('--source-repo is required') if args.source_repo is None else None
        execute(args.preparation, args.execute, args.source_repo, args.device)
    else:
        verify_run(args.verify)


if __name__ == '__main__':
    main()
