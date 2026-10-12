import json
from pathlib import Path
import unittest

from question_grouping import digest
from replay_expression_construction import exact_construction
from test_ownership_gate import fixture
from matched_expression_plan import REFERENCE


class ExactConstruction(unittest.TestCase):
    def test_outer_call_positive_inner_predicate_unknown(self):
        raw, site = fixture(statement='DECISION = FM((lambda x: x.enabled,))\n')
        start = raw.index(b'FM((', raw.index(b'DECISION'))
        end = len(raw) - 1
        self.assertEqual(exact_construction(raw, site, {'start_byte': start, 'end_byte': end})['status'], 'direct_specification_construction')
        nested_start = raw.index(b'x.enabled')
        self.assertEqual(exact_construction(raw, site, {'start_byte': nested_start, 'end_byte': nested_start + len(b'x.enabled')})['status'], 'unknown')
        with self.assertRaises(ValueError):
            exact_construction(raw + b'# drift\n', site, {'start_byte': start, 'end_byte': end})

    def test_frozen_replay_changes_only_opportunity_on_exact_positives(self):
        run = REFERENCE.parent / '2026-10-12-matched-expression-wires'
        replay = json.loads((run / 'construction-replay.json').read_text())
        native = json.loads((run / 'native-validation.json').read_text())
        positive = {cid for cid, e in replay['evidence'].items() if e['status'] != 'unknown'}
        self.assertEqual(positive, {'expression-02', 'expression-04'})
        raw = {r['request_id']: r for r in native['rows']}
        for row in replay['routes']:
            original = {a: v['choice'] for a, v in raw[row['request_id']]['prediction']['answers'].items()}
            self.assertEqual(row['raw_labels'], original)
            self.assertEqual(row['effective_labels']['concern_kind'], original['concern_kind'])
            self.assertEqual(row['effective_labels']['opportunity'], 'excluded' if row['case_id'] in positive else original['opportunity'])
        self.assertEqual(replay['recorded_semantic_callback_calls'], 24)
        self.assertEqual(replay['new_inference_requests'], 0)
        self.assertEqual(len(replay['routes']), 32)
        self.assertEqual(replay['input_sha256']['responses'], digest((run / 'responses.jsonl').read_bytes()))
        for name, expected in replay['implementation_sha256'].items():
            self.assertEqual(digest((Path(__file__).parent / name).read_bytes()), expected, name)
        for provider in replay['summaries']:
            for repeat in provider['repeats']:
                self.assertEqual(repeat['matched']['opportunity'], 7)
                self.assertEqual(repeat['eligible_recall'], {'recovered': 2, 'planned': 3})
                self.assertFalse(repeat['repeat_criteria_passed'])
                self.assertEqual(repeat['false_positive_ids'], [])


class CoverageTruthiness(unittest.TestCase):
    def test_exact_expression_decision_table_and_non_boolean_empty_value(self):
        packet = json.loads((REFERENCE / 'reference-packet.json').read_text())
        target = next(c for c in packet['cases'] if c['case_id'] == 'expression-03')['state']['target']['code']
        self.assertEqual(target, 'refs and all(ref in existing_ac for ref in refs)')
        # Only this exact verified, fixed expression is compiled. No historical
        # module, arbitrary target string, helper or side effect is executed.
        expression = compile(target, '<fixed-reviewed-expression>', 'eval')
        for refs, existing, skip in [([], set(), False), ([], {'a'}, False), (['a'], set(), False),
                                      (['a'], {'a'}, True), (['a','b'], {'a'}, False),
                                      (['a','b'], {'a','b'}, True), (['a','a'], {'a'}, True)]:
            with self.subTest(refs=refs, existing=existing):
                value = eval(expression, {'__builtins__': {}, 'all': all, 'refs': refs, 'existing_ac': existing})
                self.assertEqual(bool(value), skip)
                if not refs:
                    self.assertEqual(value, [])
                    self.assertIsNot(value, False)


if __name__ == '__main__':
    unittest.main()
