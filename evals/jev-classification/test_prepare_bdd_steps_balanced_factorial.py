import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prepare_bdd_steps_balanced_factorial import (
    CONDITIONS, RUN, SOURCES, TARGETS, build, verify,
)
from question_grouping import digest


class BalancedBDDStepsFactorialPreparation(unittest.TestCase):
    def test_saved_packets_replay_and_receipt_tracks_producer(self):
        outputs = verify()
        receipt = outputs['preparation-receipt.json']
        self.assertEqual(receipt['status'], 'bdd_balanced_factorial_packet_prepared_not_dispatched')
        self.assertEqual(receipt['fresh_contexts_planned'], 12)
        self.assertEqual(receipt['distinct_targets'], 4)
        self.assertEqual(receipt['case_annotations_planned'], 48)
        self.assertEqual(receipt['provider_requests'], 0)
        producer = RUN.parents[1] / 'prepare_bdd_steps_balanced_factorial.py'
        self.assertEqual(receipt['producer_sha256'], digest(producer.read_bytes()))
        for name, sha in receipt['artifact_file_sha256'].items():
            self.assertEqual(sha, digest((RUN / name).read_bytes()))

    def test_each_context_gets_each_condition_once_and_never_repeats_a_target(self):
        outputs = build()
        plan = outputs['dispatch-plan.json']
        self.assertEqual(len(plan['assignments']), 12)
        target_cell_counts = {target['case_id']: {cell['cell']: 0 for cell in CONDITIONS}
                              for target in TARGETS}
        position_cell_counts = {position: {cell['cell']: 0 for cell in CONDITIONS}
                                for position in range(1, 5)}
        for assignment in plan['assignments']:
            cells = [item['cell'] for item in assignment['target_cell_assignments']]
            targets = [item['case_id'] for item in assignment['target_cell_assignments']]
            self.assertEqual(set(cells), {cell['cell'] for cell in CONDITIONS})
            self.assertEqual(len(targets), len(set(targets)))
            self.assertEqual(len(targets), 4)
            for item in assignment['target_cell_assignments']:
                target_cell_counts[item['case_id']][item['cell']] += 1
                position_cell_counts[item['position']][item['cell']] += 1
            packet = outputs[assignment['packet']]
            template = outputs[assignment['template']]
            self.assertEqual([c['case_id'] for c in packet['cases']],
                             [a['case_id'] for a in template['annotations']])
            for case, annotation in zip(packet['cases'], template['annotations']):
                self.assertEqual(case['state_sha256'], annotation['state_sha256'])
                self.assertEqual(case['task_sha256'], annotation['task_sha256'])
                self.assertIsNone(annotation['opportunity'])
                self.assertIsNone(annotation['concern_kind'])
        self.assertTrue(all(count == 3 for counts in target_cell_counts.values()
                            for count in counts.values()))
        self.assertTrue(all(count == 3 for counts in position_cell_counts.values()
                            for count in counts.values()))

    def test_link_cells_bind_each_exact_target_to_its_specification_method(self):
        outputs = build()
        source_mapping = outputs['source-mapping.json']
        for assignment in outputs['dispatch-plan.json']['assignments']:
            packet = outputs[assignment['packet']]
            assigned = {item['case_id']: item['cell']
                        for item in assignment['target_cell_assignments']}
            for case in packet['cases']:
                cell = next(cell for cell in CONDITIONS if cell['cell'] == assigned[case['case_id']])
                if not cell['implementation_link']:
                    continue
                target = next(t for t in TARGETS if t['case_id'] == case['case_id'])
                fragments = case['state']['bounded_context']['fragments']
                excerpt = next(f['code'] for f in fragments
                               if f['fragment_id'] == 'target-method-context')
                self.assertIn(target['code'], excerpt)
                self.assertIn('class BDDScenario', excerpt)
                self.assertIn('def findings(', excerpt)
                self.assertIn('Specification[BDDContext]', json.dumps(fragments))
                self.assertIn('BDDScenarioValuesSpec()', json.dumps(fragments))
                self.assertIn('BDDScenarioFieldsSpec()', json.dumps(fragments))
        facts = source_mapping['source_facts']
        self.assertIn('Specification[BDDContext]', facts['implementation_base']['code'])
        self.assertIn('BDDScenarioValuesSpec', facts['implementation_values_class']['code'])
        self.assertIn('BDDScenarioFieldsSpec', facts['implementation_fields_class']['code'])
        for fact in facts.values():
            self.assertTrue(fact['file_sha256'])
            self.assertTrue(fact['excerpt_sha256'])

    def test_contract_is_a_distinct_factor_and_labels_are_not_seeded(self):
        outputs = build()
        for assignment in outputs['dispatch-plan.json']['assignments']:
            packet = outputs[assignment['packet']]
            conditions_by_case = {entry['case_id']: entry['cell']
                                  for entry in assignment['target_cell_assignments']}
            for case in packet['cases']:
                cell = next(c for c in CONDITIONS if c['cell'] == conditions_by_case[case['case_id']])
                serialized = json.dumps(case, ensure_ascii=False)
                self.assertEqual('contract-values' in serialized, cell['contract'])
                self.assertNotIn('source-mapping', serialized)
                self.assertNotIn('eligible', serialized)
                self.assertNotIn('excluded', serialized)

    def test_task_identity_changes_by_condition_but_rubric_and_prompt_do_not(self):
        outputs = build()
        plan = outputs['dispatch-plan.json']
        cells_by_target = {target['case_id']: {} for target in TARGETS}
        for assignment in plan['assignments']:
            packet = outputs[assignment['packet']]
            labels = {item['case_id']: item['cell']
                      for item in assignment['target_cell_assignments']}
            for case in packet['cases']:
                cells_by_target[case['case_id']][labels[case['case_id']]] = case
        self.assertEqual(len({cell['task_sha256'] for cell in cells_by_target[TARGETS[0]['case_id']].values()}), 4)
        self.assertEqual(len({outputs[a['packet']]['rubric_sha256'] for a in plan['assignments']}), 1)
        self.assertEqual(len({outputs[a['packet']]['annotation_prompt_sha256'] for a in plan['assignments']}), 1)

    def test_writer_refuses_existing_output_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'rubric.json'
            sentinel.write_text('keep')
            script = RUN.parents[1] / 'prepare_bdd_steps_balanced_factorial.py'
            completed = subprocess.run([sys.executable, str(script), '--run', directory, '--write'],
                                       capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])


if __name__ == '__main__':
    unittest.main()
