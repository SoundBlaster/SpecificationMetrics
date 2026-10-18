from pathlib import Path
import tempfile
import unittest

import sol_top_line_comparison_v1 as historical
from sol_top_line_comparison_v2 import score


class TruncatedComparisonTests(unittest.TestCase):
    def test_truncated_final_record_keeps_complete_capture_count_without_agreement(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'run'
            historical.prepare_run(run)
            (run / 'responses.jsonl').write_bytes(b'{"captured":"unverified"}\n{"request_id":')
            report = score(run)
            self.assertEqual(report['captured_response_rows'], 1)
            self.assertEqual(report['trailing_response_record']['status'], 'truncated_final_record')
            self.assertFalse(report['transport_evidence']['transport_verified'])
            self.assertEqual(sum(p['compared_axis_slots'] for p in report['providers'].values()), 0)
            self.assertEqual(sum(p['planned_axis_slots'] for p in report['providers'].values()), 64)
            self.assertFalse(report['H1_H2_eligibility'])

    def test_complete_historical_comparison_has_unchanged_provider_results(self):
        run = historical.ROOT / 'runs/2026-10-18-jev-luna-sol-comparison-v1'
        old, new = historical.score(run), score(run)
        self.assertEqual(old['providers'], new['providers'])
        self.assertEqual(new['captured_response_rows'], 16)
        self.assertIsNone(new['trailing_response_record'])

    def test_malformed_interior_is_not_a_truncated_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'run'
            historical.prepare_run(run)
            (run / 'responses.jsonl').write_bytes(b'{bad}\n{"later":true}\n')
            with self.assertRaises(ValueError):
                score(run)
