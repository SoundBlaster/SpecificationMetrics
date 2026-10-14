"""Exercise scope-v3.1 preflight, retained-attempt boundaries and pending review."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import prepare_scope_binding_v3_1 as preparation
import prepare_scope_binding_handoff as handoff
import validate_scope_binding_annotations as validator
from question_grouping import digest


class ScopeBindingHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / 'new-delivery'
        self.delivery = handoff.materialize(self.destination)
        self.selected = self.delivery['assignments'][0]
        self.receipt_path = self.destination / self.selected['attempt_receipt']
        self.receipt = json.loads(self.receipt_path.read_text())
        self.packet = json.loads(Path(self.receipt['delivered_files']['packet.json']).read_text())
        self.template = json.loads(Path(self.receipt['delivered_files']['template.json']).read_text())

    def fixture(self):
        annotation = copy.deepcopy(self.template)
        annotation['status'] = 'independently_annotated_not_adjudicated'
        for row, case in zip(annotation['annotations'], self.packet['cases']):
            row.update(opportunity='needs_review', concern_kind='unknown',
                       rationales={a: 'Synthetic structural fixture; semantic review remains pending.' for a in validator.AXES},
                       evidence_quotes=[{'axis': a, 'fragment_id': 'target', 'quote': case['state']['target']['code']}
                                        for a in validator.AXES],
                       uncertainties=['Synthetic uncertainty, not an independent annotation.'])
        annotation['isolation_report'] = {
            'input_files': [self.receipt['directory'] + '/' + n for n in ('packet.json', 'template.json')],
            'other_inputs_read': False}
        self.receipt.update(context_inheritance='none', agent_task='synthetic_test_fixture_not_a_real_agent')
        return annotation

    def validate(self, annotation):
        raw = preparation.encoded(annotation)
        self.receipt['raw_output_sha256'] = digest(raw)
        return validator.validate_attempt(preparation.RUN, self.receipt, raw)

    def test_all_deliveries_preflight_and_annotators_only_get_two_inputs(self):
        self.assertEqual(len(self.delivery['assignments']), 12)
        for assignment in self.delivery['assignments']:
            folder = Path(assignment['directory'])
            self.assertEqual({p.name for p in folder.iterdir()}, {'packet.json', 'template.json'})
            receipt = json.loads((self.destination / assignment['attempt_receipt']).read_text())
            result = validator.validate_delivery(preparation.RUN, receipt)
            self.assertTrue(result['scope_input_binding_verified'])
            self.assertEqual(result['protocol'], 'scope-binding-v3.1')
            self.assertIsNone(receipt['agent_task'])
        self.assertFalse(self.delivery['annotation_started'])
        self.assertFalse(self.delivery['preparation_stage_dispatch_ready'])
        self.assertTrue(self.delivery['scope_handoff_available'])
        self.assertFalse(self.delivery['semantic_grader_implemented'])

    def test_structural_scope_ack_is_not_semantic_understanding(self):
        result = self.validate(self.fixture())
        self.assertEqual(result['annotated_cases'], 4)
        self.assertTrue(result['scope_acknowledgments_verified'])
        self.assertFalse(result['scope_semantic_fidelity_verified'])
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertEqual(result['manual_scope_review'], 'pending')
        self.assertFalse(result['model_runtime_identity_verified'])

    def test_unfilled_receipt_is_not_a_completed_attempt(self):
        raw = preparation.encoded(self.template)
        with self.assertRaisesRegex(ValueError, 'raw output binding'):
            validator.validate_attempt(preparation.RUN, self.receipt, raw)
        self.receipt['raw_output_sha256'] = digest(raw)
        with self.assertRaises(ValueError):
            validator.validate_attempt(preparation.RUN, self.receipt, raw)

    def test_returned_wrong_scope_unit_or_binding_digest_is_rejected(self):
        for field, value in (('scope_unit', 'wrong_unit'), ('scope_binding_sha256', '0' * 64)):
            with self.subTest(field=field):
                annotation = self.fixture()
                annotation['annotations'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'scope acknowledgment'):
                    self.validate(annotation)

    def test_wrong_task_identity_and_duplicate_or_missing_cases_are_rejected(self):
        for change in ('stale_task', 'duplicate', 'missing'):
            with self.subTest(change=change):
                annotation = self.fixture()
                if change == 'stale_task': annotation['annotations'][0]['task_sha256'] = '0' * 64
                if change == 'duplicate': annotation['annotations'][1] = copy.deepcopy(annotation['annotations'][0])
                if change == 'missing': annotation['annotations'].pop()
                with self.assertRaises(ValueError):
                    self.validate(annotation)

    def test_cross_case_quotes_missing_axis_evidence_and_unexplained_abstention_rejected(self):
        for change in ('foreign_quote', 'missing_axis', 'missing_uncertainty'):
            with self.subTest(change=change):
                annotation = self.fixture()
                row = annotation['annotations'][0]
                if change == 'foreign_quote': row['evidence_quotes'][0]['quote'] = self.packet['cases'][1]['state']['target']['code']
                if change == 'missing_axis': row['evidence_quotes'].pop()
                if change == 'missing_uncertainty': row['uncertainties'] = []
                with self.assertRaises(ValueError):
                    self.validate(annotation)

    def test_inherited_context_or_extra_input_self_report_rejected(self):
        annotation = self.fixture()
        self.receipt['context_inheritance'] = 'all'
        with self.assertRaisesRegex(ValueError, 'Fresh context'):
            self.validate(annotation)
        self.receipt['context_inheritance'] = 'none'
        annotation['isolation_report']['other_inputs_read'] = True
        with self.assertRaisesRegex(ValueError, 'scope deviates'):
            self.validate(annotation)

    def test_tampered_input_template_and_prompt_rejected_even_with_updated_receipt_hash(self):
        for name in ('packet.json', 'template.json', 'prompt.txt'):
            with self.subTest(name=name):
                path = Path(self.receipt['delivered_files'][name])
                original = path.read_bytes()
                path.write_bytes(b'{}')
                field = ('dispatched_prompt_sha256' if name == 'prompt.txt' else None)
                if field:
                    old_hash = self.receipt[field]; self.receipt[field] = digest(b'{}')
                else:
                    old_hash = self.receipt['input_file_sha256'][name]
                    self.receipt['input_file_sha256'][name] = digest(b'{}')
                with self.assertRaisesRegex(ValueError, 'Delivered bytes differ'):
                    validator.validate_delivery(preparation.RUN, self.receipt)
                path.write_bytes(original)
                if field: self.receipt[field] = old_hash
                else: self.receipt['input_file_sha256'][name] = old_hash

    def test_pristine_alias_cannot_hide_changed_input_or_prompt(self):
        for name in ('packet.json', 'template.json', 'prompt.txt'):
            with self.subTest(name=name):
                path = Path(self.receipt['delivered_files'][name])
                alias = path.with_name('pristine-' + path.name)
                alias.write_bytes(path.read_bytes())
                self.receipt['delivered_files'][name] = str(alias)
                with self.assertRaisesRegex(ValueError, 'declared dispatch file'):
                    validator.validate_delivery(preparation.RUN, self.receipt)
                self.receipt['delivered_files'][name] = str(path)

    def test_missing_delivered_file_and_stale_stored_hash_rejected(self):
        path = Path(self.receipt['delivered_files']['template.json'])
        raw = path.read_bytes(); path.unlink()
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            validator.validate_delivery(preparation.RUN, self.receipt)
        path.write_bytes(raw)
        self.receipt['input_file_sha256']['template.json'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Recorded delivered hash'):
            validator.validate_delivery(preparation.RUN, self.receipt)

    def test_stale_protocol_preparation_implementation_and_case_bindings_rejected(self):
        original = copy.deepcopy(self.receipt)
        for change in ('protocol', 'preparation_receipt_sha256', 'implementation', 'cases'):
            with self.subTest(change=change):
                self.receipt = copy.deepcopy(original)
                if change == 'implementation':
                    self.receipt['implementation_file_sha256']['validate_scope_binding_annotations.py'] = '0' * 64
                elif change == 'cases': self.receipt['cases'][0]['scope_unit'] = 'wrong'
                else: self.receipt[change] = 'wrong'
                with self.assertRaises(ValueError):
                    validator.validate_delivery(preparation.RUN, self.receipt)

    def test_stale_raw_and_false_authority_declarations_rejected(self):
        annotation = self.fixture()
        raw = preparation.encoded(annotation)
        self.receipt['raw_output_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'raw output binding'):
            validator.validate_attempt(preparation.RUN, self.receipt, raw)
        original = copy.deepcopy(self.receipt)
        for field, value in (('provider_requests', 7), ('provider_requests', False), ('human_gold', True),
                             ('metric_effect', 'production'), ('reference_frozen_for_provider_scoring', True)):
            with self.subTest(field=field, value=value):
                self.receipt = copy.deepcopy(original); self.receipt[field] = value
                with self.assertRaisesRegex(ValueError, 'authority invariant'):
                    self.validate(annotation)

    def test_invalid_json_and_malformed_quotes_are_intentional_failures(self):
        self.receipt.update(context_inheritance='none', agent_task='synthetic')
        self.receipt['raw_output_sha256'] = digest(b'bad')
        with self.assertRaisesRegex(ValueError, 'UTF-8 JSON'):
            validator.validate_attempt(preparation.RUN, self.receipt, b'bad')
        annotation = self.fixture()
        annotation['annotations'][0]['evidence_quotes'][0]['axis'] = []
        with self.assertRaises(ValueError):
            self.validate(annotation)

    def test_v3_0_input_and_existing_destination_cannot_be_reused(self):
        with self.assertRaises(ValueError):
            handoff.materialize(self.destination.parent / 'old-protocol', preparation.historical.RUN)
        self.assertFalse((self.destination.parent / 'old-protocol').exists())
        with self.assertRaises(FileExistsError):
            handoff.materialize(self.destination)

    def test_manual_review_is_independent_pending_and_covers_all_48_rows(self):
        review = handoff.review_template(preparation.verify())
        self.assertEqual(set(review['criteria']), {'scope_fidelity', 'role_witness', 'ownership'})
        for criterion in review['criteria'].values():
            self.assertIsNone(criterion['met'])
            self.assertEqual(len(criterion['entries']), 48)
            self.assertEqual(len({(e['slot'], e['case_id']) for e in criterion['entries']}), 48)
            self.assertTrue(all(e['raw_output_sha256'] is None and e['criterion_met'] is None for e in criterion['entries']))
        review['criteria']['scope_fidelity']['entries'][0]['review_note'] = 'synthetic'
        self.assertIsNone(review['criteria']['role_witness']['entries'][0]['review_note'])

    def test_cli_preflight_and_complete_attempt_replay(self):
        annotation = self.fixture()
        raw = preparation.encoded(annotation)
        self.receipt['raw_output_sha256'] = digest(raw)
        self.receipt_path.write_bytes(preparation.encoded(self.receipt))
        output = self.destination / 'synthetic-output.json'; output.write_bytes(raw)
        command = [sys.executable, str(preparation.ROOT / 'validate_scope_binding_annotations.py'),
                   '--assignment', str(self.receipt_path)]
        preflight = subprocess.run(command + ['--check-delivery'], capture_output=True, text=True)
        self.assertEqual(preflight.returncode, 0, preflight.stderr)
        replay = subprocess.run(command + ['--annotation', str(output)], capture_output=True, text=True)
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertFalse(json.loads(replay.stdout)['scope_semantic_fidelity_verified'])
        invalid = subprocess.run(command + ['--annotation', str(output), '--check-delivery'], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)


if __name__ == '__main__':
    unittest.main()
