import copy
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from prepare_contrastive_pairs import RUN, build, expression_span, verify_source_evidence
from question_grouping import canonical, digest


class ContrastivePreparation(unittest.TestCase):
    def test_saved_artifacts_reproduce_without_network_or_inference(self):
        with patch.object(socket, 'create_connection', side_effect=AssertionError('No network')):
            artifacts = build()
        for name, value in artifacts.items():
            self.assertEqual(json.loads((RUN / name).read_text()), value, name)
        receipt = artifacts['preparation-receipt.json']
        self.assertEqual(receipt['new_inference_requests'], 0)
        self.assertEqual(receipt['reference_status'], 'awaiting_fresh_independent_annotation')
        for name, expected in receipt['artifact_sha256'].items():
            self.assertEqual(digest(canonical(artifacts[name])), expected, name)

    def test_pair_and_withheld_targets_are_exact_and_source_ancestor_is_separate(self):
        artifacts = build()
        states = {c['case_id']: c for c in artifacts['case-packet.json']['cases']}
        mapping = artifacts['source-mapping.json']['cases']
        scenarios = {p['pair_id']: p for p in json.loads((RUN / 'scenarios.json').read_text())['pairs']}
        self.assertEqual(len(states), 12)
        for pair_id, pair in scenarios.items():
            members = [m for m in mapping if m['pair_id'] == pair_id]
            self.assertEqual({m['stratum'] for m in members}, {'mechanics', 'policy', 'withheld'})
            targets = [states[m['case_id']]['state']['target'] for m in members]
            self.assertTrue(all(t == targets[0] for t in targets))
            for m in members:
                state = states[m['case_id']]['state']
                self.assertEqual(states[m['case_id']]['state_sha256'], digest(canonical(state)))
                self.assertEqual(set(state), {'architecture_profile', 'target', 'bounded_context'})
                self.assertNotIn('pair_id', state)
                self.assertNotIn('stratum', state)
                self.assertNotIn('historical_ancestor', state)
                context = state['bounded_context']
                if m['stratum'] == 'withheld':
                    self.assertEqual(context['fragments'], [])
                    self.assertNotIn('scenario_contract', context)
                    self.assertIsNone(m['authored_span'])
                else:
                    scenario = pair[m['stratum']]
                    self.assertEqual(context['scenario_contract'], scenario['contract'])
                    self.assertEqual(m['authored_span'], expression_span(scenario['code'], pair['expression']))
                    raw = scenario['code'].encode()
                    span = m['authored_span']
                    self.assertEqual(raw[span['start_byte']:span['end_byte']], pair['expression'].encode())
                self.assertLessEqual(len(canonical(state)), 16 * 1024)
                self.assertFalse(context['truncated'])

    def test_schedule_preserves_denominator_and_reverses_each_case_provider_order(self):
        schedule = build()['logical-schedule.json']
        rows = schedule['requests']
        self.assertEqual(len(rows), 48)
        self.assertEqual(len({r['request_id'] for r in rows}), 48)
        self.assertEqual(schedule['max_network_attempts'], len(rows) * 3)
        for cid in {r['case_id'] for r in rows}:
            order = {repeat: [r['provider'] for r in rows if r['case_id'] == cid and r['repeat'] == repeat]
                     for repeat in (1, 2)}
            self.assertEqual(order[1], list(reversed(order[2])))
            self.assertEqual(set(order[1]), {'jev-coreinfra', 'luna-decision-coreinfra'})
            self.assertEqual(len({r['state_sha256'] for r in rows if r['case_id'] == cid}), 1)
        self.assertEqual(schedule['status'], 'logical_order_only_not_executable_native_wires')

    def test_author_proposals_never_become_reference_or_blank_annotations(self):
        artifacts = build()
        proposals = artifacts['author-proposals.json']
        self.assertFalse(proposals['independent'])
        self.assertFalse(proposals['prior_labels_transferred'])
        template = artifacts['annotation-template.json']
        self.assertEqual(template['status'], 'blank_not_reference')
        for annotation in template['annotations']:
            self.assertIsNone(annotation['opportunity'])
            self.assertIsNone(annotation['concern_kind'])
            self.assertEqual(annotation['evidence_quotes'], [])
        packet = artifacts['case-packet.json']
        self.assertNotIn('annotations', packet)
        self.assertNotIn('author-proposals', canonical(packet).decode())

    def test_stale_historical_bytes_or_quotes_fail_validation(self):
        sources = json.loads((RUN / 'source-evidence.json').read_text())['sources']
        with self.assertRaisesRegex(ValueError, 'Pinned historical source changed'):
            verify_source_evidence(sources, lambda revision, path: b'drift')
        changed = copy.deepcopy(sources)
        changed[0]['quote'] += '# changed'
        with self.assertRaisesRegex(ValueError, 'quote digest/span mismatch'):
            verify_source_evidence(changed)
        changed = copy.deepcopy(sources)
        changed[0]['path'] = '../escape.py'
        with self.assertRaisesRegex(ValueError, 'Invalid pinned Git source'):
            verify_source_evidence(changed)

    def test_ambiguous_targets_and_changed_budget_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            expression_span('a = x or y\nb = x or y\n', 'x or y')
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            for name in ('scenarios.json', 'source-evidence.json', 'study-plan.json'):
                shutil.copyfile(RUN / name, local / name)
            plan = json.loads((local / 'study-plan.json').read_text())
            plan['design']['planned_logical_requests'] = 64
            (local / 'study-plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'bounded preparation design'):
                build(local)


if __name__ == '__main__':
    unittest.main()
