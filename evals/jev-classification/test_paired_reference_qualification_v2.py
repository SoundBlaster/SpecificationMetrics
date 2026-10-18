from pathlib import Path
import tempfile
import unittest

from coreinfra_retry_run import decode, sha
from paired_reference_qualification_v2 import configuration_groups, freeze, qualify, verify
from retrieval_index_v1.source import encoded


class ConfigurationQualificationTests(unittest.TestCase):
    def test_historical_group_balances_requested_configuration_not_agent_ids(self):
        result = qualify()
        self.assertEqual(result['execution_contexts'], 8)
        self.assertEqual(len(result['requested_configuration_groups']), 1)
        group = next(iter(result['requested_configuration_groups'].values()))
        self.assertEqual(group['mode_counts'], {'baseline': 4, 'retrieval': 4})
        self.assertTrue(result['requested_configuration_balanced'])
        self.assertFalse(result['identity_only_confound_rejection'])
        self.assertIsNone(group['requested_configuration']['model'])
        self.assertFalse(result['runtime_configuration_verified'])
        self.assertEqual(result['repeatability_status'], 'not_measured_same_view')
        self.assertFalse(result['paired_quality_scoring_allowed'])

    def test_execution_name_does_not_change_group_identity(self):
        rows = [dict(execution_id='one', arm='baseline', requested_configuration={'model': 'm', 'reasoning': 'medium'}),
                dict(execution_id='two', arm='retrieval', requested_configuration={'model': 'm', 'reasoning': 'medium'})]
        first = configuration_groups(rows)
        rows[0]['execution_id'] = 'three'
        second = configuration_groups(rows)
        self.assertEqual(set(first), set(second))
        self.assertTrue(next(iter(second.values()))['equal_mode_exposure'])

    def test_changed_model_or_reasoning_confounded_with_mode_is_not_balanced(self):
        for field in ('model', 'reasoning'):
            rows = [dict(execution_id='one', arm='baseline', requested_configuration={'model': 'm', 'reasoning': 'medium'}),
                    dict(execution_id='two', arm='retrieval', requested_configuration={'model': 'm', 'reasoning': 'medium'})]
            rows[1]['requested_configuration'][field] = 'changed'
            groups = configuration_groups(rows)
            self.assertEqual(len(groups), 2)
            self.assertFalse(any(g['equal_mode_exposure'] for g in groups.values()))

    def test_reused_context_is_rejected_even_for_identical_configuration(self):
        rows = [dict(execution_id='one', arm=arm, requested_configuration={'model': 'm'}) for arm in ('baseline', 'retrieval')]
        with self.assertRaisesRegex(ValueError, 'reused execution'):
            configuration_groups(rows)

    def test_freeze_and_checksum_rebinding_cannot_promote_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'qualification'
            freeze(output)
            self.assertEqual(verify(output), qualify())
            path = output / 'qualification.json'
            value = decode(path.read_bytes())
            value['paired_quality_scoring_allowed'] = True
            path.write_text(encoded(value))
            receipt_path = output / 'receipt.json'
            receipt = decode(receipt_path.read_bytes())
            receipt['file_sha256']['qualification.json'] = sha(path.read_bytes())
            receipt_path.write_text(encoded(receipt))
            with self.assertRaises(ValueError):
                verify(output)


if __name__ == '__main__':
    unittest.main()
