"""Regression checks for frozen annotation provenance and independent axes."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
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


class ReplayArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / 'run'
        shutil.copytree(subject.RUN, self.run)

    def write_receipt(self, receipt):
        (self.run / 'execution-receipt.json').write_text(json.dumps(receipt))

    def read_receipt(self):
        return json.loads((self.run / 'execution-receipt.json').read_text())

    def write_review(self, review):
        path = self.run / 'semantic-review.json'
        path.write_text(json.dumps(review))
        receipt = self.read_receipt()
        receipt['semantic_review'] = {'file': path.name, 'sha256': subject.digest(path.read_bytes())}
        self.write_receipt(receipt)

    def read_review(self):
        return json.loads((self.run / 'semantic-review.json').read_text())

    def test_rejects_missing_review(self):
        (self.run / 'semantic-review.json').unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            subject.build(self.run)

    def test_rejects_empty_review_even_when_rebound(self):
        self.write_review({})
        with self.assertRaises(ValueError):
            subject.build(self.run)

    def test_rejects_changed_review_bytes(self):
        with (self.run / 'semantic-review.json').open('a') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'review.*binding'):
            subject.build(self.run)

    def test_rejects_stale_review_assignment_bindings(self):
        original = self.read_review()
        changes = {'raw_output_sha256': '0' * 64, 'raw_output': 'foreign.json',
                   'case_id': 'probe-b', 'cell': '01'}
        for field, value in changes.items():
            with self.subTest(field=field):
                review = copy.deepcopy(original)
                review['H_definition']['entries'][0][field] = value
                self.write_review(review)
                with self.assertRaisesRegex(ValueError, 'review.*assignment'):
                    subject.build(self.run)

    def test_rejects_missing_or_duplicate_review_entries(self):
        original = self.read_review()
        for mutation in ('missing', 'duplicate'):
            with self.subTest(mutation=mutation):
                review = copy.deepcopy(original)
                entries = review['H_definition']['entries']
                if mutation == 'missing':
                    entries.pop()
                else:
                    entries[-1] = copy.deepcopy(entries[0])
                self.write_review(review)
                with self.assertRaisesRegex(ValueError, 'eight.*review'):
                    subject.build(self.run)

    def test_rejects_inconsistent_manual_review_counts(self):
        review = self.read_review()
        review['H_definition']['conflicts'] = 1
        self.write_review(review)
        with self.assertRaisesRegex(ValueError, 'review.*counts'):
            subject.build(self.run)

    def test_preserves_a_manual_failed_criterion(self):
        review = self.read_review()
        row = review['H_definition']['entries'][0]
        row.update(claims_operational_validity_unavailable=True, criterion_met=False)
        review['H_definition'].update(met=False, conflicts=1)
        self.write_review(review)
        result = subject.build(self.run)
        self.assertFalse(result['summary']['H_definition']['met'])
        self.assertFalse(result['summary']['semantic_correctness_verified'])

    def test_rejects_false_receipt_metadata(self):
        original = self.read_receipt()
        changes = {'provider_requests': (7, False, None),
                   'excluded_attempts': ([{'attempt': 'not-preserved'}], None),
                   'human_gold': (True,), 'metric_effect': ('updated',),
                   'reference_frozen_for_provider_scoring': (True,),
                   'fresh_contexts': (15,), 'case_annotations': (63,)}
        for field, values in changes.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    receipt = copy.deepcopy(original)
                    receipt[field] = value
                    self.write_receipt(receipt)
                    with self.assertRaisesRegex(ValueError, 'receipt.*' + field):
                        subject.build(self.run)


if __name__ == '__main__':
    unittest.main()
