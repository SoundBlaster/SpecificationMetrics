"""Guard scope-factor isolation, static source bindings and frozen evidence."""
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_scope_binding_diagnostic as subject
from prepare_context_reference_v2 import task_digest
from question_grouping import canonical, digest


class ScopeBindingPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = subject.verify()
        cls.evidence = json.loads((subject.EVIDENCE / 'source-bindings.json').read_text())
        cls.catalog = json.loads((subject.prior.EVIDENCE / 'evidence-bundles.json').read_text())
        cls.cases = {}
        for assignment in cls.outputs['dispatch-plan.json']['assignments']:
            for condition, case in zip(assignment['cases'], cls.outputs[assignment['packet']]['cases']):
                cls.cases[condition['case_id'], condition['cell']] = case

    def test_every_context_balances_distinct_families_and_four_conditions(self):
        plan = self.outputs['dispatch-plan.json']
        self.assertEqual(len(plan['assignments']), 12)
        for assignment in plan['assignments']:
            self.assertEqual(len(assignment['cases']), 4)
            self.assertEqual({c['cell'] for c in assignment['cases']}, {'01', '02', '03', '04'})
            self.assertEqual(len({c['case_id'] for c in assignment['cases']}), 4)
        rows = [c for a in plan['assignments'] for c in a['cases']]
        for fields in (('case_id', 'cell'), ('case_id', 'position'), ('cell', 'position')):
            counts = Counter(tuple(c[f] for f in fields) for c in rows)
            self.assertEqual(len(counts), 16)
            self.assertEqual(set(counts.values()), {3})
        self.assertLess(len({(c['case_id'], c['cell'], c['position']) for c in rows}), 64)

    def test_scope_changes_only_unit_and_documents_are_additive(self):
        for cid in ('target-01', 'target-02', 'target-03', 'target-04'):
            for left, right in (('01', '03'), ('02', '04')):
                a, b = (copy.deepcopy(self.cases[cid, cell]['state']) for cell in (left, right))
                self.assertEqual(a['evaluation_scope'].pop('unit'), 'shared_definition')
                self.assertEqual(b['evaluation_scope'].pop('unit'), 'bound_application')
                self.assertEqual(a, b)
            for left, right in (('01', '02'), ('03', '04')):
                a, b = (copy.deepcopy(self.cases[cid, cell]['state']) for cell in (left, right))
                code = b['bounded_context']['fragments']
                self.assertTrue(any('text' in f for f in code))
                b['bounded_context']['fragments'] = [f for f in code if 'text' not in f]
                self.assertEqual(a, b)

    def test_task_identity_binds_scope_and_repeats_case_bytes_three_times(self):
        counts, seen = Counter(), {}
        for assignment in self.outputs['dispatch-plan.json']['assignments']:
            packet = self.outputs[assignment['packet']]
            for case in packet['cases']:
                self.assertEqual(case['task_sha256'], task_digest(case, packet))
                self.assertEqual(case['state_sha256'], digest(canonical(case['state'])))
                raw = subject.encoded(case)
                self.assertEqual(seen.setdefault(case['task_sha256'], raw), raw)
                counts[case['task_sha256']] += 1
                altered = copy.deepcopy(case)
                altered['state']['evaluation_scope']['unit'] = 'wrong_scope'
                self.assertNotEqual(case['task_sha256'], task_digest(altered, packet))
        self.assertEqual(len(counts), 16)
        self.assertEqual(set(counts.values()), {3})

    def test_ast_identity_does_not_depend_on_dump_format_or_locations(self):
        import ast
        node = ast.parse('f(x)', mode='eval').body
        expected = subject.ast_key(node)
        with patch.object(ast, 'dump', side_effect=AssertionError('format-specific dump must not be used')):
            self.assertEqual(subject.ast_key(node), expected)
            node.lineno = 99
            node.col_offset = 8
            self.assertEqual(subject.ast_key(node), expected)

    def test_real_anchors_and_arguments_validate_against_snapshots(self):
        targets = {t['case_id']: t['target'] for t in self.catalog['targets']}
        for binding in self.evidence['bindings']:
            subject.verify_binding(self.evidence['sources'], binding, targets[binding['case_id']])

    def test_stale_anchor_wrong_argument_and_foreign_receiver_are_rejected(self):
        bindings = self.evidence['bindings']
        a = copy.deepcopy(bindings[0])
        a['definition']['span'][0] += 1
        with self.assertRaisesRegex(ValueError, 'AST anchor'):
            subject.verify_binding(self.evidence['sources'], a, self.catalog['targets'][0]['target'])
        a = copy.deepcopy(bindings[0])
        a['application']['argument_binding']['expression'] = 'staging_prefix'
        with self.assertRaisesRegex(ValueError, 'argument binding'):
            subject.verify_binding(self.evidence['sources'], a, self.catalog['targets'][0]['target'])
        a = copy.deepcopy(bindings[2])
        a['application']['receiver_binding']['selected_member'] = 'BDDScenarioIDsSpec()'
        with self.assertRaisesRegex(ValueError, 'receiver membership'):
            subject.verify_binding(self.evidence['sources'], a, self.catalog['targets'][2]['target'])

    def test_snapshot_cannot_be_replaced_even_with_self_consistent_catalog_hash(self):
        with tempfile.TemporaryDirectory() as parent:
            folder = Path(parent)
            altered = copy.deepcopy(self.evidence)
            source = altered['sources']['tools/static_artifact_incremental_stage.py']
            source['content'] += '\n# altered after source selection\n'
            source['sha256'] = digest(source['content'].encode())
            raw = subject.encoded(altered)
            (folder / 'source-bindings.json').write_bytes(raw)
            with patch.object(subject, 'EVIDENCE', folder), patch.object(subject, 'BINDING_SHA', digest(raw)):
                with self.assertRaisesRegex(ValueError, 'Pinned source snapshot'):
                    subject.build()

    def test_no_prior_labels_enter_preparation_or_dispatch_readiness(self):
        receipt = self.outputs['preparation-receipt.json']
        self.assertFalse(receipt['annotation_started'])
        self.assertFalse(receipt['dispatch_ready'])
        self.assertEqual(receipt['provider_requests'], 0)
        self.assertFalse(receipt['human_gold'])
        self.assertTrue(all('results' not in p for p in receipt['input_file_sha256']))
        for assignment in self.outputs['dispatch-plan.json']['assignments']:
            blank = self.outputs[assignment['template']]
            self.assertTrue(all(r['opportunity'] is None and r['concern_kind'] is None for r in blank['annotations']))
            self.assertIsNone(assignment['agent_task'])
        rubric = json.loads(self.outputs['rubric.json'])
        old = json.loads(subject.prior.verify()['rubric.json'])
        for axis in old['questions']:
            self.assertEqual(rubric['questions'][axis]['criteria'], old['questions'][axis]['criteria'])
            self.assertTrue(rubric['questions'][axis]['instructions'].endswith(old['questions'][axis]['instructions']))

    def test_controls_do_not_reveal_focal_helper_and_all_views_keep_exact_targets(self):
        for target in self.catalog['targets']:
            for cell in ('01', '02', '03', '04'):
                state = self.cases[target['case_id'], cell]['state']
                self.assertEqual(state['target'], target['target'])
                if target['case_id'] != 'target-01':
                    raw = json.dumps(state)
                    self.assertNotIn('_safe_path', raw)
                    self.assertNotIn('staging_prefix', raw)

    def test_exclusive_write_replay_and_extra_or_changed_file_rejection(self):
        with tempfile.TemporaryDirectory() as parent:
            run = Path(parent) / 'new'
            subject.write(run)
            subject.verify(run)
            with self.assertRaises(FileExistsError):
                subject.write(run)
            extra = run / 'unreviewed.json'
            extra.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'file set'):
                subject.verify(run)
            extra.unlink()
            (run / 'packet-annotator-01.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Frozen scope preparation'):
                subject.verify(run)


if __name__ == '__main__':
    unittest.main()
