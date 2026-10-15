"""Prevent criterion drift and success inferred from incomplete evidence; offline."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import verify_results as replay


class PreregisteredResultsTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((Path(__file__).parent / 'native-report.json').read_text())['rows']

    def test_improved_action_counts_do_not_override_failed_echo(self):
        result = replay.compare(self.rows)
        for provider, counts in result.items():
            self.assertEqual(counts['H1'], 'not_supported_premise_echo_failed')
            self.assertIsNone(counts['counts']['baseline']['premise_echo_matches'])
        self.assertEqual(result['luna-decision-coreinfra']['H2'], 'supported_in_single_pair')
        self.assertEqual(result['jev-coreinfra']['H2'], 'no_incremental_evidence_already_reused')

    def test_missing_or_native_invalid_response_does_not_confirm_H1(self):
        for invalid in (False, True):
            changed = copy.deepcopy(self.rows)
            if invalid:
                changed[0]['native_status'] = 'invalid'
            else:
                changed.pop(0)
            self.assertEqual(replay.compare(changed)['jev-coreinfra']['H1'], 'incomplete_not_evaluable')

    def test_H2_does_not_ignore_premise_failure(self):
        changed = copy.deepcopy(self.rows)
        row = next(r for r in changed if r['provider'] == 'luna-decision-coreinfra'
                   and r['arm'] == 'ownership_witness')
        row['premise_echo_matches'] = False
        self.assertEqual(replay.compare(changed)['luna-decision-coreinfra']['H2'],
                         'incomplete_or_premise_failure_not_evaluable')

    def test_local_ledger_tampering_is_rejected(self):
        original = replay.RUN
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for name in ('manifest.json', 'responses.jsonl', 'attempts.jsonl', 'receipt.json',
                         'authorization.json', 'native-report.json'):
                (target / name).write_bytes((original / name).read_bytes())
            ledger = [json.loads(line) for line in (target / 'attempts.jsonl').read_text().splitlines()]
            ledger[2]['wire_sha256'] = '0' * 64
            (target / 'attempts.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in ledger))
            try:
                replay.RUN = target
                with self.assertRaisesRegex(ValueError, 'event identity differs'):
                    replay.analyze()
            finally:
                replay.RUN = original


if __name__ == '__main__':
    unittest.main()
