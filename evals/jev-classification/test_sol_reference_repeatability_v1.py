from pathlib import Path
import shutil
import tempfile
import unittest

from coreinfra_retry_run import decode, sha
from retrieval_index_v1.source import encoded
from sol_reference_repeatability_v1 import RUN, analyze, seal, verify


class SolRepeatabilityTests(unittest.TestCase):
    def copy_run(self, directory):
        output = Path(directory) / 'execution'
        shutil.copytree(RUN, output)
        # Work with original inputs, even after the recorded run is sealed.
        for name in ('analysis.json', 'top-line.json', 'receipt.json'):
            (output / name).unlink(missing_ok=True)
        return output

    def rewrite_annotation(self, output, transform):
        path = sorted((output / 'raw').iterdir())[0]
        value = decode(path.read_bytes())
        transform(value)
        path.write_text(encoded(value) + '\n')
        events_path = output / 'dispatch.jsonl'
        events = [decode(line) for line in events_path.read_bytes().splitlines()]
        for event in events:
            if event['event'] == 'annotation_sealed' and event['task_id'] == path.stem:
                event['annotation_sha256'] = sha(path.read_bytes())
        events_path.write_text(''.join(encoded(e) + '\n' for e in events))

    def test_recorded_24_outputs_are_source_checked_and_unanimous_not_accuracy(self):
        result = analyze(RUN)
        self.assertEqual(result['annotations'], 24)
        self.assertTrue(result['diagnostic']['primary_stable_in_pilot'])
        self.assertTrue(all(v == {'agreed': 24, 'compared': 24, 'planned': 24}
                            for v in result['diagnostic']['per_axis'].values()))
        self.assertFalse(result['independent_semantic_truth_verified'])
        self.assertFalse(result['paired_quality_scoring_allowed'])
        self.assertTrue(all(not v['differing_from_historical'] for v in result['historical_comparison']))

    def test_changed_requested_model_or_reasoning_is_rejected(self):
        for key, value in [('requested_model', 'different'), ('reasoning_effort', 'low'), ('model_override_explicit', 1)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                output = self.copy_run(directory)
                path = output / 'configuration.json'
                config = decode(path.read_bytes())
                config[key] = value
                path.write_text(encoded(config) + '\n')
                with self.assertRaisesRegex(ValueError, 'requested configuration'):
                    analyze(output)

    def test_invalid_quote_and_span_fail_after_seal_digest_rebinding(self):
        for key, value in [('quote', 'invented unavailable evidence'), ('start_line', -1), ('document_id', 'not-in-view')]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                output = self.copy_run(directory)
                self.rewrite_annotation(output, lambda a: a['source_locators'][0].update({key: value}))
                with self.assertRaises(ValueError):
                    analyze(output)

    def test_duplicate_context_and_changed_dispatch_binding_fail(self):
        for key, value in [('actual_agent', '/root/old_exposed_context'), ('fork_turns', 'all'),
                           ('reasoning_effort', 'low'), ('prompt_sha256', '0' * 64)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                output = self.copy_run(directory)
                path = output / 'dispatch.jsonl'
                events = [decode(line) for line in path.read_bytes().splitlines()]
                events[0][key] = value
                path.write_text(''.join(encoded(e) + '\n' for e in events))
                with self.assertRaises(ValueError):
                    analyze(output)

    def test_missing_or_extra_annotations_cannot_be_scored_as_complete(self):
        for extra in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                output = self.copy_run(directory)
                path = next((output / 'raw').iterdir())
                if extra:
                    (output / 'raw' / 'unplanned.json').write_bytes(path.read_bytes())
                else:
                    path.unlink()
                with self.assertRaisesRegex(ValueError, 'inventory'):
                    analyze(output)

    def test_injected_primary_disagreement_stays_visible_without_majority_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self.copy_run(directory)
            self.rewrite_annotation(output, lambda a: a.update(concern_kind='mechanics'))
            result = analyze(output)
            self.assertFalse(result['diagnostic']['primary_stable_in_pilot'])
            self.assertEqual(result['diagnostic']['per_axis']['concern_kind']['agreed'], 22)
            self.assertIn('requires_adjudication', result['top_line_status'])
            self.assertTrue(any(v['needs_adjudication'] for v in result['historical_comparison']))
            self.assertFalse(result['paired_quality_scoring_allowed'])

    def test_bad_budget_types_and_registration_time_are_rejected(self):
        for key, value in [('hosted_coreinfra_requests', False), ('started_at', '2026-10-18T12:00:00')]:
            with tempfile.TemporaryDirectory() as directory:
                output = self.copy_run(directory)
                path = output / 'run-start.json'
                start = decode(path.read_bytes())
                start[key] = value
                path.write_text(encoded(start) + '\n')
                with self.assertRaises(ValueError):
                    analyze(output)

    def test_completion_reconstructs_top_line_and_rejects_checksum_rebound_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self.copy_run(directory)
            seal(output)
            self.assertEqual(verify(output), analyze(output))
            path = output / 'top-line.json'
            value = decode(path.read_bytes())
            value['paired_quality_scoring_allowed'] = True
            path.write_text(encoded(value))
            receipt_path = output / 'receipt.json'
            receipt = decode(receipt_path.read_bytes())
            receipt['file_sha256']['top-line.json'] = sha(path.read_bytes())
            receipt_path.write_text(encoded(receipt))
            with self.assertRaisesRegex(ValueError, 'top line'):
                verify(output)


if __name__ == '__main__':
    unittest.main()
