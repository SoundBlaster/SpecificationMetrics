from pathlib import Path
import tempfile
import unittest

from paired_reference_repeatability_v2 import ROOT, build_plan, freeze, prompt, verify
from coreinfra_retry_run import decode, sha
from retrieval_index_v1.source import encoded


class PortableRepeatabilityTests(unittest.TestCase):
    def test_first_arm_flips_for_each_case_independently_of_shuffle(self):
        plan = build_plan()
        self.assertEqual(len(plan['tasks']), 24)
        cases = sorted({t['case_id'] for t in plan['tasks']})
        for case in cases:
            first = [next(t['arm'] for t in plan['tasks'] if t['repeat'] == repeat and t['case_id'] == case)
                     for repeat in (1, 2, 3)]
            self.assertNotEqual(first[0], first[1])
            self.assertNotEqual(first[1], first[2])
        for repeat in (1, 2, 3):
            tasks = [t for t in plan['tasks'] if t['repeat'] == repeat]
            self.assertEqual(sum(t['arm'] == 'baseline' for t in tasks[::2]), 2)
        self.assertFalse(plan['dispatch_authorized'])
        self.assertFalse(plan['historical_run_reinterpreted'])

    def test_prompt_is_byte_stable_and_paths_work_in_a_relocated_checkout(self):
        task = build_plan()['tasks'][0]
        raw = prompt(task)
        self.assertEqual(raw, prompt(decode(encoded(task))))
        self.assertNotIn('/Users/', raw)
        self.assertEqual(sha(raw.encode()), task['prompt_sha256'])
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / 'different-checkout'
            for name, digest in task['input_sha256'].items():
                relative = Path('evals/jev-classification') / name
                target = checkout / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
                self.assertEqual(sha(target.read_bytes()), digest)
            for path in raw.splitlines()[1:-1]:
                self.assertFalse(Path(path).is_absolute())
                self.assertTrue((checkout / path).is_file())

    def test_freeze_verifies_generated_prompt_not_historical_absolute_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'plan'
            plan = freeze(output)
            self.assertEqual(verify(output), plan)
            path = output / plan['tasks'][0]['prompt_source']
            path.write_text(path.read_text().replace('evals/', '/machine-specific/evals/'))
            receipt = decode((output / 'receipt.json').read_bytes())
            receipt['file_sha256'][str(path.relative_to(output))] = sha(path.read_bytes())
            (output / 'receipt.json').write_text(encoded(receipt))
            with self.assertRaises(ValueError):
                verify(output)
