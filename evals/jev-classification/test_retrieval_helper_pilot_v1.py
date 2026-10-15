import ast
import json
import unittest

import numpy as np

import retrieval_helper_pilot_v1 as pilot


class HelperContextTests(unittest.TestCase):
    def test_unique_local_helper_has_exact_source_span(self):
        raw = 'def rule(x):\n    return x > 0\n\nSPEC = PredicateSpec(rule)\n'
        extra = pilot.helpers(raw, 'SPEC = PredicateSpec(rule)\n', 4, 4)
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0]['code'], 'def rule(x):\n    return x > 0\n')
        self.assertEqual(extra[0]['start_line'], 1)
        self.assertEqual(extra[0]['end_line'], 2)

    def test_rebinding_imports_local_scopes_and_recursive_expansion_are_not_followed(self):
        base = 'def rule(x):\n    return other(x)\n\n'
        for body in ('rule = other\nSPEC = PredicateSpec(rule)\n',
                     'from another import rule\nSPEC = PredicateSpec(rule)\n',
                     'def wrap(rule):\n    return PredicateSpec(rule)\n',
                     'SPEC = lambda rule: PredicateSpec(rule)\n',
                     'if condition:\n    def rule(x):\n        return False\nSPEC = PredicateSpec(rule)\n'):
            with self.subTest(body=body):
                self.assertEqual(pilot.helpers(base + body, body), [])
        raw = base + 'def other(x):\n    return x\nSPEC = PredicateSpec(rule)\n'
        self.assertEqual([h['symbol'] for h in pilot.helpers(raw, 'SPEC = PredicateSpec(rule)')], ['rule'])

    def test_indented_partial_excerpt_uses_complete_module_ast(self):
        raw = 'def f():\n    require(True)\nSPEC = PredicateSpec(missing)\n'
        # The original failure: ast.parse on this excerpt raises IndentationError.
        self.assertEqual(pilot.helpers(raw, '    require(True)\n', 2, 2), [])

    def test_wrong_source_hash_or_span_rejected(self):
        raw = 'def f():\n    return True\n'
        doc = pilot.document('f', 'f.py', 'f', 'revision', raw, ast.parse(raw).body[0])
        with self.assertRaisesRegex(ValueError, 'hash'):
            pilot.expand(doc, raw + '\n')
        doc['source']['start_line'] = 2
        with self.assertRaisesRegex(ValueError, 'span'):
            pilot.expand(doc, raw)

    def test_prepared_pairing_isolates_representation_and_language(self):
        data = json.loads((pilot.PREP / 'packet.json').read_text())
        views = dict(pilot.views(data))
        for scope in ('historical', 'current'):
            a, b = views[scope + '_declaration'], views[scope + '_with_helpers']
            self.assertEqual(a['queries'], b['queries'])
            self.assertEqual([d['id'] for d in a['documents']], [d['id'] for d in b['documents']])
            for left, right in zip(a['documents'], b['documents']):
                self.assertEqual(left['source'], right['source'])
                self.assertEqual(left['text'] == right['text'], not bool(right['helpers']))
        queries = data['current']['queries']
        self.assertEqual(len(queries), 16)
        for en, ru in zip(queries[::2], queries[1::2]):
            self.assertEqual((en['mode'], ru['mode']), ('en', 'ru'))
            self.assertEqual(en['relevant_document'], ru['relevant_document'])

    def test_generic_ranker_reproduces_frozen_predecessor(self):
        data = json.loads((pilot.BASE / 'packet.json').read_text())
        with np.load(pilot.BASE / 'embeddings.npz', allow_pickle=False) as saved:
            result = pilot.rankings(data, saved['documents'], saved['queries'])
        previous = json.loads((pilot.BASE / 'scores.json').read_text())
        for method, outcome in result.items():
            self.assertEqual([r['rank'] for r in outcome['rows']], [r['rank'] for r in previous[method]['rows']])
            self.assertEqual([r['top_10'] for r in outcome['rows']], [r['ranked_documents'][:10] for r in previous[method]['rows']])

    def test_malformed_vectors_rejected(self):
        data = dict(documents=[dict(id='target', text='rule')],
                    queries=[dict(id='q', mode='ru', text='правило', relevant_document='target')])
        for kind in ('shape', 'nan', 'zero_prefix'):
            with self.subTest(kind=kind):
                docs = np.ones((1, 768), dtype=np.float32)
                queries = docs.copy()
                if kind == 'shape':
                    docs = docs[:, :256]
                elif kind == 'nan':
                    docs[0, 0] = np.nan
                else:
                    docs[0, :256] = 0
                with self.assertRaises(ValueError):
                    pilot.rankings(data, docs, queries)


if __name__ == '__main__':
    unittest.main()
