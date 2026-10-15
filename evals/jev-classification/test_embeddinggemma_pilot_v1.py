"""Offline retrieval contracts; no model import, download or inference."""
import unittest
import tempfile
from pathlib import Path

import numpy as np

import embeddinggemma_pilot_v1 as pilot


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.data = pilot.packet()
        rng = np.random.default_rng(7)
        self.docs = rng.standard_normal((45, 768)).astype(np.float32)
        self.queries = rng.standard_normal((30, 768)).astype(np.float32)

    def test_preparation_and_no_exact_query_leakage(self):
        self.assertEqual(pilot.verify_preparation(pilot.PREPARATION), self.data)
        ids = {d['id'] for d in self.data['documents']}
        self.assertEqual(len(ids), 45)
        self.assertEqual(len(self.data['queries']), 30)
        self.assertTrue(all(q['relevant_document'] in ids for q in self.data['queries']))
        texts = {d['source']['excerpt_sha256'] for d in self.data['documents']}
        self.assertTrue(all(q['source']['excerpt_sha256'] not in texts for q in self.data['queries']))

    def test_all_methods_rank_every_document_and_separate_query_modes(self):
        result = pilot.score(self.data, self.docs, self.queries)
        self.assertEqual(set(result), {'bm25', 'dense_768', 'dense_256', 'hybrid_768', 'hybrid_256'})
        ids = {d['id'] for d in self.data['documents']}
        for output in result.values():
            self.assertEqual(len(output['rows']), 30)
            for row in output['rows']:
                self.assertEqual(set(row['ranked_documents']), ids)
                self.assertEqual(row['ranked_documents'][row['rank'] - 1], row['expected'])
            for mode in ('code', 'intent'):
                self.assertEqual(output['summary'][mode]['queries'], 15)

    def test_truncated_vectors_are_renormalized(self):
        # A has the best direction but very little mass in its first 256 values.
        # B wins an unnormalized truncated dot product; correct cosine picks A.
        docs = np.zeros((45, 768), dtype=np.float32)
        docs[:, 2] = 1
        docs[0] = 0
        docs[0, 0], docs[0, 400] = .01, 1
        docs[1] = 0
        docs[1, 0], docs[1, 1] = .9, .1
        queries = np.zeros((30, 768), dtype=np.float32)
        queries[:, 0] = 1
        result = pilot.score(self.data, docs, queries)
        self.assertEqual(result['dense_256']['rows'][0]['ranked_documents'][0], self.data['documents'][0]['id'])
        self.assertEqual(result['dense_768']['rows'][0]['ranked_documents'][0], self.data['documents'][1]['id'])

    def test_bad_vectors_fail_closed(self):
        for alteration in ('shape', 'nan', 'zero_prefix'):
            with self.subTest(alteration=alteration):
                docs = self.docs.copy()
                if alteration == 'shape':
                    docs = docs[:, :256]
                elif alteration == 'nan':
                    docs[0, 0] = np.nan
                else:
                    docs[0, :256] = 0
                with self.assertRaises(ValueError):
                    pilot.score(self.data, docs, self.queries)

    def test_ties_use_document_id(self):
        self.assertEqual(pilot.ranked([.5, .8, .5], ['z', 'm', 'a']), [1, 2, 0])

    def test_replay_detects_vector_ranking_and_identity_tampering(self):
        for alteration in (None, 'vectors', 'ranking', 'revision', 'failure'):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'packet.json').write_bytes(pilot.encoded(self.data))
                np.savez_compressed(root / 'embeddings.npz', documents=self.docs, queries=self.queries)
                output = pilot.score(self.data, self.docs, self.queries)
                receipt = dict(status='completed_local_inference', model=pilot.MODEL, revision=pilot.REVISION,
                               hosted_inference_requests=0, metric_effect='none',
                               packet_sha256=pilot.sha(pilot.encoded(self.data)),
                               producer_sha256=pilot.sha(Path(pilot.__file__).read_bytes()),
                               embeddings_sha256=pilot.sha((root / 'embeddings.npz').read_bytes()))
                if alteration == 'vectors':
                    np.savez_compressed(root / 'embeddings.npz', documents=self.docs * 2, queries=self.queries)
                elif alteration == 'ranking':
                    output['dense_768']['rows'][0]['rank'] = 100
                elif alteration == 'revision':
                    receipt['revision'] = 'different'
                elif alteration == 'failure':
                    (root / 'failure.json').write_text('{}')
                (root / 'scores.json').write_bytes(pilot.encoded(output))
                (root / 'receipt.json').write_bytes(pilot.encoded(receipt))
                if alteration:
                    with self.assertRaises(ValueError):
                        pilot.verify_run(root)
                else:
                    pilot.verify_run(root)


if __name__ == '__main__':
    unittest.main()
