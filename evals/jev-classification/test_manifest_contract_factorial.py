"""Regression controls for source-bound balanced preparation and attempts."""
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest

import prepare_manifest_contract_balanced as preparation
import validate_manifest_contract_factorial as subject
from question_grouping import canonical, digest


class ManifestContractFactorialTests(unittest.TestCase):
    def setUp(self):
        self.outputs = preparation.verify()
        self.plan = self.outputs['dispatch-plan.json']
        self.selected = next(a for a in self.plan['assignments'] if any(c['case_id'] == 'target-01' and c['cell'] == '02' for c in a['cases']))
        self.packet = copy.deepcopy(self.outputs[self.selected['packet']])
        self.template = copy.deepcopy(self.outputs[self.selected['template']])
        self.assignment = {'slot': self.selected['slot'], 'directory': '/private/tmp/synthetic-unit-test-only',
                           'context_inheritance': 'none', 'agent_task': 'synthetic_fixture_not_a_real_annotation',
                           'provider_requests': 0, 'human_gold': False, 'metric_effect': 'none',
                           'reference_frozen_for_provider_scoring': False}
        # Put the focal case first in test fixtures only; identity is case-bound.
        self.packet['cases'].sort(key=lambda c: c['case_id'])
        self.template['annotations'].sort(key=lambda c: c['case_id'])
        rows = []
        for case, blank in zip(self.packet['cases'], self.template['annotations']):
            row = copy.deepcopy(blank)
            row.update(opportunity='needs_review', concern_kind='unknown',
                       rationales={a: 'Synthetic structural fixture, not a semantic judgment.' for a in subject.AXES},
                       evidence_quotes=[{'axis': a, 'fragment_id': 'target',
                                         'quote': case['state']['target']['code']} for a in subject.AXES],
                       uncertainties=['Synthetic fixture retains responsibility ambiguity.'])
            rows.append(row)
        self.annotation = {'status': 'independently_annotated_not_adjudicated', 'annotations': rows,
                           'isolation_report': {'input_files': [self.assignment['directory'] + '/' + n
                                                               for n in ('packet.json', 'template.json')],
                                                'other_inputs_read': False}}
        self.delivery = tempfile.TemporaryDirectory()
        self.addCleanup(self.delivery.cleanup)
        self.assignment['directory'] = self.delivery.name
        self.annotation['isolation_report']['input_files'] = [self.delivery.name + '/' + n for n in ('packet.json', 'template.json')]


    def validate(self):
        return subject.validate_annotation(self.packet, self.template, self.annotation, self.assignment)

    def bind_attempt(self):
        files = {'packet.json': preparation.encoded(self.outputs[self.selected['packet']]),
                 'template.json': preparation.encoded(self.outputs[self.selected['template']]),
                 'prompt.txt': preparation.PROMPT.format(directory=self.assignment['directory']).encode()}
        self.assignment['delivered_files'] = {}
        for name, data in files.items():
            path = Path(self.delivery.name) / name
            path.write_bytes(data)
            self.assignment['delivered_files'][name] = str(path)
            if name == 'prompt.txt':
                self.assignment['dispatched_prompt_sha256'] = digest(data)
            else:
                self.assignment.setdefault('input_file_sha256', {})[name] = digest(data)
        raw = preparation.encoded(self.annotation)
        self.assignment['raw_output_sha256'] = digest(raw)
        return raw

    def test_frozen_replay_and_no_dispatch(self):
        result = subject.validate_preparation()
        self.assertFalse(result['annotation_started'])
        self.assertEqual(result['provider_requests'], 0)
        self.assertFalse(result['semantic_correctness_verified'])

    def test_one_view_and_three_case_identical_repetitions_per_cell(self):
        counts = Counter()
        tasks = {}
        for assignment in self.plan['assignments']:
            self.assertEqual(len(assignment['cases']), 4)
            for entry, case in zip(assignment['cases'], self.outputs[assignment['packet']]['cases']):
                key = (entry['case_id'], entry['cell'])
                counts[key] += 1
                tasks.setdefault(key, set()).add(preparation.encoded(case))
        self.assertEqual(len(counts), 16)
        self.assertEqual(set(counts.values()), {3})
        self.assertTrue(all(len(v) == 1 for v in tasks.values()))

    def test_additive_factors_and_fixed_baseline_profile_rubric(self):
        states = {}
        for cell in ('01', '02', '03', '04'):
            a = next(a for a in self.plan['assignments'] if any(c['case_id'] == 'target-01' and c['cell'] == cell for c in a['cases']))
            packet = self.outputs[a['packet']]
            states[cell] = next(c['state'] for c in packet['cases'] if c['case_id'] == 'target-01')
            self.assertEqual(packet['questions'], self.packet['questions'])
            self.assertEqual(packet['rubric_sha256'], digest(self.outputs['rubric.json']))
            self.assertNotIn('cell', packet)
            self.assertNotIn('source-mapping', packet)
            self.assertIsNone(self.outputs[a['template']]['annotations'][0]['opportunity'])
        base = states['01']['bounded_context']['fragments']
        for state in states.values():
            self.assertEqual(state['bounded_context']['fragments'][:4], base)
            self.assertEqual(state['target'], states['01']['target'])
            self.assertEqual(state['architecture_profile'], states['01']['architecture_profile'])
        def additions(cell, key):
            return [f[key] for f in states[cell]['bounded_context']['fragments'][4:] if key in f]
        self.assertEqual(additions('02', 'text'), additions('04', 'text'))
        self.assertEqual(additions('03', 'code'), additions('04', 'code'))
        self.assertEqual(len(additions('02', 'code')), 0)
        self.assertEqual(len(additions('03', 'text')), 0)
        self.assertEqual(digest(canonical(states['01'])), preparation.legacy.inputs()[0]['baseline_state_sha256'])

    def test_document_quotes_are_accepted_with_explicit_fragment(self):
        fragment = next(f for f in self.packet['cases'][0]['state']['bounded_context']['fragments'] if 'text' in f)
        self.annotation['annotations'][0]['evidence_quotes'][0] = {
            'axis': 'opportunity', 'fragment_id': fragment['fragment_id'],
            'quote': 'Path traversal and local digest mismatches fail closed.'}
        self.assertFalse(self.validate()['semantic_correctness_verified'])

    def test_rejects_quote_from_wrong_fragment(self):
        self.annotation['annotations'][0]['evidence_quotes'][0]['fragment_id'] = 'fragment-02'
        with self.assertRaisesRegex(ValueError, 'assigned fragment'):
            self.validate()

    def test_rejects_changed_target_and_stale_identity(self):
        self.packet['cases'][0]['state']['target']['code'] = 'path.is_absolute()'
        with self.assertRaisesRegex(ValueError, 'task content'):
            self.validate()

    def test_rejects_missing_axis_evidence_and_unexplained_abstention(self):
        original = copy.deepcopy(self.annotation)
        self.annotation['annotations'][0]['evidence_quotes'].pop()
        with self.assertRaisesRegex(ValueError, 'Both axes'):
            self.validate()
        self.annotation = original
        self.annotation['annotations'][0]['uncertainties'] = []
        with self.assertRaisesRegex(ValueError, 'material uncertainty'):
            self.validate()

    def test_rejects_context_or_input_scope_deviation(self):
        self.assignment['context_inheritance'] = 'all'
        with self.assertRaisesRegex(ValueError, 'Fresh context'):
            self.validate()
        self.assignment['context_inheritance'] = 'none'
        self.annotation['isolation_report']['other_inputs_read'] = True
        with self.assertRaisesRegex(ValueError, 'scope deviates'):
            self.validate()

    def test_attempt_bindings_and_authority(self):
        raw = self.bind_attempt()
        result = subject.validate_attempt(preparation.RUN, self.assignment, raw)
        self.assertEqual(result['slot'], self.selected['slot'])
        self.assertEqual(result['manual_rationale_checks'], 'pending')
        self.assignment['provider_requests'] = 7
        with self.assertRaisesRegex(ValueError, 'provider_requests'):
            subject.validate_attempt(preparation.RUN, self.assignment, raw)

    def test_rejects_stale_raw_prompt_and_input_bindings(self):
        raw = self.bind_attempt()
        original = copy.deepcopy(self.assignment)
        for key in ('raw_output_sha256', 'dispatched_prompt_sha256'):
            self.assignment = copy.deepcopy(original)
            self.assignment[key] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'binding differs'):
                subject.validate_attempt(preparation.RUN, self.assignment, raw)
        self.assignment = original
        self.assignment['input_file_sha256']['packet.json'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'input binding'):
            subject.validate_attempt(preparation.RUN, self.assignment, raw)

    def test_rejects_tampered_delivered_files_despite_correct_receipt_hashes(self):
        for name in ('packet.json', 'template.json', 'prompt.txt'):
            with self.subTest(name=name):
                raw = self.bind_attempt()
                Path(self.assignment['delivered_files'][name]).write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError, 'Delivered bytes differ: ' + name):
                    subject.validate_attempt(preparation.RUN, self.assignment, raw)

    def test_delivery_preflight_rejects_missing_file(self):
        self.bind_attempt()
        Path(self.assignment['delivered_files']['prompt.txt']).unlink()
        with self.assertRaisesRegex(ValueError, 'Delivered file unavailable'):
            subject.validate_delivery(preparation.RUN, self.assignment)

    def test_delivery_preflight_does_not_adjudicate_or_require_dispatch(self):
        self.bind_attempt()
        self.assignment['agent_task'] = None
        self.assignment['context_inheritance'] = None
        result = subject.validate_delivery(preparation.RUN, self.assignment)
        self.assertEqual(result['status'], 'delivery_bytes_verified_not_dispatched')
        self.assertFalse(result['semantic_correctness_verified'])

    def test_rejects_missing_or_duplicate_case(self):
        self.annotation['annotations'][1] = copy.deepcopy(self.annotation['annotations'][0])
        with self.assertRaisesRegex(ValueError, 'case set'):
            self.validate()

    def test_rejects_cross_case_quote(self):
        self.annotation['annotations'][0]['evidence_quotes'][0]['quote'] = self.packet['cases'][1]['state']['target']['code']
        with self.assertRaisesRegex(ValueError, 'assigned fragment'):
            self.validate()

    def test_writer_rejects_overwrite_and_replay_rejects_drift(self):
        with tempfile.TemporaryDirectory() as parent:
            run = Path(parent) / 'new'
            preparation.write(run)
            preparation.verify(run)
            with self.assertRaises(FileExistsError):
                preparation.write(run)
            (run / 'packet-annotator-01.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'preparation differs'):
                preparation.verify(run)


if __name__ == '__main__':
    unittest.main()
