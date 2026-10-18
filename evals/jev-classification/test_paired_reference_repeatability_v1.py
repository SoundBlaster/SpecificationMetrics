from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from coreinfra_retry_run import decode, sha
from paired_reference_repeatability_v1 import ROOT, agreement, build_plan, freeze, verify
from retrieval_index_v1.source import encoded


class RepeatabilityTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan()
        self.config = 'a' * 64

    def rows(self):
        # Synthetic labels exercise arithmetic, never model output or truth.
        return [dict(task_id=t['task_id'], execution_id='synthetic-' + str(i),
            configuration_sha256=self.config, input_sha256=t['input_sha256'],
            labels=dict(concern_kind='policy', evidence_confidence='supported',
                        ownership='unknown', tool_responsibility='unknown'))
            for i, t in enumerate(self.plan['tasks'])]

    def test_24_new_contexts_and_balanced_interleaving(self):
        self.assertEqual(len(self.plan['tasks']), 24)
        self.assertEqual(len({t['task_id'] for t in self.plan['tasks']}), 24)
        for repeat in range(1, 4):
            tasks = [t for t in self.plan['tasks'] if t['repeat'] == repeat]
            self.assertEqual(len({t['view_id'] for t in tasks}), 8)
            self.assertEqual(sum(t['arm'] == 'baseline' for t in tasks), 4)
            for index in range(0, 8, 2):
                self.assertEqual({t['arm'] for t in tasks[index:index + 2]}, {'baseline', 'retrieval'})
        self.assertFalse(self.plan['dispatch_authorized'])
        self.assertFalse(self.plan['historical_results_used_as_repeats'])
        self.assertEqual(self.plan['configuration_binding']['status'], 'pending_before_dispatch')

    def test_prompts_are_original_blind_inputs_without_labels_or_integrator_plan(self):
        for task in self.plan['tasks']:
            raw = (ROOT / task['prompt_source']).read_bytes()
            self.assertEqual(sha(raw), task['prompt_sha256'])
            self.assertEqual(len(task['input_sha256']), 4)
            self.assertNotIn(b'reference.json', raw)
            self.assertNotIn(b'plan.json', raw)
            self.assertNotIn(b'/raw/', raw)

    def test_empty_or_partial_results_keep_planned_denominators_and_null_status(self):
        for rows in ([], self.rows()[:1], self.rows()[:-1]):
            result = agreement(self.plan, rows, self.config)
            self.assertEqual(result['status'], 'not_evaluable_incomplete')
            self.assertIsNone(result['primary_stable_in_pilot'])
            self.assertEqual(result['planned'], 24)
            self.assertTrue(all(v['planned'] == 24 for v in result['per_axis'].values()))

    def test_full_agreement_is_repeatability_not_truth_or_scoring_authority(self):
        result = agreement(self.plan, self.rows(), self.config)
        self.assertTrue(result['primary_stable_in_pilot'])
        self.assertTrue(all(v == {'agreed': 24, 'compared': 24, 'planned': 24} for v in result['per_axis'].values()))
        self.assertIsNone(result['semantic_accuracy'])
        self.assertFalse(result['paired_quality_scoring_allowed'])
        self.assertFalse(result['source_evidence_verified_by_this_function'])

    def test_primary_disagreement_counts_same_view_pairs_not_cross_view_pairs(self):
        rows = self.rows()
        rows[0]['labels']['concern_kind'] = 'mechanics'
        result = agreement(self.plan, rows, self.config)
        self.assertFalse(result['primary_stable_in_pilot'])
        self.assertEqual(result['per_axis']['concern_kind']['agreed'], 22)
        self.assertEqual(sum(bool(v['differing_axes']) for v in result['per_view']), 1)

    def test_secondary_disagreement_remains_visible_without_changing_primary_criterion(self):
        rows = self.rows()
        rows[0]['labels']['evidence_confidence'] = 'limited'
        result = agreement(self.plan, rows, self.config)
        self.assertTrue(result['primary_stable_in_pilot'])
        self.assertEqual(result['per_axis']['evidence_confidence']['agreed'], 22)
        self.assertEqual(sum(bool(v['differing_axes']) for v in result['per_view']), 1)

    def test_context_config_view_task_and_category_mutations_are_rejected(self):
        for mutation in ('context', 'config', 'input', 'duplicate', 'category', 'unknown_task'):
            with self.subTest(mutation=mutation):
                rows = self.rows()
                if mutation == 'context':
                    rows[1]['execution_id'] = rows[0]['execution_id']
                elif mutation == 'config':
                    rows[0]['configuration_sha256'] = 'b' * 64
                elif mutation == 'input':
                    rows[0]['input_sha256'] = {}
                elif mutation == 'duplicate':
                    rows[1] = rows[0]
                elif mutation == 'unknown_task':
                    rows[0]['task_id'] = 'unplanned'
                else:
                    rows[0]['labels']['concern_kind'] = 'invented'
                with self.assertRaises(ValueError):
                    agreement(self.plan, rows, self.config)

    def test_modified_design_cannot_change_denominators_or_primary_axes(self):
        changed = deepcopy(self.plan)
        changed['measurement']['primary_axes'] = []
        with self.assertRaisesRegex(ValueError, 'frozen design'):
            agreement(changed, [], self.config)

    def test_freeze_round_trip_and_rebound_prompt_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'repeatability'
            freeze(output)
            self.assertEqual(verify(output), self.plan)
            prompt = next((output / 'prompts').iterdir())
            prompt.write_text(prompt.read_text() + '\nRead historical labels too.')
            receipt_path = output / 'receipt.json'
            receipt = decode(receipt_path.read_bytes())
            receipt['file_sha256'][str(prompt.relative_to(output))] = sha(prompt.read_bytes())
            receipt_path.write_text(encoded(receipt))
            with self.assertRaises(ValueError):
                verify(output)


if __name__ == '__main__':
    unittest.main()
