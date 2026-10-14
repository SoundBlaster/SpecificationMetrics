"""Verify scoped offline handoff and genuine pending receipt/review states."""
import json
from pathlib import Path
import tempfile
import unittest

import prepare_manifest_contract_factorial as preparation
import prepare_manifest_contract_handoff as subject
import validate_manifest_contract_factorial as validator


class ManifestContractHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / 'new-delivery'

    def test_delivers_only_assigned_packet_and_blank_template_to_each_context(self):
        receipt = subject.materialize(self.destination)
        outputs = preparation.verify()
        by_slot = {a['slot']: a for a in outputs['dispatch-plan.json']['assignments']}
        self.assertEqual(len(receipt['assignments']), 12)
        for a in receipt['assignments']:
            folder = Path(a['directory'])
            self.assertEqual({p.name for p in folder.iterdir()}, {'packet.json', 'template.json'})
            assigned = by_slot[a['slot']]
            self.assertEqual((folder / 'packet.json').read_bytes(), preparation.encoded(outputs[assigned['packet']]))
            self.assertEqual((folder / 'template.json').read_bytes(), preparation.encoded(outputs[assigned['template']]))
            prompt = (self.destination / a['prompt']).read_text()
            self.assertEqual(prompt, preparation.PROMPT.format(directory=folder))
        self.assertFalse(receipt['annotation_started'])
        self.assertEqual(receipt['provider_requests'], 0)

    def test_unfilled_attempt_cannot_validate_as_a_completed_annotation(self):
        receipt = subject.materialize(self.destination)
        a = receipt['assignments'][0]
        attempt = json.loads((self.destination / a['attempt_receipt']).read_text())
        self.assertIsNone(attempt['agent_task'])
        self.assertIsNone(attempt['context_inheritance'])
        self.assertIsNone(attempt['raw_output_sha256'])
        with self.assertRaises(ValueError):
            validator.validate_attempt(preparation.RUN, attempt, b'{}')

    def test_manual_review_template_is_pending_and_covers_expected_slots(self):
        plan = preparation.verify()['dispatch-plan.json']
        review = subject.review_template(plan)
        self.assertEqual(review['status'], 'blank_manual_review_not_result')
        self.assertEqual({k: len(v['entries']) for k, v in review['criteria'].items()},
                         {'H_contract': 6, 'H_consumers': 6, 'H_target_fidelity': 12})
        for criterion in review['criteria'].values():
            self.assertIsNone(criterion['met'])
            for entry in criterion['entries']:
                self.assertIsNone(entry['criterion_met'])
                self.assertIsNone(entry['raw_output_sha256'])

    def test_refuses_reuse_of_an_existing_delivery_directory(self):
        subject.materialize(self.destination)
        with self.assertRaises(FileExistsError):
            subject.materialize(self.destination)


if __name__ == '__main__':
    unittest.main()
