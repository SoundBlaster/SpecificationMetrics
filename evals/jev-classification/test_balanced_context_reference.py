import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from prepare_balanced_context_reference import MODES, RUN, SOURCE, build
from question_grouping import canonical
from validate_context_annotations import build as annotation_report
from compare_context_references import compare


class BalancedContextReference(unittest.TestCase):
    def test_saved_delivery_replays_frozen_source_states(self):
        outputs = build()
        for name, value in outputs.items():
            self.assertEqual(canonical(json.loads((RUN / name).read_text())), canonical(value))
        before = json.loads((SOURCE / 'case-packet.json').read_text())
        cases = {c['case_id']: c for c in before['cases']}
        delivered = [c for n, p in outputs.items() if n.startswith('annotation-packet') for c in p['cases']]
        self.assertEqual(len(delivered), 18)
        self.assertEqual({c['case_id']: c for c in delivered}, cases)

    def test_modes_are_balanced_without_showing_two_views_of_one_target(self):
        outputs = build()
        mapping = outputs['source-mapping.json']['cases']
        for slot in (1, 2, 3):
            members = [m for m in mapping if m['annotation_packet'] == f'annotation-packet-{slot:02d}.json']
            self.assertEqual(len(members), 6)
            self.assertEqual(len({m['target_id'] for m in members}), 6)
            self.assertEqual({mode: sum(m['evidence_mode'] == mode for m in members) for mode in MODES},
                             dict.fromkeys(MODES, 2))
            blank = outputs[f'annotation-template-{slot:02d}.json']['annotations']
            self.assertEqual({r['case_id'] for r in blank}, {m['case_id'] for m in members})
            self.assertTrue(all(r['opportunity'] is None and r['concern_kind'] is None for r in blank))

    def test_original_delivery_reproduces_the_mode_annotator_confound(self):
        mapping = json.loads((SOURCE / 'source-mapping.json').read_text())['cases']
        for slot in (1, 2, 3):
            members = [m for m in mapping if m['annotation_packet'] == f'annotation-packet-{slot:02d}.json']
            counts = {mode: sum(m['evidence_mode'] == mode for m in members) for mode in MODES}
            self.assertEqual(sorted(counts.values()), [0, 0, 6])
            self.assertNotEqual(counts, dict.fromkeys(MODES, 2))

    def test_write_refuses_existing_delivery_before_mutating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'annotation-template-03.json'
            sentinel.write_text('keep')
            result = subprocess.run([sys.executable, str(RUN.parents[1] / 'prepare_balanced_context_reference.py'),
                                     '--run', directory, '--write'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Refusing to overwrite', result.stderr)
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])

    def test_balanced_annotation_receipt_replays_without_semantic_or_causal_claim(self):
        receipt = json.loads((RUN / 'annotation-receipt.json').read_text())
        self.assertEqual(receipt, annotation_report(RUN))
        self.assertFalse(receipt['reference_frozen_for_provider_scoring'])
        self.assertEqual(receipt['comparison']['label_overrides'], [])
        self.assertEqual(receipt['comparison']['jev_luna_requests'], 0)
        preparation = build()['balanced-preparation-receipt.json']
        self.assertFalse(preparation['causal_inference_claimed'])

    def test_same_input_comparison_replays_raw_labels_without_voting(self):
        report = json.loads((RUN / 'same-input-comparison.json').read_text())
        self.assertEqual(report, compare())
        self.assertEqual(len(report['cases']), 18)
        self.assertEqual(report['label_overrides'], [])
        self.assertTrue(all(report['agreement'][axis]['total'] == 18 for axis in ('opportunity', 'concern_kind')))


if __name__ == '__main__':
    unittest.main()
