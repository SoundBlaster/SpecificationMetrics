import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prepare_bdd_steps_factorial import CELLS, RUN, V2_RUN, build, verify
from question_grouping import canonical, digest


class BDDStepsFactorialPreparation(unittest.TestCase):
    def test_saved_packets_replay_and_receipt_is_bound(self):
        outputs = verify()
        receipt = outputs['preparation-receipt.json']
        self.assertEqual(receipt['status'], 'bdd_factorial_packet_prepared_not_dispatched')
        self.assertEqual(receipt['fresh_contexts_planned'], 12)
        self.assertEqual(receipt['provider_requests'], 0)
        for name, sha in receipt['artifact_file_sha256'].items():
            self.assertEqual(sha, digest((RUN / name).read_bytes()))
        for name, sha in receipt['source_file_sha256'].items():
            source = V2_RUN / Path(name).name
            self.assertEqual(sha, digest(source.read_bytes()))

    def test_four_cells_change_only_the_registered_evidence_groups(self):
        outputs = build()
        mapping = outputs['source-mapping.json']
        self.assertEqual(len(mapping['cells']), 4)
        self.assertEqual({(c['contract_evidence_present'], c['implementation_link_evidence_present'])
                          for c in mapping['cells']}, {(False, False), (True, False), (False, True), (True, True)})
        states = []
        baseline_packet = json.loads((V2_RUN / 'annotation-packet-03.json').read_text())
        baseline = next(case for case in baseline_packet['cases'] if case['case_id'] == 'context-03')
        common_fragments = {f['fragment_id'] for f in baseline['state']['bounded_context']['fragments']}
        for cell in CELLS:
            packet = outputs[cell['packet']]
            self.assertEqual(packet['questions'], baseline_packet['questions'])
            self.assertEqual(packet['instructions'], baseline_packet['instructions'])
            self.assertEqual(packet['rubric_sha256'], digest((V2_RUN / 'rubric.json').read_bytes()))
            self.assertEqual(len(packet['cases']), 1)
            case = packet['cases'][0]
            self.assertEqual(case['state']['target']['code'], 'not entry.steps_is_list or not entry.steps')
            self.assertEqual(case['state']['architecture_profile'],
                             baseline['state']['architecture_profile'])
            self.assertEqual(case['state']['bounded_context']['fragments'][0]['code'],
                             baseline['state']['bounded_context']['fragments'][0]['code'])
            without_factors = copy.deepcopy(case['state'])
            without_factors['bounded_context']['fragments'] = [
                f for f in without_factors['bounded_context']['fragments'] if f['fragment_id'] in common_fragments]
            self.assertEqual(without_factors, baseline['state'])
            states.append(case['state'])
        self.assertEqual(len({s['target']['code'] for s in states}), 1)
        self.assertEqual(len({s['bounded_context']['fragments'][0]['code'] for s in states}), 1)

    def test_contract_and_implementation_evidence_are_source_pinned_and_separate(self):
        mapping = build()['source-mapping.json']
        facts = mapping['source_facts']
        self.assertIn('nonempty ordered list of nonempty strings', facts['contract_values']['code'])
        self.assertIn('Human approved for bdd_scenarios_v1', facts['contract_approval']['code'])
        self.assertIn('Specification[BDDContext]', facts['implementation_base']['code'])
        self.assertIn('return not self.findings(candidate)', facts['implementation_evaluator']['code'])
        self.assertIn('BDDScenarioValuesSpec()', facts['composition_membership']['code'])
        self.assertTrue(all(f['file_sha256'] for f in facts.values()))
        for cell in CELLS:
            packet = build()[cell['packet']]
            serialized = json.dumps(packet)
            self.assertNotIn('source-mapping', serialized)
            self.assertNotIn('contract_evidence_present', serialized)
            self.assertNotIn('implementation_link_evidence_present', serialized)

    def test_dispatch_plan_has_three_fresh_slots_per_cell_and_blank_templates(self):
        outputs = build()
        plan = outputs['dispatch-plan.json']
        self.assertEqual(len(plan['assignments']), 12)
        self.assertEqual({c['cell']: sum(a['cell'] == c['cell'] for a in plan['assignments'])
                          for c in CELLS}, {c['cell']: 3 for c in CELLS})
        for cell in CELLS:
            packet = outputs[cell['packet']]['cases'][0]
            template = outputs[cell['template']]['annotations'][0]
            self.assertEqual(template['state_sha256'], packet['state_sha256'])
            self.assertEqual(template['task_sha256'], packet['task_sha256'])
            self.assertIsNone(template['opportunity'])
            self.assertIsNone(template['concern_kind'])
        self.assertTrue(all(a['agent_task'] is None and a['directory'] is None for a in plan['assignments']))

    def test_task_digests_distinguish_context_cells_under_same_rubric_and_prompt(self):
        outputs = build()
        cases = [outputs[c['packet']]['cases'][0] for c in CELLS]
        self.assertEqual(len({c['state_sha256'] for c in cases}), 4)
        self.assertEqual(len({c['task_sha256'] for c in cases}), 4)
        self.assertEqual(len({outputs[c['packet']]['rubric_sha256'] for c in CELLS}), 1)
        self.assertEqual(len({outputs[c['packet']]['annotation_prompt_sha256'] for c in CELLS}), 1)

    def test_writer_refuses_existing_output_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'rubric.json'
            sentinel.write_text('keep')
            script = RUN.parents[1] / 'prepare_bdd_steps_factorial.py'
            completed = subprocess.run([sys.executable, str(script), '--run', directory, '--write'],
                                       capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn('Refusing to overwrite', completed.stderr)
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])


if __name__ == '__main__':
    unittest.main()
