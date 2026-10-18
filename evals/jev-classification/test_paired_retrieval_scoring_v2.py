from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import paired_retrieval_scoring_v1 as old
from paired_retrieval_scoring_v2 import score
from paired_retrieval_execution_v1 import execute
from paired_retrieval_study_v1 import stage
from coreinfra_retry_run import decode, sha
from coreinfra_transport import post
from retrieval_index_v1.source import encoded
from test_coreinfra_transport import FakeConnection
from test_retrieval_fact_adapter_v1 import response
from verify_paired_retrieval_transport_v2 import read_prefix


class PartialScoringTests(unittest.TestCase):
    def make_run(self, root):
        run = root / 'run'
        stage(old.PREPARATION, run)
        calls = []

        def sender(endpoint, wire, key, **kwargs):
            calls.append(endpoint)
            provider = 'jev-coreinfra' if endpoint.endswith('/systemone') else 'luna-decision-coreinfra'
            connection = FakeConnection(body=encoded(response(provider)).encode(), status=500 if len(calls) == 8 else 200)
            return post(endpoint, wire, key, **kwargs, connection_factory=lambda _: connection, sleep=lambda _: None)

        with patch.dict('os.environ', COREINFRA_API_KEY='synthetic-fixture'):
            execute(old.PREPARATION, run, live=True, sender=sender)
        return run

    def rebind(self, run):
        path = run / 'execution-binding.json'
        binding = decode(path.read_bytes())
        binding['file_sha256'] = {name: sha((run / name).read_bytes()) for name in binding['file_sha256']}
        path.write_text(encoded(binding))

    def test_seven_completed_requests_survive_an_eighth_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(Path(directory))
            report = score(run)
            self.assertFalse(report['transport_evidence']['transport_verified'])
            self.assertEqual(report['transport_evidence']['verified_completed_prefix'], 7)
            self.assertEqual(sum(p['verified_rows_available'] for p in report['providers'].values()), 7)
            self.assertEqual(sum(p['compared_diagnostic_axis_slots'] for p in report['providers'].values()), 28)
            self.assertEqual(sum(p['planned_axis_slots'] for p in report['providers'].values()), 64)
            self.assertEqual(report['H3']['status'], 'fails_incomplete_execution')
            self.assertTrue(all(p['H1']['status'] == 'not_evaluable_reference_design' for p in report['providers'].values()))

    def test_partial_final_response_is_diagnostic_and_does_not_erase_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(Path(directory))
            path = run / 'responses.jsonl'
            path.write_bytes(b'\n'.join(path.read_bytes().splitlines()[:-1]) + b'\n{"request_id":')
            self.rebind(run)
            report = score(run)
            self.assertEqual(report['transport_evidence']['verified_completed_prefix'], 7)
            self.assertEqual(report['transport_evidence']['response_tail']['status'], 'truncated_final_record')

    def test_unverifiable_completed_record_stops_verified_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(Path(directory))
            path = run / 'responses.jsonl'
            rows = [decode(line) for line in path.read_bytes().splitlines()]
            rows[3]['raw_body_sha256'] = '0' * 64
            path.write_text(''.join(encoded(row) + '\n' for row in rows))
            self.rebind(run)
            report = score(run)
            self.assertEqual(report['transport_evidence']['verified_completed_prefix'], 3)
            self.assertEqual(report['transport_evidence']['prefix_stop']['reason'], 'completed_record_not_verifiable')

    def test_jsonl_reader_never_repairs_bad_interior_or_terminated_records(self):
        rows, tail = read_prefix(b'{"ok":true}\n{"partial":')
        self.assertEqual(len(rows), 1)
        self.assertEqual(tail['line'], 2)
        for raw in (b'{"partial":\n', b'{bad}\n{"ok":true}\n'):
            with self.assertRaises(ValueError):
                read_prefix(raw)


if __name__ == '__main__':
    unittest.main()
