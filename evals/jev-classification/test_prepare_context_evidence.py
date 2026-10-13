import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from prepare_context_evidence import OUTPUTS, RUN, build, collect, verify_sources
from question_grouping import canonical


def synthetic(*, duplicate=False, oversized=False):
    selectors = {'revision': 'a' * 40, 'repository': 'example/source', 'targets': []}
    raw = ('def f(é):\n' + ('    "' + 'x' * 9000 + '"\n' if oversized else '')
           + '    return é and ready\n' + ('    return é and ready\n' if duplicate else '')).encode()
    for n in range(6):
        selectors['targets'].append({'target_id': f'target-{n}', 'path': f'tools/f{n}.py',
                                     'scope': 'f', 'expression': 'é and ready', 'support': []})
    return selectors, raw


class SourceContextPreparation(unittest.TestCase):
    def test_saved_packet_replays_offline_without_git_or_inference(self):
        with patch('prepare_context_evidence.subprocess.check_output', side_effect=AssertionError('Offline must not call Git')):
            artifacts = build()
        for name, value in artifacts.items():
            self.assertEqual(canonical(value), canonical(json.loads((RUN / name).read_text())))
        self.assertEqual(artifacts['preparation-receipt.json']['new_inference_requests'], 0)
        self.assertFalse(artifacts['preparation-receipt.json']['expected_labels_assigned'])

    def test_same_targets_in_three_views_with_blank_independent_template(self):
        artifacts = build(); cases = artifacts['case-packet.json']['cases']
        self.assertEqual(len(cases), 18)
        mapping = artifacts['source-mapping.json']['cases']
        indexed = {c['case_id']: c for c in cases}
        for target in {m['target_id'] for m in mapping}:
            rows = [m for m in mapping if m['target_id'] == target]
            self.assertEqual({m['evidence_mode'] for m in rows},
                             {'expression_only', 'containing_declaration', 'evidence_bundle'})
            self.assertEqual(len({m['expression_sha256'] for m in rows}), 1)
            self.assertEqual(len({indexed[m['case_id']]['state']['target']['code'] for m in rows}), 1)
            for m in rows:
                state = indexed[m['case_id']]['state']
                self.assertNotIn('evidence_mode', state)
                self.assertNotIn('revision', state)
                self.assertNotIn('target_id', state)
                self.assertFalse(state['bounded_context']['truncated'])
                self.assertLessEqual(m['context_code_bytes'], 8192)
                self.assertLessEqual(m['state_bytes'], 16384)
                if m['evidence_mode'] == 'expression_only':
                    self.assertEqual(state['bounded_context']['fragments'], [])
        for row in artifacts['annotation-template.json']['annotations']:
            self.assertIsNone(row['opportunity']); self.assertIsNone(row['concern_kind'])

    def test_utf8_spans_and_complete_expression_selection(self):
        selectors, raw = synthetic()
        sources = collect(selectors, lambda *_: raw)
        verify_sources(sources, lambda *_: raw)
        for target in sources['targets']:
            span = target['span']
            self.assertEqual(raw[span['start_byte']:span['end_byte']], 'é and ready'.encode())
        selectors, raw = synthetic(duplicate=True)
        with self.assertRaisesRegex(ValueError, 'exactly one complete expression'):
            collect(selectors, lambda *_: raw)

    def test_missing_context_and_stale_pinned_source_rejected(self):
        selectors, raw = synthetic(); sources = collect(selectors, lambda *_: raw)
        bad = copy.deepcopy(sources); bad['targets'][0]['bundle'] = []
        with self.assertRaisesRegex(ValueError, 'does not contain'):
            verify_sources(bad)
        bad = copy.deepcopy(sources); bad['targets'][0]['expression_sha256'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'Target hash/span'):
            verify_sources(bad)
        with self.assertRaisesRegex(ValueError, 'Pinned Git source'):
            verify_sources(sources, lambda *_: raw + b'\n')

    def test_selector_mismatch_and_oversized_context_cannot_be_published(self):
        for oversized in (False, True):
            selectors, raw = synthetic(oversized=oversized)
            sources = collect(selectors, lambda *_: raw)
            if not oversized:
                selectors['targets'][0]['scope'] = 'different'
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'selectors.json').write_bytes(canonical(selectors))
                (root / 'source-evidence.json').write_bytes(canonical(sources))
                with self.assertRaisesRegex(ValueError, 'Selectors and source evidence|Context exceeds'):
                    build(root)
                self.assertFalse(any((root / name).exists() for name in OUTPUTS))

    def test_write_refuses_existing_preparation_before_mutating_inputs(self):
        script = str(Path(__file__).with_name('prepare_context_evidence.py'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / OUTPUTS[0]).write_text('sentinel')
            result = subprocess.run([sys.executable, script, '--run', str(root), '--write'],
                                    capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / OUTPUTS[0]).read_text(), 'sentinel')
            self.assertEqual(len(list(root.iterdir())), 1)


if __name__ == '__main__':
    unittest.main()
