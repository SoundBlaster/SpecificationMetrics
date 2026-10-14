"""Dispatch identity regression checks; no models, original private logs or network."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import scope_dispatch_provenance as subject

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT / 'runs/2026-10-14-scope-dispatch-provenance-repair-v1'
SOURCE = ROOT / 'runs/2026-10-14-scope-binding-v3-1-results-astra-high'


class DispatchProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'capture'
        shutil.copytree(CAPTURE, self.root)
        self.capture = subject.read(self.root / 'dispatch-capture.json')
        self.record = self.capture['records'][0]

    def edit(self, key, mutate):
        binding = self.record[key]
        path = self.root / binding['path']
        value = subject.read(path)
        mutate(value)
        raw = (json.dumps(value) + '\n').encode()
        path.write_bytes(raw)
        binding['sha256'] = subject.sha(raw)  # Exercise semantics, not merely stale checksums.

    def verify(self):
        return subject.validate_record(self.root, self.record, SOURCE)

    def test_twelve_actual_sessions_and_writer_answers(self):
        results = subject.validate_capture(self.root, SOURCE)
        self.assertEqual(len(results), 12)
        self.assertEqual(len({r['child_session_id'] for r in results}), 12)
        self.assertTrue(all(r['writer_literals_match_raw'] for r in results))
        self.assertFalse(any(r['prompt_plaintext_verified'] for r in results))
        self.assertEqual(sum(r['writer_exit_code_verified'] for r in results), 11)

    def test_slot_shaped_fabricated_identity_is_rejected(self):
        self.edit('spawn_result', lambda e: e['payload'].update(output=json.dumps({'task_name': '/invented/annotator_01'})))
        with self.assertRaisesRegex(ValueError, 'returned tool identity'):
            self.verify()

    def test_result_from_other_spawn_is_rejected(self):
        self.edit('spawn_result', lambda e: e['payload'].update(call_id='other-call'))
        with self.assertRaisesRegex(ValueError, 'Spawn call/result'):
            self.verify()

    def test_inherited_context_is_rejected(self):
        self.edit('spawn_call', lambda e: e['fields']['arguments'].update(fork_turns='all'))
        with self.assertRaisesRegex(ValueError, 'Fresh context'):
            self.verify()

    def test_mismatched_actual_child_session_is_rejected(self):
        self.edit('child_session', lambda e: e['fields'].update(id=self.capture['records'][1]['child_session_id']))
        with self.assertRaisesRegex(ValueError, 'session identity'):
            self.verify()

    def test_wrong_parent_is_rejected(self):
        self.edit('child_session', lambda e: e['fields'].update(parent_thread_id='unrelated-parent'))
        with self.assertRaisesRegex(ValueError, 'Child session/task/parent'):
            self.verify()

    def test_reused_attempt_context_is_rejected(self):
        self.capture['records'].append(deepcopy(self.record))
        (self.root / 'dispatch-capture.json').write_text(json.dumps(self.capture))
        with self.assertRaisesRegex(ValueError, 'Reused dispatch identity'):
            subject.validate_capture(self.root, SOURCE)

    def test_missing_context_does_not_report_completed_capture(self):
        self.capture['records'].pop()
        (self.root / 'dispatch-capture.json').write_text(json.dumps(self.capture))
        with self.assertRaisesRegex(ValueError, 'slot coverage is incomplete'):
            subject.validate_capture(self.root, SOURCE)

    def test_distinct_task_names_cannot_hide_reused_session_uuid(self):
        first_id = self.record['child_session_id']
        self.record = self.capture['records'][1]
        self.record['child_session_id'] = first_id
        self.edit('child_session', lambda e: e['fields'].update(id=first_id))
        for key in ('child_session', 'incoming_task', 'writer_call', 'writer_result'):
            self.record[key]['session_id'] = first_id
        (self.root / 'dispatch-capture.json').write_text(json.dumps(self.capture))
        with self.assertRaisesRegex(ValueError, 'Reused dispatch identity: child_session_id'):
            subject.validate_capture(self.root, SOURCE)

    def test_incoming_message_from_other_dispatch_is_rejected(self):
        self.edit('incoming_task', lambda e: e['fields'].update(message_payload_sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'Incoming task payload'):
            self.verify()

    def test_incoming_wrong_recipient_is_rejected(self):
        self.edit('incoming_task', lambda e: e['fields'].update(recipient='/other/task'))
        with self.assertRaisesRegex(ValueError, 'routing'):
            self.verify()

    def test_cross_session_writer_is_rejected(self):
        self.record['writer_call'] = deepcopy(self.capture['records'][1]['writer_call'])
        with self.assertRaisesRegex(ValueError, 'source session differs|different session'):
            self.verify()

    def test_captured_lifecycle_order_is_checked(self):
        self.record['writer_result']['source_line'] = self.record['writer_call']['source_line'] - 1
        with self.assertRaisesRegex(ValueError, 'lifecycle order'):
            self.verify()

    def test_answer_literals_substitution_is_rejected(self):
        self.edit('writer_call', lambda e: e['payload'].update(
            input=e['payload']['input'].replace('eligible', 'excluded', 1)))
        with self.assertRaisesRegex(ValueError, 'Raw answer differs'):
            self.verify()

    def test_writer_command_is_never_executed(self):
        with self.assertRaises((ValueError, SyntaxError)):
            subject.literal_judgments("rtk proxy python3 - <<'PY'\njudgments=__import__('os').system('false')\nPY")

    def test_writer_nonzero_exit_is_rejected(self):
        def nonzero(event):
            blocks = event['payload']['output']
            value = json.loads(blocks[1]['text'])
            value['exit_code'] = 1
            blocks[1]['text'] = json.dumps(value)
        self.edit('writer_result', nonzero)
        with self.assertRaisesRegex(ValueError, 'successful completion'):
            self.verify()

    def test_missing_capture_does_not_write_retention(self):
        destination = Path(self.temp.name) / 'retained'
        self.record['spawn_result']['path'] = 'missing.json'
        (self.root / 'dispatch-capture.json').write_text(json.dumps(self.capture))
        with self.assertRaises(FileNotFoundError):
            subject.retain(self.root, SOURCE, self.record['slot'], destination)
        self.assertFalse(destination.exists())

    def test_first_retention_uses_blank_receipt_and_actual_returned_identity(self):
        for record in self.capture['records']:
            slot = record['slot']
            record.update(attempt_stage='delivered_unretained',
                          raw_path='delivery/' + slot + '/annotations.json',
                          attempt_receipt_path='delivery/receipts/' + slot + '.json')
        (self.root / 'dispatch-capture.json').write_text(json.dumps(self.capture))
        destination = Path(self.temp.name) / 'retained'
        # Original-path preflight has its own existing tests; this fixture is
        # deliberately relocatable and cannot certify the original machine paths.
        with patch.object(subject.annotations, 'validate_attempt') as original_paths:
            result = subject.retain(self.root, SOURCE, self.record['slot'], destination)
        receipt = subject.read(destination / 'attempt-receipt.json')
        marker = subject.read(destination / 'retention-complete.json')
        self.assertEqual(original_paths.call_count, 1)
        self.assertEqual(receipt['agent_task'], result['agent_task'])
        self.assertEqual(receipt['child_session_id'], result['child_session_id'])
        self.assertEqual(marker['receipt_sha256'], subject.sha((destination / 'attempt-receipt.json').read_bytes()))
        self.assertEqual(receipt['raw_output_sha256'], subject.sha((destination / 'annotations.json').read_bytes()))
        self.assertIn('captured_spawn_result', receipt['identity_source'])
        with self.assertRaises(FileExistsError):
            with patch.object(subject.annotations, 'validate_attempt'):
                subject.retain(self.root, SOURCE, self.record['slot'], destination)


if __name__ == '__main__':
    unittest.main()
