"""Regression checks for frozen annotation provenance and independent axes."""
import copy
import json
import unittest

import validate_definition_owner_annotations as subject


class AnnotationValidationTests(unittest.TestCase):
    def setUp(self):
        receipt = json.loads((subject.RUN / 'execution-receipt.json').read_text())
        self.assignment = receipt['assignments'][0]
        self.packet = json.loads((subject.PREPARATION / self.assignment['packet']).read_text())
        self.template = json.loads((subject.PREPARATION / self.assignment['template']).read_text())
        self.annotation = json.loads((subject.RUN / self.assignment['annotation_output']).read_text())

    def validate(self):
        return subject.validate(self.packet, self.template, self.annotation, self.assignment)

    def test_frozen_results_replay(self):
        result = subject.build()
        self.assertEqual(result, json.loads((subject.RUN / 'validation-summary.json').read_text()))
        self.assertEqual(result['case_annotations'], 64)
        self.assertFalse(result['summary']['semantic_correctness_verified'])
        self.assertEqual(result['summary']['metric_effect'], 'none')

    def test_rejects_stale_identity(self):
        self.annotation['annotations'][0]['task_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.validate()

    def test_recomputes_task_content(self):
        self.packet['cases'][0]['state']['target']['code'] += ' '
        with self.assertRaisesRegex(ValueError, 'Task content'):
            self.validate()

    def test_rejects_cross_case_quote(self):
        self.annotation['annotations'][0]['evidence_quotes'][0]['quote'] = self.packet['cases'][1]['state']['target']['code']
        with self.assertRaisesRegex(ValueError, 'same case'):
            self.validate()

    def test_rejects_duplicate_case(self):
        self.annotation['annotations'][-1] = copy.deepcopy(self.annotation['annotations'][0])
        with self.assertRaisesRegex(ValueError, 'four unique'):
            self.validate()

    def test_rejects_missing_axis_evidence(self):
        row = self.annotation['annotations'][0]
        row['evidence_quotes'] = [q for q in row['evidence_quotes'] if q['axis'] == 'opportunity']
        with self.assertRaisesRegex(ValueError, 'both axes'):
            self.validate()

    def test_rejects_undeclared_isolation(self):
        self.annotation['isolation_report']['other_inputs_read'] = True
        with self.assertRaisesRegex(ValueError, 'input scope'):
            self.validate()

    def test_requires_explicit_abstention_reason(self):
        row = self.annotation['annotations'][0]
        row.update(concern_kind='unknown', uncertainties=[])
        with self.assertRaisesRegex(ValueError, 'missing evidence'):
            self.validate()

    def test_axes_remain_independent(self):
        # Already owned can still be policy; unknown responsibility does not
        # erase ownership when an uncertainty is recorded.
        row = self.annotation['annotations'][0]
        self.assertEqual((row['opportunity'], row['concern_kind']), ('excluded', 'policy'))
        row.update(concern_kind='unknown', uncertainties=['Domain purpose is unproved.'])
        self.assertEqual(self.validate()['annotated_cases'], 4)


if __name__ == '__main__':
    unittest.main()
