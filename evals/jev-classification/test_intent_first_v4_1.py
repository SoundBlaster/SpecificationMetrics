"""Reproduce legacy contradictions, then require consistent v4.1 responses."""
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest

import intent_first_contract_v4_1 as rules
import prepare_intent_first_v4_1 as preparation


class IntentFirstRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = preparation.build()
        cls.packet = json.loads(cls.files['packet.json'])
        cls.rows = json.loads(cls.files['integrator-examples.json'])['annotations']
        cls.hash = rules.digest(cls.files['contract.json'])

    def test_original_gate_and_unknown_path_failures_are_preserved_and_rejected_in_new_version(self):
        legacy = preparation.previous
        old = legacy.verify()
        old_packet = json.loads(old['packet.json'])
        old_rows = json.loads(old['integrator-examples.json'])['annotations']
        old_hash = rules.digest(old['contract.json'])
        for index in (0, 1):
            with self.subTest(index=index):
                row = {**old_rows[index], 'recommendation': 'keep_procedural', 'basis': 'mechanics'}
                self.assertEqual(legacy.rules.validate(old_packet['cases'][index], row, old_hash)['status'],
                                 'contract_valid_not_semantically_adjudicated')
                changed = {**self.rows[index], 'recommendation': 'keep_procedural', 'basis': 'mechanics'}
                with self.assertRaisesRegex(ValueError, 'keep_procedural requires mechanics with supported evidence'):
                    rules.validate(self.packet['cases'][index], changed, self.hash)

    def test_all_role_support_combinations_allow_procedural_only_for_supported_mechanics(self):
        for role, support in itertools.product(('policy', 'variant_behavior', 'mechanics', 'unknown'),
                                               ('supported', 'limited', 'insufficient')):
            with self.subTest(role=role, support=support):
                row = copy.deepcopy(self.rows[0])
                row.update(concern_kind=role, evidence_confidence=support,
                           recommendation='keep_procedural', basis='mechanics')
                if (role, support) == ('mechanics', 'supported'):
                    rules.Annotation.model_validate(row)
                else:
                    with self.assertRaises(ValueError):
                        rules.Annotation.model_validate(row)

    def test_affirmative_newline_mechanics_can_be_procedural_and_existing_rules_still_reuse(self):
        row = {**self.rows[3], 'recommendation': 'keep_procedural', 'basis': 'mechanics'}
        rules.validate(self.packet['cases'][3], row, self.hash)
        result = rules.validate_response(self.packet, {'annotations': self.rows}, self.hash)
        self.assertEqual(len(result), 4)
        self.assertTrue(all(not r['semantic_correctness_verified'] for r in result))
        self.assertEqual(self.rows[2]['recommendation'], 'reuse_specification')
        self.assertEqual(self.rows[3]['recommendation'], 'use_tool_rules')

    def test_supported_domain_rule_keeps_role_confidence_despite_implementation_questions(self):
        row = copy.deepcopy(self.rows[1])
        row['uncertainties'] = ['Implementation decomposition remains undecided.']
        rules.validate(self.packet['cases'][1], row, self.hash)
        self.assertEqual((row['concern_kind'], row['evidence_confidence'], row['basis']),
                         ('policy', 'supported', 'domain_contract'))
        row['basis'] = 'formalization_preference'
        with self.assertRaisesRegex(ValueError, 'retain role uncertainty'):
            rules.validate(self.packet['cases'][1], row, self.hash)

    def test_schema_exports_the_same_strict_response_envelope_as_template_and_consumer(self):
        schema = json.loads(self.files['contract.json'])['output_schema']
        self.assertEqual(schema['required'], ['annotations'])
        self.assertEqual(set(schema['properties']), {'annotations'})
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['annotations']['type'], 'array')
        annotation = schema['$defs']['Annotation']
        self.assertEqual(annotation['properties']['contract_id']['const'], rules.CONTRACT_ID)
        template = json.loads(self.files['template.json'])
        self.assertEqual(set(template), set(schema['properties']))
        for blank, filled in zip(template['annotations'], self.rows):
            for axis in ('concern_kind', 'evidence_confidence', 'recommendation'):
                self.assertIsNone(blank[axis])
            blank.update(filled)
        rules.Response.model_validate(template)
        rules.validate_response(self.packet, template, self.hash)

    def test_bare_row_extra_envelope_metadata_empty_or_wrong_case_sets_are_rejected(self):
        for answer in (self.rows[0], {'annotations': self.rows, 'status': 'ready'},
                       {'annotations': []}, {'annotations': self.rows[:1]},
                       {'annotations': [self.rows[0]] * 4}):
            with self.subTest(answer_keys=list(answer)):
                with self.assertRaises(ValueError):
                    rules.validate_response(self.packet, answer, self.hash)

    def test_old_contract_and_task_identities_cannot_be_reused(self):
        old = preparation.previous.verify()
        packet = json.loads(old['packet.json'])
        for case, prior in zip(self.packet['cases'], packet['cases']):
            self.assertEqual(case['state'], prior['state'])
            self.assertEqual(case['state_sha256'], prior['state_sha256'])
            self.assertEqual(case['scope_binding_sha256'], prior['scope_binding_sha256'])
            self.assertNotEqual(case['task_sha256'], prior['task_sha256'])
        row = {**self.rows[0], 'task_sha256': packet['cases'][0]['task_sha256']}
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            rules.validate(self.packet['cases'][0], row, self.hash)
        with self.assertRaisesRegex(ValueError, 'packet contract identity'):
            rules.validate_response(packet, {'annotations': self.rows}, self.hash)

    def test_source_quote_and_case_substitution_are_rejected_by_new_validator(self):
        row = copy.deepcopy(self.rows[1])
        row['evidence_quotes'][0]['quote'] = 'foreign evidence'
        with self.assertRaisesRegex(ValueError, 'exact source excerpt'):
            rules.validate(self.packet['cases'][1], row, self.hash)
        case = copy.deepcopy(self.packet['cases'][0])
        case['state']['target']['code'] = 'True'
        with self.assertRaisesRegex(ValueError, 'case state digest'):
            rules.validate(case, self.rows[0], self.hash)

    def test_document_acknowledgments_and_scope_identity_still_require_exact_matches(self):
        legacy = preparation.previous
        old, _ = legacy.source_case('target-01', '04')
        case = legacy.make_case(old, '04', self.hash)
        row = legacy.example(case, self.hash, 0)
        row.update(contract_id=rules.CONTRACT_ID, concern_kind='policy', evidence_confidence='supported',
                   basis='domain_contract', uncertainties=[],
                   intent_review={'checked_document_ids': ['fragment-11', 'fragment-12'], 'missing_context': []},
                   rationales={axis: 'The selected manifest binding is constrained by the supplied publication integrity proposal.'
                               for axis in legacy.rules.AXES})
        rules.validate(case, row, self.hash)
        row['intent_review']['checked_document_ids'] = ['fragment-11']
        with self.assertRaisesRegex(ValueError, 'document review'):
            rules.validate(case, row, self.hash)
        row['intent_review']['checked_document_ids'] = ['fragment-11', 'fragment-12']
        row['scope_unit'] = 'shared_definition'
        with self.assertRaisesRegex(ValueError, 'contract/scope identity'):
            rules.validate(case, row, self.hash)

    def test_frozen_old_and_new_replay_without_overwriting_either(self):
        preparation.previous.verify()
        preparation.verify()
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'new'
            preparation.write(run)
            preparation.verify(run)
            with self.assertRaises(FileExistsError):
                preparation.write(run)
            (run / 'contract.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'bytes differ: contract.json'):
                preparation.verify(run)


if __name__ == '__main__':
    unittest.main()
