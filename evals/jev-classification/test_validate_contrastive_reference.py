import copy
import json
import unittest

from question_grouping import digest
from validate_contrastive_reference import RUN, compare, validate


class ContrastiveReference(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((RUN / 'case-packet.json').read_text())
        self.reference = json.loads((RUN / 'independent-annotations.json').read_text())
        self.proposals = json.loads((RUN / 'author-proposals.json').read_text())
        self.mapping = json.loads((RUN / 'source-mapping.json').read_text())

    def test_complete_reference_has_case_local_evidence_without_claiming_semantic_proof(self):
        result = validate(self.packet, self.reference)
        self.assertEqual(result['annotated_cases'], 12)
        self.assertEqual(result['structural_evidence_validation'], 'passed')
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertEqual(result['authority'], 'independent_model_annotation_not_human_gold')

    def test_missing_duplicate_stale_or_invalid_annotations_fail(self):
        mutations = [lambda r: r['annotations'].pop(),
                     lambda r: r['annotations'].__setitem__(1, copy.deepcopy(r['annotations'][0])),
                     lambda r: r['annotations'][0].update(state_sha256='stale'),
                     lambda r: r['annotations'][0].update(concern_kind='eligible'),
                     lambda r: r.update(status='human_gold'),
                     lambda r: r['isolation'].update(context_inheritance='all'),
                     lambda r: r['isolation'].update(other_sources_used=True),
                     lambda r: r['isolation']['inputs_read'].append('author-proposals.json')]
        for mutate in mutations:
            changed = copy.deepcopy(self.reference)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate(self.packet, changed)

    def test_quotes_rationales_and_both_axis_evidence_are_required(self):
        mutations = [lambda r: r['annotations'][0].update(evidence_quotes=[]),
                     lambda r: r['annotations'][0]['evidence_quotes'][0].update(quote='invented evidence'),
                     lambda r: r['annotations'][0]['evidence_quotes'][0].update(location='other-case'),
                     lambda r: r['annotations'][0]['rationale'].update(opportunity=''),
                     lambda r: r['annotations'][0].update(uncertainties=['']),
                     lambda r: [e.update(supports_axes=['opportunity']) for e in r['annotations'][0]['evidence_quotes']]]
        for mutate in mutations:
            changed = copy.deepcopy(self.reference)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate(self.packet, changed)

    def test_disagreements_are_preserved_not_relabelled(self):
        changed = copy.deepcopy(self.proposals)
        first = changed['annotations'][0]
        first['opportunity'] = 'excluded' if first['opportunity'] != 'excluded' else 'eligible'
        result = compare(self.packet, self.reference, changed, self.mapping)
        mismatch = next(d for d in result['disagreements'] if d['case_id'] == first['case_id'])
        original = next(r for r in self.reference['annotations'] if r['case_id'] == first['case_id'])
        self.assertEqual(mismatch['independent']['opportunity'], original['opportunity'])
        self.assertEqual(result['label_overrides'], [])
        first['state_sha256'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'Stale proposal'):
            compare(self.packet, self.reference, changed, self.mapping)

    def test_saved_review_matches_raw_reference_and_keeps_original_uncertainties(self):
        review = json.loads((RUN / 'reference-review.json').read_text())
        self.assertEqual(review['reference_sha256'], digest((RUN / 'independent-annotations.json').read_bytes()))
        for field, name in [('packet_file_sha256', 'case-packet.json'), ('template_sha256', 'annotation-template.json'),
                            ('proposals_sha256', 'author-proposals.json'), ('mapping_sha256', 'source-mapping.json')]:
            self.assertEqual(review[field], digest((RUN / name).read_bytes()))
        self.assertEqual(review['validator_sha256'], digest(RUN.parents[1].joinpath('validate_contrastive_reference.py').read_bytes()))
        self.assertEqual(review['comparison'], compare(self.packet, self.reference, self.proposals, self.mapping))
        self.assertEqual(review['jev_luna_requests'], 0)
        self.assertEqual(review['label_overrides'], [])
        uncertain = {r['case_id'] for r in self.reference['annotations'] if r['uncertainties']}
        self.assertEqual({r['case_id'] for r in review['uncertainty_review']}, uncertain)
        self.assertEqual(review['status'], 'independent_model_reference_reviewed_native_wires_pending')


if __name__ == '__main__':
    unittest.main()
