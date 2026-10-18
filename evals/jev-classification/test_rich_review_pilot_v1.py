from functools import partial
import json
import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch

from coreinfra_transport import post
import rich_review_pilot_v1 as pilot
from rich_review_report_v1 import render
from structured_semantic_review_v1.preparation import CONTRACT, MODEL, encoded

LIVE_RESULT_RECEIPT_SHA256 = '25bc5df1412d62b8daf1ee2d129bc9e3e39161c4816d486e5dea36f905eedcbd'


def response(prepared, *, role='policy', quote=None, rationale='Synthetic offline review, not provider evidence.'):
    fragment = prepared.fragments[0]
    review = dict(contract=CONTRACT, task_sha256=prepared.task_sha256(),
        decision_binding_sha256=prepared.original.expected.fingerprint(),
        labels=dict(concern_kind=role, evidence_confidence='supported', ownership='unknown', tool_responsibility='unknown'),
        citations=[dict(axis='concern_kind', fragment_id='target/source', start_line=fragment.start_line,
                        end_line=fragment.end_line, quote=fragment.code if quote is None else quote)],
        missing_evidence=[], rationale=rationale)
    return encoded(dict(model=MODEL, status='completed', usage=dict(input_tokens=100, output_tokens=50),
        output=[dict(type='message', role='assistant', status='completed',
                     content=[dict(type='output_text', text=encoded(review))])])).encode()


class HTTPResponse:
    chunked = False
    chunk_left = None

    def __init__(self, raw, status):
        self.raw, self.status, self.length = raw, status, len(raw)

    def read(self, count):
        value = self.raw[:count]
        self.raw = self.raw[count:]
        self.length = len(self.raw)
        return value


