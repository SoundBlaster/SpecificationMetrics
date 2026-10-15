"""Regress action/confidence conflation, trivial wrappers and input substitution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import intent_first_contract_v4 as rules
import prepare_intent_first_v4 as preparation


class IntentFirstContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = preparation.build()
        cls.packet = json.loads(cls.files['packet.json'])
        cls.examples = json.loads(cls.files['integrator-examples.json'])
        cls.contract_hash = rules.digest(cls.files['contract.json'])

    def pair(self, index):
        return copy.deepcopy(self.packet['cases'][index]), copy.deepcopy(self.examples['annotations'][index])

    def test_ambiguous_path_can_recommend_formalization_with_unknown_role(self):
        case, row = self.pair(0)
        self.assertEqual((row['concern_kind'], row['evidence_confidence'], row['recommendation']),
                         ('unknown', 'insufficient', 'formalize'))
        result = rules.validate(case, row, self.contract_hash)
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertFalse(result['provider_scoring_enabled'])
        self.assertTrue(row['intent_review']['missing_context'])

    def test_gate_bdd_and_formatting_have_distinct_actions(self):
        self.assertEqual([r['recommendation'] for r in self.examples['annotations']],
                         ['formalize', 'formalize', 'reuse_specification', 'use_tool_rules'])
        self.assertEqual(len(preparation.validate_examples(self.packet, self.examples, self.contract_hash)), 4)

    def test_unknown_role_cannot_be_claimed_supported(self):
        case, row = self.pair(0)
        row['evidence_confidence'] = 'supported'
        with self.assertRaisesRegex(ValueError, 'unknown role'):
            rules.validate(case, row, self.contract_hash)

    def test_uncertainty_cannot_be_erased_by_formalization_preference(self):
        case, row = self.pair(0)
        row['uncertainties'] = []
        with self.assertRaisesRegex(ValueError, 'explicit uncertainties'):
            rules.validate(case, row, self.contract_hash)

    def test_existing_specification_and_simple_composition_need_no_wrapper(self):
        case, row = self.pair(2)
        for basis in ('existing_specification', 'simple_composition'):
            with self.subTest(basis=basis):
                row['basis'] = basis
                rules.validate(case, row, self.contract_hash)
                row['recommendation'] = 'formalize'
                with self.assertRaisesRegex(ValueError, 'declared basis'):
                    rules.validate(case, row, self.contract_hash)
                row['recommendation'] = 'reuse_specification'
        # This checks contract consistency; it does not prove the BDD source is
        # a Boolean-spec API composition. That remains a semantic evidence question.
        self.assertIsNone(rules.PROFILE['composition_complexity_limit'])

    def test_affirmative_mechanics_can_remain_procedural(self):
        case, row = self.pair(3)
        row.update(recommendation='keep_procedural', basis='mechanics')
        rules.validate(case, row, self.contract_hash)
        row.update(recommendation='formalize', basis='domain_contract')
        with self.assertRaisesRegex(ValueError, 'established mechanics'):
            rules.validate(case, row, self.contract_hash)

    def test_confidence_is_ordinal_not_provider_probability(self):
        case, row = self.pair(1)
        row['evidence_confidence'] = 0.99
        with self.assertRaises(ValueError):
            rules.validate(case, row, self.contract_hash)
        self.assertEqual(json.loads(self.files['contract.json'])['confidence_semantics'],
                         'ordinal_evidence_support_not_provider_probability')

    def test_old_opportunity_answer_and_unexpected_fields_are_rejected(self):
        case, row = self.pair(1)
        for key, value in (('opportunity', 'eligible'), ('provider_confidence', .9)):
            with self.subTest(key=key):
                changed = {**row, key: value}
                with self.assertRaises(ValueError):
                    rules.validate(case, changed, self.contract_hash)

    def test_stale_scope_task_state_or_contract_answer_identity_is_rejected(self):
        case, row = self.pair(1)
        for field in ('case_id', 'task_sha256', 'state_sha256', 'scope_binding_sha256',
                      'contract_sha256', 'contract_id', 'scope_unit'):
            with self.subTest(field=field):
                changed = {**row, field: '0' * 64}
                with self.assertRaises(ValueError):
                    rules.validate(case, changed, self.contract_hash)

    def test_modified_case_bytes_and_profile_are_rejected(self):
        case, row = self.pair(1)
        case['state']['target']['code'] = 'True'
        with self.assertRaisesRegex(ValueError, 'state digest'):
            rules.validate(case, row, self.contract_hash)
        case['state_sha256'] = rules.digest(rules.encoded(case['state']))
        case['state']['architecture_profile']['ambiguity'] = 'Always keep procedural'
        case['state_sha256'] = rules.digest(rules.encoded(case['state']))
        with self.assertRaisesRegex(ValueError, 'profile mismatch'):
            rules.validate(case, row, self.contract_hash)

    def test_contract_and_prompt_changes_change_task_identity(self):
        case, _ = self.pair(0)
        original = case['task_sha256']
        with patch.object(rules, 'PROMPT', rules.PROMPT + ' Changed allowed inputs.'):
            changed = rules.digest(rules.encoded(rules.contract()))
            self.assertNotEqual(rules.task_digest(case, changed), original)

    def test_supplied_documents_must_be_acknowledged_without_importing_other_views(self):
        case, row = self.pair(0)
        row['intent_review']['checked_document_ids'] = ['fragment-11']
        with self.assertRaisesRegex(ValueError, 'document review'):
            rules.validate(case, row, self.contract_hash)
        old, _ = preparation.source_case('target-01', '04')
        case = preparation.make_case(old, '04', self.contract_hash)
        row = preparation.example(case, self.contract_hash, 0)
        with self.assertRaisesRegex(ValueError, 'document review'):
            rules.validate(case, row, self.contract_hash)
        row['intent_review']['checked_document_ids'] = ['fragment-11', 'fragment-12']
        row['intent_review']['missing_context'] = ['Shared-helper contract is not settled by manifest documentation.']
        rules.validate(case, row, self.contract_hash)
        row['intent_review']['checked_document_ids'].append('fragment-11')
        with self.assertRaisesRegex(ValueError, 'document review'):
            rules.validate(case, row, self.contract_hash)

    def test_quotes_must_exist_in_this_case_and_cover_both_judgments(self):
        case, row = self.pair(0)
        row['evidence_quotes'][0]['quote'] = 'This missing intent is known from another packet.'
        with self.assertRaisesRegex(ValueError, 'exact source excerpt'):
            rules.validate(case, row, self.contract_hash)
        case, row = self.pair(0)
        row['evidence_quotes'][1]['axis'] = 'concern_kind'
        with self.assertRaisesRegex(ValueError, 'both semantic judgments'):
            rules.validate(case, row, self.contract_hash)

    def test_source_code_scope_preserved_but_new_profile_changes_all_task_hashes(self):
        for case, (target, cell) in zip(self.packet['cases'], preparation.SELECTED):
            old, _ = preparation.source_case(target, cell)
            for key in ('target', 'bounded_context', 'evaluation_scope'):
                self.assertEqual(case['state'][key], old['state'][key])
            self.assertNotEqual(case['state_sha256'], old['state_sha256'])
            self.assertNotEqual(case['task_sha256'], old['task_sha256'])

    def test_source_packet_substitution_cannot_be_rehashed_as_new_valid_evidence(self):
        _, source = preparation.source_case('target-01', '03')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replaced = root / source.relative_to(preparation.RESULT)
            replaced.parent.mkdir(parents=True)
            packet = json.loads(source.read_bytes())
            packet['cases'][0]['state']['target']['code'] = 'True'
            replaced.write_bytes(rules.encoded(packet))
            with patch.object(preparation, 'RESULT', root):
                with self.assertRaisesRegex(ValueError, 'frozen preparation'):
                    preparation.source_case('target-01', '03')

    def test_template_is_blank_and_examples_are_not_gold_or_dispatch(self):
        template = json.loads(self.files['template.json'])
        for row in template['annotations']:
            for axis in rules.AXES:
                self.assertIsNone(row[axis])
        receipt = json.loads(self.files['preparation-receipt.json'])
        self.assertFalse(receipt['dispatch_ready'])
        self.assertFalse(receipt['human_gold'])
        self.assertEqual(receipt['provider_requests'], 0)
        self.assertIn('integrator_examples_after_human_guidance', self.examples['status'])
        changed = copy.deepcopy(self.examples)
        changed['annotations'][1] = changed['annotations'][0]
        with self.assertRaisesRegex(ValueError, 'case set'):
            preparation.validate_examples(self.packet, changed, self.contract_hash)

    def test_exclusive_frozen_preparation_replay_and_tamper_rejection(self):
        preparation.verify()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'prepared'
            preparation.write(root)
            preparation.verify(root)
            with self.assertRaises(FileExistsError):
                preparation.write(root)
            (root / 'prompt.txt').write_text('Read prior labels.')
            with self.assertRaisesRegex(ValueError, 'bytes differ: prompt.txt'):
                preparation.verify(root)


if __name__ == '__main__':
    unittest.main()
