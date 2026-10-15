"""Offline diagnosis: Unicode tokenization and evidence-bearing RRF channels."""
import argparse
import json
from pathlib import Path
import re

import numpy as np
from rank_bm25 import BM25Okapi

import retrieval_helper_pilot_v1 as pilot

RUN = pilot.ROOT / 'runs/2026-10-15-retrieval-helper-live-v1'
OUTPUT = pilot.ROOT / 'runs/2026-10-15-retrieval-fusion-replay-v2'


def unicode_tokens(text):
    split = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return re.findall(r'[^\W_]+', split.casefold())


def fuse(lexical_scores, dense_order, ids, *, positive_only):
    lexical_order = pilot.prior.ranked(lexical_scores, ids)
    if positive_only:
        lexical_order = [i for i in lexical_order if lexical_scores[i] > 0]
    scores = [0.0] * len(ids)
    for order in (lexical_order, dense_order):
        for rank, pos in enumerate(order, 1):
            scores[pos] += 1 / (60 + rank)
    return pilot.prior.ranked(scores, ids)


def report(data, documents, queries, tokenizer, positive_only):
    ids = [d['id'] for d in data['documents']]
    bm25 = BM25Okapi([tokenizer(d['text']) for d in data['documents']])
    lexical = [bm25.get_scores(tokenizer(q['text'])) for q in data['queries']]
    orders = {'bm25': [pilot.prior.ranked(s, ids) for s in lexical]}
    if positive_only:
        orders['bm25'] = [[i for i in order if scores[i] > 0] for order, scores in zip(orders['bm25'], lexical)]
    for dimension in (768, 256):
        d, q = documents[:, :dimension].astype(np.float64), queries[:, :dimension].astype(np.float64)
        similarities = np.einsum('qd,nd->qn', q / np.linalg.norm(q, axis=1, keepdims=True),
                                 d / np.linalg.norm(d, axis=1, keepdims=True), optimize=False)
        dense = [pilot.prior.ranked(row, ids) for row in similarities]
        orders['dense_' + str(dimension)] = dense
        orders['hybrid_' + str(dimension)] = [fuse(scores, order, ids, positive_only=positive_only)
                                              for scores, order in zip(lexical, dense)]
    result = {}
    for method, values in orders.items():
        rows = []
        for query, order in zip(data['queries'], values):
            target = ids.index(query['relevant_document'])
            rows.append(dict(query_id=query['id'], mode=query['mode'],
                             rank=order.index(target) + 1 if target in order else None,
                             top_10=[ids[i] for i in order[:10]]))
        summary = {}
        for mode in ('en', 'ru'):
            group = [r for r in rows if r['mode'] == mode]
            summary[mode] = dict(n=len(group), mrr=sum(1 / r['rank'] if r['rank'] else 0 for r in group) / len(group),
                                **{'hits@' + str(k): sum(r['rank'] is not None and r['rank'] <= k for r in group) for k in (1, 5, 10)})
        result[method] = dict(rows=rows, summary=summary)
    return dict(results=result, lexical_diagnostics=[dict(query_id=q['id'], tokens=tokenizer(q['text']),
                    positive_documents=int(np.count_nonzero(scores > 0))) for q, scores in zip(data['queries'], lexical)])


def build():
    pilot.verify(RUN)
    packet = json.loads((RUN / 'packet.json').read_text())
    view = dict(pilot.views(packet))['current_declaration']
    _, mapping = pilot.layout(packet)
    with np.load(RUN / 'embeddings.npz', allow_pickle=False) as saved:
        documents, queries = saved['documents'][mapping['current_declaration']], saved['queries'][30:]
    arms = {}
    for name, tokenizer, positive in (
        ('original_ascii_full_rrf', pilot.prior.tokens, False),
        ('unicode_only_full_rrf', unicode_tokens, False),
        ('positive_only_ascii_rrf', pilot.prior.tokens, True),
        ('unicode_positive_rrf', unicode_tokens, True),
    ):
        arms[name] = report(view, documents, queries, tokenizer, positive)
    frozen = json.loads((RUN / 'scores.json').read_text())['current_declaration']
    pilot.prior.require(arms['original_ascii_full_rrf']['results'] == frozen, 'control differs from frozen v1')
    return dict(contract='specmetrics.retrieval-fusion-repair/v2', inference_requests=0,
                source_vectors_sha256=pilot.prior.sha((RUN / 'embeddings.npz').read_bytes()),
                source_packet_sha256=pilot.prior.sha((RUN / 'packet.json').read_bytes()),
                producer_sha256=pilot.prior.sha(Path(__file__).read_bytes()),
                status='post_failure_development_replay_not_independent_validation', arms=arms)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = build()
    if args.write:
        OUTPUT.mkdir(parents=True, exist_ok=False)
        (OUTPUT / 'replay.json').write_bytes(pilot.prior.encoded(result))
    else:
        pilot.prior.require((OUTPUT / 'replay.json').read_bytes() == pilot.prior.encoded(result), 'v2 replay differs')
    print(json.dumps({name: {method: value['summary'] for method, value in arm['results'].items()}
                      for name, arm in result['arms'].items()}, indent=2))


if __name__ == '__main__':
    main()
