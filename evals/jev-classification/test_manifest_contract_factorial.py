"""Regression controls for source-bound one-target preparation and attempts."""
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest

import prepare_manifest_contract_factorial as preparation
import validate_manifest_contract_factorial as subject
from question_grouping import canonical, digest


class ManifestContractFactorialTests(unittest.TestCase):
    def setUp(self):
        self.outputs = preparation.verify()
        self.plan = self.outputs['dispatch-plan.json']
        self.selected = next(a for a in self.plan['assignments'] if a['cell'] == '02')
        self.packet = copy.deepcopy(self.outputs[self.selected['packet']])
        self.template = copy.deepcopy(self.outputs[self.selected['template']])
        self.assignment = {'slot': self.selected['slot'], 'directory': '/private/tmp/synthetic-unit-test-only',
                           'context_inheritance': 'none', 'agent_task': 'synthetic_fixture_not_a_real_annotation',
                           'provider_requests': 0, 'human_gold': False, 'metric_effect': 'none',
                           'reference_frozen_for_provider_scoring': False}
        row = copy.deepcopy(self.template['annotations'][0])
        row.update(opportunity='needs_review', concern_kind='unknown',
                   rationales={a: 'Synthetic structural fixture, not a semantic judgment.' for a in subject.AXES},
                   evidence_quotes=[{'axis': a, 'fragment_id': 'target',
                                     'quote': self.packet['cases'][0]['state']['target']['code']} for a in subject.AXES],
                   uncertainties=['Synthetic fixture retains responsibility ambiguity.'])
        self.annotation = {'status': 'independently_annotated_not_adjudicated', 'annotations': [row],
                           'isolation_report': {'input_files': [self.assignment['directory'] + '/' + n
                                                               for n in ('packet.json', 'template.json')],
                                                'other_inputs_read': False}}

    def validate(self):
        return subject.validate_annotation(self.packet, self.template, self.annotation, self.assignment)

    def bind_attempt(self):
        for alias, key in (('packet.json', 'packet'), ('template.json', 'template')):
            self.assignment.setdefault('input_file_sha256', {})[alias] = digest(preparation.encoded(self.outputs[self.selected[key]]))
        self.assignment['dispatched_prompt_sha256'] = digest(preparation.PROMPT.format(directory=self.assignment['directory']).encode())
        raw = preparation.encoded(self.annotation)
        self.assignment['raw_output_sha256'] = digest(raw)
        return raw

    def test_frozen_replay_and_no_dispatch(self):
        result = subject.validate_preparation()
        self.assertFalse(result['annotation_started'])
        self.assertEqual(result['provider_requests'], 0)
        self.assertFalse(result['semantic_correctness_verified'])

    def test_one_view_and_three_byte_identical_repetitions_per_cell(self):
        self.assertEqual(Counter(a['cell'] for a in self.plan['assignments']), dict.fromkeys(('01', '02', '03', '04'), 3))
        for cell in ('01', '02', '03', '04'):
            entries = [a for a in self.plan['assignments'] if a['cell'] == cell]
            self.assertEqual(len({preparation.encoded(self.outputs[a['packet']]) for a in entries}), 1)
            self.assertEqual(len({preparation.encoded(self.outputs[a['template']]) for a in entries}), 1)
            self.assertTrue(all(len(self.outputs[a['packet']]['cases']) == 1 for a in entries))

    def test_additive_factors_and_fixed_baseline_profile_rubric(self):
        states = {}
        for cell in ('01', '02', '03', '04'):
            a = next(a for a in self.plan['assignments'] if a['cell'] == cell)
            packet = self.outputs[a['packet']]
            states[cell] = packet['cases'][0]['state']
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
        self.assertEqual(digest(canonical(states['01'])), preparation.inputs()[0]['baseline_state_sha256'])

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
