"""Prevent one-mode annotator assignment and direct focal evidence leakage."""
from collections import Counter
import json
import unittest

import prepare_manifest_contract_balanced as subject


class BalancedManifestPreparationTests(unittest.TestCase):
    def setUp(self):
        self.outputs = subject.verify()
        self.plan = self.outputs['dispatch-plan.json']

    def test_every_context_has_all_four_modes_and_one_view_per_target(self):
        for a in self.plan['assignments']:
            self.assertEqual({c['cell'] for c in a['cases']}, {'01', '02', '03', '04'})
            self.assertEqual({c['case_id'] for c in a['cases']}, {'target-01', 'target-02', 'target-03', 'target-04'})
            self.assertEqual(len(self.outputs[a['packet']]['cases']), 4)

    def test_target_cell_and_both_position_marginals_are_balanced(self):
        cases = [c for a in self.plan['assignments'] for c in a['cases']]
        for fields in (('case_id', 'cell'), ('case_id', 'position'), ('cell', 'position')):
            counts = Counter(tuple(c[k] for k in fields) for c in cases)
            self.assertEqual(len(counts), 16)
            self.assertEqual(set(counts.values()), {3})

    def test_case_task_bytes_repeat_three_times_but_packet_order_can_differ(self):
        identities = Counter(c['task_sha256'] for a in self.plan['assignments']
                             for c in self.outputs[a['packet']]['cases'])
        self.assertEqual(len(identities), 16)
        self.assertEqual(set(identities.values()), {3})
        by_task = {}
        for a in self.plan['assignments']:
            for c in self.outputs[a['packet']]['cases']:
                raw = subject.encoded(c)
                self.assertEqual(by_task.setdefault(c['task_sha256'], raw), raw)

    def test_controls_do_not_reveal_focal_helper_or_manifest_contract(self):
        catalog = json.loads((subject.EVIDENCE / 'evidence-bundles.json').read_text())
        for target in catalog['targets'][1:]:
            evidence = '\n'.join(f.get('code', f.get('text', '')) for bundle in
                                 ('base_fragments', 'document_fragments', 'consumer_fragments') for f in target[bundle])
            for marker in ('_safe_path', 'static_artifact_incremental_stage', 'staging_prefix',
                           'Path traversal and local digest mismatches fail closed.'):
                self.assertNotIn(marker, evidence)

    def test_v1_is_preserved_and_supersession_claims_no_model_failure(self):
        subject.legacy.verify()
        supersession = self.outputs['supersession.json']
        self.assertFalse(supersession['prior_annotation_started'])
        self.assertEqual(supersession['status'], 'v1_superseded_before_dispatch_not_failed_model_run')
        self.assertEqual(self.plan['case_annotations_planned'], 48)


if __name__ == '__main__':
    unittest.main()
