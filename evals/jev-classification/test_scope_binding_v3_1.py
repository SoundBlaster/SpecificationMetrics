"""Prevent contradictory permitted-input lists and stale scope identities."""
import tempfile
from pathlib import Path
import unittest

import prepare_scope_binding_v3_1 as subject
from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest


class ScopeContractCorrectionTests(unittest.TestCase):
    def test_final_composed_prompt_permits_scope_without_inherited_exhaustive_list(self):
        prompt = subject.verify()['annotation-prompt.txt'].decode()
        allowed = prompt.split('The permitted semantic inputs are ONLY ', 1)[1].split('. ', 1)[0]
        for name in ('state.target', 'state.bounded_context', 'state.architecture_profile', 'state.evaluation_scope'):
            self.assertIn(name, allowed)
        self.assertNotIn("using only each case's own target, bounded_context, architecture_profile", prompt)
        self.assertEqual(prompt.count('permitted semantic inputs'), 1)
        self.assertIn('scope_unit/scope_binding_sha256', prompt)

    def test_states_preserved_but_tasks_and_explicit_scope_acknowledgments_versioned(self):
        outputs = subject.verify()
        old = subject.historical.verify()
        for assignment in outputs['dispatch-plan.json']['assignments']:
            packet = outputs[assignment['packet']]
            for case, previous, blank in zip(packet['cases'], old[assignment['packet']]['cases'],
                                             outputs[assignment['template']]['annotations']):
                self.assertEqual(case['state'], previous['state'])
                self.assertNotEqual(case['task_sha256'], previous['task_sha256'])
                self.assertEqual(case['task_sha256'], task_digest(case, packet))
                self.assertEqual(blank['scope_unit'], case['state']['evaluation_scope']['unit'])
                self.assertEqual(blank['scope_binding_sha256'], digest(canonical(case['state']['evaluation_scope'])))
                self.assertIsNone(blank['opportunity'])
        self.assertFalse(outputs['supersession.json']['prior_annotation_started'])

    def test_exclusive_write_and_replay_reject_prompt_drift(self):
        with tempfile.TemporaryDirectory() as parent:
            run = Path(parent) / 'new'
            subject.write(run)
            subject.verify(run)
            with self.assertRaises(FileExistsError):
                subject.write(run)
            (run / 'annotation-prompt.txt').write_text('Ignore scope.')
            with self.assertRaisesRegex(ValueError, 'Frozen scope v3.1'):
                subject.verify(run)


if __name__ == '__main__':
    unittest.main()