class Connection:
    def __init__(self, raw, status=200, fail_connect=False):
        self.raw, self.status, self.fail_connect, self.posts = raw, status, fail_connect, 0

    def connect(self):
        if self.fail_connect:
            raise ssl.SSLEOFError('synthetic TLS interruption')

    def request(self, method, path, body, headers):
        if method != 'POST' or path != '/openai/api/v1/responses':
            raise AssertionError('unexpected dispatch')
        self.posts += 1

    def getresponse(self):
        return HTTPResponse(self.raw, self.status)

    def close(self):
        pass


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.preparation, self.run = self.base / 'preparation', self.base / 'run'
        pilot.freeze(self.preparation)
        pilot.stage(self.preparation, self.run)
        self.prepared = pilot.selected()[2]

    def execute(self, raw=None, *, status=200, fail_connect=False):
        connection = Connection(raw if raw is not None else response(self.prepared), status, fail_connect)
        sender = partial(post, connection_factory=lambda timeout: connection)
        with patch.dict(os.environ, {'COREINFRA_API_KEY': 'offline-fixture-key'}):
            receipt = pilot.execute(self.preparation, self.run, live=True, sender=sender)
        return connection, receipt

    def test_dry_run_never_reads_key_dispatches_or_reserves(self):
        with patch.dict(os.environ, {}, clear=True), patch('socket.socket.connect', side_effect=AssertionError('offline')):
            result = pilot.execute(self.preparation, self.run)
        self.assertFalse(result['inference'])
        self.assertFalse((self.preparation / 'dispatch-reservation.json').exists())
        self.assertFalse((self.run / 'attempts.jsonl').exists())

    def test_successful_capture_report_replay_and_preparation_wide_single_spend(self):
        connection, receipt = self.execute()
        self.assertEqual(connection.posts, 1)
        self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts']), (1, 1))
        self.assertEqual(receipt['ambiguous_posts'], 0)
        self.assertTrue(receipt['http_body_received'])
        events = [json.loads(line)['event'] for line in (self.run / 'attempts.jsonl').read_text().splitlines()]
        self.assertEqual(events, ['attempt_started', 'post_may_start', 'attempt_finished'])
        self.assertEqual(pilot.save_report(self.preparation, self.run)['status'], 'resolved_proposal')
        self.assertTrue(pilot.verify_result(self.preparation, self.run)['verified'])
        self.assertIn('not a review of the current main', (self.run / 'report.md').read_text())
        with self.assertRaises(ValueError):
            self.execute()
        # A different staged directory cannot spend the same prepared request again.
        other = self.base / 'other'
        with self.assertRaisesRegex(ValueError, 'already dispatched'):
            pilot.stage(self.preparation, other)
        self.assertFalse(other.exists())
        for path in self.run.iterdir():
            if path.is_file():
                self.assertNotIn(b'offline-fixture-key', path.read_bytes())

    def test_lease_prevents_dispatch_through_a_second_previously_staged_run(self):
        other = self.base / 'other'
        pilot.stage(self.preparation, other)
        self.execute()
        with patch.dict(os.environ, {'COREINFRA_API_KEY': 'offline-fixture-key'}), \
                self.assertRaises(FileExistsError), patch('socket.socket.connect', side_effect=AssertionError('no second request')):
            pilot.execute(self.preparation, other, live=True)

    def test_wrong_quote_is_preserved_as_needs_review(self):
        self.execute(response(self.prepared, quote='not a source quote'))
        result = pilot.analyze(self.preparation, self.run)
        self.assertEqual(result['inspection']['status'], 'needs_review')
        text = render(result)
        self.assertIn('invalid_citations', text)
        self.assertIn('invalid quote/span', text)
        self.assertIn('not a source quote', text)
        self.assertFalse(result['inspection']['source_locators_verified'])

    def test_tls_failure_has_no_post_no_retry_and_incomplete_report(self):
        connection, receipt = self.execute(fail_connect=True)
        self.assertEqual(connection.posts, 0)
        self.assertEqual(receipt['network_attempts'], 1)
        self.assertEqual(receipt['potentially_billable_posts'], 0)
        self.assertFalse(receipt['http_body_received'])
        report = pilot.analyze(self.preparation, self.run)
        self.assertEqual(report['inspection']['status'], 'analysis_incomplete')
        self.assertIn('unavailable', render(report))

    def test_http_errors_and_credential_reflection_are_not_persisted_as_response_bodies(self):
        self.execute(b'offline-fixture-key', status=400)
        row = json.loads((self.run / 'response.json').read_text())
        self.assertEqual(row['status'], 'http_error')
        self.assertIsNone(row['raw_body_base64'])
        self.assertEqual(pilot.analyze(self.preparation, self.run)['inspection']['status'], 'analysis_incomplete')

    def test_credential_reflected_in_http_200_is_dropped(self):
        self.execute(b'{"secret":"offline-fixture-key"}')
        row = json.loads((self.run / 'response.json').read_text())
        self.assertEqual(row['status'], 'credential_reflection')
        self.assertIsNone(row['raw_body_base64'])
        self.assertNotIn('offline-fixture-key', (self.run / 'response.json').read_text())

    def test_modified_manifest_prevents_dispatch_and_modified_result_fails_replay(self):
        self.execute()
        pilot.save_report(self.preparation, self.run)
        with (self.run / 'report.md').open('a') as output:
            output.write('edited')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            pilot.verify_result(self.preparation, self.run)
        with (self.preparation / 'manifest.json').open('a') as output:
            output.write(' ')
        with self.assertRaisesRegex(ValueError, 'frozen'):
            pilot.execute(self.preparation, self.run, live=True)

    def test_unexpected_failure_has_a_receipt_and_never_retries(self):
        calls = []

        def broken(*args, **kwargs):
            calls.append(1)
            raise RuntimeError('Do not store this exception text')

        with patch.dict(os.environ, {'COREINFRA_API_KEY': 'offline-fixture-key'}):
            receipt = pilot.execute(self.preparation, self.run, live=True, sender=broken)
        self.assertEqual(calls, [1])
        self.assertEqual(receipt['stop_reason'], 'RuntimeError')
        self.assertFalse(receipt['attempt_ledger_complete'])
        self.assertEqual(pilot.analyze(self.preparation, self.run)['inspection']['status'], 'analysis_incomplete')
        self.assertNotIn('Do not store', (self.run / 'transport-receipt.json').read_text())

    def test_model_rationale_is_fenced_as_data_instead_of_active_markdown(self):
        rationale = '```\n<script>alert(1)</script>\n[link](javascript:alert(1))\n```'
        self.execute(response(self.prepared, rationale=rationale))
        text = render(pilot.analyze(self.preparation, self.run))
        self.assertIn('````\n' + rationale + '\n````', text)


class SavedCaptureTests(unittest.TestCase):
    @unittest.skipIf(LIVE_RESULT_RECEIPT_SHA256 is None, 'authorized capture is not sealed yet')
    def test_saved_live_result_replays_without_inference(self):
        from structured_semantic_review_v1.preparation import sha
        self.assertEqual(sha((pilot.RUN / 'result-receipt.json').read_bytes()), LIVE_RESULT_RECEIPT_SHA256)
        with patch('socket.socket.connect', side_effect=AssertionError('offline replay only')):
            verified = pilot.verify_result(pilot.PREPARATION, pilot.RUN)
        self.assertTrue(verified['verified'])
        self.assertEqual(verified['additional_hosted_requests'], 0)


def load_tests(loader, tests, pattern):
    if pattern is None:
        tests.addTests(loader.loadTestsFromName('test_rich_review_pilot_v2'))
    return tests


if __name__ == '__main__':
    unittest.main()
