import copy
import json
import unittest

from question_grouping import digest
from validate_context_annotations import AXES, RUN, build, compare_views, validate


class ContextAnnotations(unittest.TestCase):
    def setUp(self):
        self.assignments = json.loads((RUN / 'annotation-assignments.json').read_text())['assignments']
        self.packets = [json.loads((RUN / f'annotation-packet-{n:02d}.json').read_text()) for n in (1, 2, 3)]
        self.annotations = [json.loads((RUN / f'independent-annotations-{n:02d}.json').read_text()) for n in (1, 2, 3)]
        self.mapping = json.loads((RUN / 'source-mapping.json').read_text())

    def test_saved_annotations_validate_without_asserting_semantic_truth(self):
        for packet, annotation, assignment in zip(self.packets, self.annotations, self.assignments):
            result = validate(packet, annotation, assignment)
            self.assertEqual(result['annotated_cases'], 6)
            self.assertFalse(result['semantic_correctness_verified'])
        report = build()
        self.assertFalse(report['reference_frozen_for_provider_scoring'])
        self.assertEqual(report['metric_effect'], 'none')

    def test_missing_duplicate_stale_and_unknown_label_rejected(self):
        mutations = [lambda a: a['annotations'].pop(),
                     lambda a: a['annotations'].__setitem__(1, copy.deepcopy(a['annotations'][0])),
                     lambda a: a['annotations'][0].update(state_sha256='stale'),
                     lambda a: a['annotations'][0].update(opportunity='policy'),
                     lambda a: a.update(status='human_gold'),
                     lambda a: a['isolation_report'].update(other_inputs_read=True),
                     lambda a: a['isolation_report']['input_files'].append('other-packet.json')]
        for mutate in mutations:
            changed = copy.deepcopy(self.annotations[0]); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate(self.packets[0], changed, self.assignments[0])

    def test_each_axis_requires_case_local_code_evidence_and_explanation(self):
        mutations = [lambda a: a['annotations'][0].update(evidence_quotes=[]),
                     lambda a: a['annotations'][0]['evidence_quotes'][0].update(quote='invented quote'),
                     lambda a: a['annotations'][0]['evidence_quotes'][0].update(quote=self.packets[0]['cases'][1]['state']['target']['code']),
                     lambda a: a['annotations'][0]['rationales'].update(opportunity=''),
                     lambda a: a['annotations'][0].update(uncertainties=['']),
                     lambda a: [q.update(axis='opportunity') for q in a['annotations'][0]['evidence_quotes']],
                     lambda a: a['annotations'][0].update(opportunity='needs_review', uncertainties=[])]
        for mutate in mutations:
            changed = copy.deepcopy(self.annotations[0]); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate(self.packets[0], changed, self.assignments[0])

    def test_differences_preserved_without_promoting_full_context_to_gold(self):
        original = copy.deepcopy(self.annotations)
        changed = copy.deepcopy(self.annotations)
        for doc, label in zip(changed, ('eligible', 'excluded', 'needs_review')):
            for row in doc['annotations']:
                row['opportunity'] = label
        result = compare_views(self.mapping, self.packets, changed)
        self.assertEqual(len(result['target_families']), 6)
        self.assertTrue(all('opportunity' in f['varying_axes'] for f in result['target_families']))
        self.assertEqual(result['label_overrides'], [])
        self.assertEqual(self.annotations, original)
        self.assertIn('confound evidence and annotator', result['interpretation'])

    def test_cross_view_mapping_cannot_duplicate_drop_or_rebind_cases(self):
        mutations = [lambda m: m['cases'].pop(),
                     lambda m: m['cases'].__setitem__(1, copy.deepcopy(m['cases'][0])),
                     lambda m: m['cases'][0].update(state_sha256='stale'),
                     lambda m: m['cases'][0].update(evidence_mode='expression_only'),
                     lambda m: m['cases'][0].update(target_id='wrong-target'),
                     lambda m: m['cases'][0].update(expression_sha256='wrong-expression')]
        for mutate in mutations:
            changed = copy.deepcopy(self.mapping); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                compare_views(changed, self.packets, self.annotations)

    def test_saved_receipt_binds_all_inputs_and_replays_exactly(self):
        receipt = json.loads((RUN / 'annotation-receipt.json').read_text())
        self.assertEqual(receipt, build())
        for name, sha in receipt['input_file_sha256'].items():
            self.assertEqual(sha, digest((RUN / name).read_bytes()))
        self.assertEqual(receipt['comparison']['jev_luna_requests'], 0)
        self.assertEqual(receipt['comparison']['label_overrides'], [])
        self.assertEqual(set(AXES), {'opportunity', 'concern_kind'})


if __name__ == '__main__':
    unittest.main()
