import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from prepare_context_reference_v2 import RUN, V1, build as prepare, encoded, task_digest, verify
from question_grouping import canonical, digest
from validate_context_reference_v2 import AXES, build, compare_rounds, validate


class ContextReferenceV2(unittest.TestCase):
    def read(self, name):
        return json.loads((RUN / name).read_text())

    def test_preparation_preserves_source_states_balances_views_and_keeps_labels_blank(self):
        outputs = verify()
        mapping = outputs['source-mapping.json']['cases']
        self.assertEqual(len(mapping), 18)
        for slot in ('01', '02', '03'):
            packet = outputs[f'annotation-packet-{slot}.json']
            old = json.loads((V1 / f'annotation-packet-{slot}.json').read_text())
            self.assertEqual([c['state'] for c in packet['cases']], [c['state'] for c in old['cases']])
            self.assertNotEqual(packet['questions'], old['questions'])
            members = [m for m in mapping if m['annotation_packet'] == f'annotation-packet-{slot}.json']
            self.assertEqual(len({m['target_id'] for m in members}), 6)
            self.assertEqual(sorted(sum(m['evidence_mode'] == mode for m in members)
                                    for mode in {m['evidence_mode'] for m in members}), [2, 2, 2])
            self.assertTrue(all(r[a] is None for r in outputs[f'annotation-template-{slot}.json']['annotations'] for a in AXES))
            for case in packet['cases']:
                self.assertEqual(case['task_sha256'], task_digest(case, packet))
                self.assertEqual(case['state_sha256'], digest(canonical(case['state'])))

    def test_task_identity_changes_with_questions_instructions_rubric_or_prompt_but_not_state_identity(self):
        packet = self.read('annotation-packet-01.json'); case = packet['cases'][0]
        mutations = [lambda p: p['questions']['opportunity'].update(instructions='different'),
                     lambda p: p.update(instructions='different'),
                     lambda p: p.update(rubric_sha256='different'),
                     lambda p: p.update(annotation_prompt_sha256='different')]
        for mutate in mutations:
            changed = copy.deepcopy(packet); mutate(changed)
            self.assertNotEqual(task_digest(case, changed), case['task_sha256'])
            self.assertEqual(digest(canonical(case['state'])), case['state_sha256'])

    def test_old_or_stale_annotation_rejected_even_when_state_matches(self):
        packet = self.read('annotation-packet-01.json')
        annotation = self.read('round-1/independent-annotations-01.json')
        assignment = self.read('round-1/annotation-assignments.json')['assignments'][0]
        mutations = [lambda a: a['annotations'][0].pop('task_sha256'),
                     lambda a: a['annotations'][0].update(task_sha256='0' * 64),
                     lambda a: a['annotations'][0].update(rubric_sha256='old-rubric')]
        for mutate in mutations:
            changed = copy.deepcopy(annotation); mutate(changed)
            with self.assertRaisesRegex(ValueError, 'task mismatch'):
                validate(packet, changed, assignment)

    def rounds(self):
        return [{r['case_id']: r for slot in ('01', '02', '03')
                 for r in self.read(f'round-{n}/independent-annotations-{slot}.json')['annotations']}
                for n in (1, 2)]

    def test_cross_rubric_or_missing_task_identity_cannot_be_called_same_input_repeat(self):
        rounds = self.rounds(); cid = sorted(rounds[0])[0]
        for field, value in [('task_sha256', None), ('task_sha256', 'f' * 64), ('rubric_sha256', 'old-rubric')]:
            changed = copy.deepcopy(rounds); changed[1][cid][field] = value
            with self.assertRaisesRegex(ValueError, 'task identity'):
                compare_rounds(changed, self.read('study-plan.json'))

    def test_blanket_abstention_cannot_pass_decisive_coverage_guard(self):
        rounds = copy.deepcopy(self.rounds())
        for rows in rounds:
            for row in rows.values():
                row.update(opportunity='needs_review', concern_kind='unknown')
        result = compare_rounds(rounds, self.read('study-plan.json'))
        self.assertTrue(result['H1']['passed'])
        self.assertFalse(result['H2']['passed'])
        self.assertEqual(result['coverage'][0]['joint_decisive'], 0)
        self.assertEqual(result['agreement_when_both_decisive']['opportunity']['total'], 0)
        self.assertEqual(len(result['H2']['abstentions_on_controls']), 40)

    def test_saved_result_replays_offline_without_relabelling_or_semantic_promotion(self):
        with patch('subprocess.check_output', side_effect=AssertionError('offline replay')):
            result = build()
        self.assertEqual(result, self.read('annotation-receipt.json'))
        self.assertEqual(len(result['validations']), 6)
        self.assertEqual(result['new_jev_luna_requests'], 0)
        self.assertEqual(result['within_v2']['label_overrides'], [])
        self.assertFalse(result['within_v2']['reference_frozen_for_provider_scoring'])
        self.assertFalse(result['within_v2']['semantic_correctness_verified'])
        for name, sha in result['input_file_sha256'].items():
            self.assertEqual(sha, digest((RUN / name).read_bytes()))

    def test_preparation_writer_refuses_existing_output_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'rubric.json'; sentinel.write_text('keep')
            completed = subprocess.run([sys.executable, str(RUN.parents[1] / 'prepare_context_reference_v2.py'),
                                        '--run', directory, '--write'], capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn('Refusing to overwrite', completed.stderr)
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])


if __name__ == '__main__':
    unittest.main()
