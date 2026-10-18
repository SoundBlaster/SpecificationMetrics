from pathlib import Path
import shutil
import tempfile
import unittest

from coreinfra_retry_run import decode, sha
from paired_blind_reference_v1 import analyze, seal, verify
from retrieval_index_v1.source import encoded

RUN = Path(__file__).resolve().parent / 'runs/2026-10-18-paired-blind-reference-v1'


class BlindReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name) / 'copy'
        shutil.copytree(RUN, self.run, ignore=shutil.ignore_patterns('analysis.json', 'reference.json', 'receipt.json'))

    def events(self):
        return [decode(line) for line in (self.run / 'dispatch.jsonl').read_bytes().splitlines()]

    def write_events(self, events):
        (self.run / 'dispatch.jsonl').write_text(''.join(encoded(e) + '\n' for e in events))

    def test_actual_eight_annotations_have_four_stable_pairs_and_valid_source_witnesses(self):
        result = analyze(self.run)
        self.assertEqual((result['annotations'], result['fresh_agent_contexts']), (8, 8))
        self.assertEqual((result['comparable_target_pairs'], result['compared_axis_pairs']), (4, 16))
        self.assertEqual((result['differing_target_pairs'], result['differing_axis_pairs']), (0, 0))
        self.assertEqual(result['consistency_review_tasks'], [])
        self.assertEqual(result['hosted_coreinfra_requests'], 0)

    def test_dispatch_cannot_reuse_context_inherit_history_or_change_requested_configuration(self):
        original = self.events()
        for field, value in (('actual_agent', original[0]['actual_agent']), ('fork_turns', 'all'),
                             ('model_selection', 'different')):
            events = self.events() if field == 'actual_agent' else [decode(encoded(e)) for e in original]
            events[1][field] = value
            self.write_events(events)
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze(self.run)
            self.write_events(original)

    def test_retrieval_cannot_precede_baseline_seals_even_with_rebound_timestamps(self):
        events = self.events()
        second_wave = next(e for e in events if e['event'] == 'annotation_dispatched' and e['task_id'] == 'A2')
        events.remove(second_wave)
        events.insert(4, second_wave)
        for event in events:
            event['recorded_at'] = '2026-10-18T00:00:00+00:00'
        self.write_events(events)
        with self.assertRaisesRegex(ValueError, 'before baseline'):
            analyze(self.run)

    def test_prompt_with_extra_author_context_is_rejected_after_digest_rebinding(self):
        path = self.run / 'prompts/A1.txt'
        path.write_text(path.read_text() + '\nAuthor label: policy')
        events = self.events()
        events[0]['prompt_sha256'] = sha(path.read_bytes())
        self.write_events(events)
        with self.assertRaisesRegex(ValueError, 'extra context'):
            analyze(self.run)

    def test_citations_cannot_invent_quotes_spans_or_unsupplied_documents(self):
        path = self.run / 'raw/A1.json'
        original = path.read_bytes()
        original_events = self.events()
        for field, value in (('quote', 'invented witness'), ('start_line', 999),
                             ('document_id', 'hidden.py::unseen')):
            annotation = decode(original)
            annotation['source_locators'][0][field] = value
            path.write_text(encoded(annotation))
            events = [decode(encoded(e)) for e in original_events]
            for event in events:
                if event['task_id'] == 'A1' and event['event'] == 'annotation_sealed':
                    event['annotation_sha256'] = sha(path.read_bytes())
            self.write_events(events)
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze(self.run)
        path.write_bytes(original)
        self.write_events(original_events)

    def test_completion_receipt_replays_comparison_and_reference_without_overwrite(self):
        result = seal(self.run)
        self.assertEqual(verify(self.run), result)
        with self.assertRaises(FileExistsError):
            seal(self.run)
        path = self.run / 'reference.json'
        reference = decode(path.read_bytes())
        reference['views'][0]['labels']['ownership'] = 'unknown'
        path.write_text(encoded(reference))
        receipt_path = self.run / 'receipt.json'
        receipt = decode(receipt_path.read_bytes())
        receipt['file_sha256']['reference.json'] = sha(path.read_bytes())
        receipt_path.write_text(encoded(receipt))
        with self.assertRaisesRegex(ValueError, 'view reference differs'):
            verify(self.run)

    def test_missing_extra_artifacts_and_forged_receipt_authority_are_rejected(self):
        extra = self.run / 'raw/extra.json'
        extra.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            analyze(self.run)
        extra.unlink()
        seal(self.run)
        path = self.run / 'receipt.json'
        original = decode(path.read_bytes())
        for field, value in (('independent_semantic_truth_verified', True),
                             ('hosted_coreinfra_requests', False), ('producer_sha256', {})):
            receipt = decode(encoded(original))
            receipt[field] = value
            path.write_text(encoded(receipt))
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(self.run)


if __name__ == '__main__':
    unittest.main()
