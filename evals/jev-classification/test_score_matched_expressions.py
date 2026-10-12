import copy
import json
import unittest

from matched_expression_plan import REFERENCE
from score_matched_expressions import score, summarize

ANNOTATIONS = json.loads((REFERENCE / 'independent-annotations.json').read_text())


def native_fixture():
    rows = []
    for provider in ('jev-coreinfra', 'luna-decision-coreinfra'):
        for repeat in (1, 2):
            for ref in ANNOTATIONS['annotations']:
                answers = {axis: {'choice': ref[axis], 'confidence': 1.0, 'probabilities': {ref[axis]: 1.0}}
                           for axis in ('opportunity', 'concern_kind')}
                rows.append({'provider': provider, 'repeat': repeat, 'case_id': ref['case_id'],
                             'native_status': 'valid', 'prediction': {'answers': answers}})
    return {'planned_requests': 32, 'received_rows': 32, 'native_valid': 32, 'native_invalid': 0,
            'missing_result_request_ids': [], 'unattempted_request_ids': [],
            'attempt_status_unknown_request_ids': [], 'attempted_without_result_request_ids': [], 'rows': rows}


class Scoring(unittest.TestCase):
    def test_saved_live_report_replays_exactly_without_inference(self):
        run = REFERENCE.parent / '2026-10-12-matched-expression-wires'
        saved = json.loads((run / 'raw-provider-score.json').read_text())
        self.assertEqual(score(run), saved)
        self.assertEqual(saved['native_valid'], 32)
        self.assertFalse(saved['inference_performed_by_scorer'])

    def test_perfect_fixture_satisfies_registered_criteria(self):
        result = summarize(native_fixture(), ANNOTATIONS)
        self.assertTrue(all(p['preregistered_provider_criteria_passed'] for p in result['providers']))
        for p in result['providers']:
            for repeat in p['repeats']:
                self.assertEqual(repeat['eligible_recall'], {'recovered': 3, 'planned': 3})
                self.assertEqual(repeat['excluded_control_strata']['policy']['planned'], 2)
                self.assertEqual(repeat['excluded_control_strata']['mechanics']['planned'], 3)

    def test_missing_native_response_does_not_shrink_denominator(self):
        native = native_fixture(); native['rows'].pop()
        native.update(received_rows=31, native_valid=31, missing_result_request_ids=['missing'])
        result = summarize(native, ANNOTATIONS); provider = result['providers'][1]
        self.assertFalse(provider['preregistered_provider_criteria_passed'])
        self.assertEqual(provider['repeats'][1]['axes']['opportunity']['planned'], 8)
        self.assertEqual(provider['repeats'][1]['native_valid'], 7)
        self.assertEqual(provider['repeat_consistency']['paired_axis_answers'], 14)
        self.assertEqual(result['missing_result_request_ids'], ['missing'])

    def test_false_exclusion_and_repeat_disagreement_fail_strong_claim(self):
        native = native_fixture()
        row = next(r for r in native['rows'] if r['prediction']['answers']['opportunity']['choice'] == 'eligible')
        row['prediction']['answers']['opportunity']['choice'] = 'excluded'
        result = summarize(native, ANNOTATIONS); p = result['providers'][0]
        self.assertFalse(p['preregistered_provider_criteria_passed'])
        self.assertEqual(p['repeats'][0]['axes']['opportunity']['matched'], 7)
        self.assertEqual(p['repeats'][0]['eligible_recall']['recovered'], 2)
        self.assertEqual(p['repeats'][0]['missed_or_unavailable_eligible_ids'], [row['case_id']])
        self.assertEqual(len(p['repeat_consistency']['label_disagreements']), 1)

    def test_false_positive_controls_are_reported_by_stratum(self):
        native = native_fixture()
        row = next(r for r in native['rows'] if r['prediction']['answers']['opportunity']['choice'] == 'excluded'
                   and r['prediction']['answers']['concern_kind']['choice'] == 'mechanics')
        row['prediction']['answers']['opportunity']['choice'] = 'eligible'
        p = summarize(native, ANNOTATIONS)['providers'][0]
        self.assertFalse(p['preregistered_provider_criteria_passed'])
        self.assertEqual(p['repeats'][0]['excluded_control_strata']['mechanics']['false_positive_ids'], [row['case_id']])

    def test_duplicate_rows_are_rejected(self):
        native = native_fixture(); native['rows'].append(copy.deepcopy(native['rows'][0]))
        with self.assertRaises(ValueError): summarize(native, ANNOTATIONS)


if __name__ == '__main__':
    unittest.main()
