import copy
from pathlib import Path
import tempfile
import unittest

import coreinfra_retry_run as transport
from paired_reference_assignment_v1 import build_plan, freeze, validate_assignments, validate_roster, verify
from retrieval_index_v1.source import encoded

PREPARATION = Path(__file__).resolve().parent / 'runs/2026-10-18-paired-retrieval-preparation-v1'


class ReferenceAssignmentTests(unittest.TestCase):
    def test_each_annotator_has_both_modes_and_distinct_dependency_families(self):
        plan = build_plan(PREPARATION)
        self.assertEqual(plan['status'], 'prepared_not_dispatched')
        self.assertFalse(plan['dispatch_authorized'])
        self.assertEqual([(s['annotator_slot'], [t['case_id'] for t in s['tasks']]) for s in plan['slots']],
                         [('A', ['R01', 'R02']), ('B', ['R02', 'R01']),
                          ('C', ['R03', 'R04']), ('D', ['R04', 'R03'])])
        for slot in plan['slots']:
            self.assertEqual([t['arm'] for t in slot['tasks']], ['baseline', 'retrieval'])
            self.assertEqual(len({t['family'] for t in slot['tasks']}), 2)
            # Shared retrieved definitions really exist; session resets alone
            # cannot justify independence for a human annotator.
            self.assertTrue(slot['leakage_audit']['withheld_baseline_definitions_present_in_later_view'])
            self.assertEqual(slot['tasks'][1]['after_annotation_sealed'], slot['tasks'][0]['task_id'])

    def test_original_confounded_assignment_and_unsafe_groupings_are_rejected(self):
        original = build_plan(PREPARATION)['slots']
        for mutation in ('single_mode', 'same_target', 'shared_family', 'wrong_family', 'unsealed', 'retrieval_first'):
            with self.subTest(mutation=mutation):
                slots = copy.deepcopy(original)
                if mutation == 'single_mode':
                    slots[0]['tasks'][1]['arm'] = 'baseline'
                elif mutation == 'same_target':
                    slots[0]['tasks'][1].update(case_id='R01', family='workspace_allocation')
                elif mutation == 'shared_family':
                    slots[0]['tasks'][0].update(case_id='R03', family='subject_source_write')
                elif mutation == 'wrong_family':
                    slots[0]['tasks'][0]['family'] = 'invented'
                elif mutation == 'unsealed':
                    slots[0]['tasks'][1]['after_annotation_sealed'] = None
                else:
                    slots[0]['tasks'].reverse()
                with self.assertRaises(ValueError):
                    validate_assignments(slots)

    def test_actual_identities_cannot_be_reused_across_slots_or_have_prior_exposure(self):
        roster = [dict(annotator_slot=slot, actual_identity='participant:' + slot,
                       prior_cohort_exposure=False) for slot in 'ABCD']
        validate_roster(roster)
        for mutation in ('shared_identity', 'exposed', 'missing_slot'):
            value = copy.deepcopy(roster)
            if mutation == 'shared_identity':
                value[1]['actual_identity'] = value[0]['actual_identity']
            elif mutation == 'exposed':
                value[0]['prior_cohort_exposure'] = True
            else:
                value[0]['annotator_slot'] = 'B'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_roster(value)

    def test_separate_receipt_binds_plan_producers_and_existing_frozen_views(self):
        before = {str(p.relative_to(PREPARATION)): p.read_bytes()
                  for p in PREPARATION.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'handoff'
            plan = freeze(PREPARATION, output)
            self.assertEqual(verify(PREPARATION, output), plan)
            with self.assertRaises(FileExistsError):
                freeze(PREPARATION, output)
            value = copy.deepcopy(plan)
            value['slots'][0]['tasks'][0]['files'] = {}
            raw = (encoded(value) + '\n').encode()
            (output / 'plan.json').write_bytes(raw)
            receipt = transport.decode((output / 'receipt.json').read_bytes())
            receipt['file_sha256']['plan.json'] = transport.sha(raw)
            (output / 'receipt.json').write_text(encoded(receipt))
            with self.assertRaisesRegex(ValueError, 'plan differs'):
                verify(PREPARATION, output)
        self.assertEqual(before, {str(p.relative_to(PREPARATION)): p.read_bytes()
                                 for p in PREPARATION.rglob('*') if p.is_file()})

    def test_receipt_authority_and_producer_mutations_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'handoff'
            freeze(PREPARATION, output)
            path = output / 'receipt.json'
            original = transport.decode(path.read_bytes())
            for name, replacement in (('producer_sha256', {}), ('hosted_requests', False),
                                      ('dispatch_authorized', 0), ('dispatch_authorized', True)):
                value = copy.deepcopy(original)
                value[name] = replacement
                path.write_text(encoded(value))
                with self.subTest(name=name, value=replacement), self.assertRaises(ValueError):
                    verify(PREPARATION, output)


if __name__ == '__main__':
    unittest.main()
