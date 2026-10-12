import copy
import json
from pathlib import Path
import tempfile
import unittest

from contrastive_decision_study import REFERENCE, build
from decision_choice_contract import parse_response
from question_grouping import canonical, digest
from score_contrastive_decisions import score, summarize
from test_contrastive_decision_study import ANNOTATIONS, QUESTIONS, response_for

MAPPING = json.loads((REFERENCE / 'source-mapping.json').read_text())


def native_fixture():
    rows = []
    for request in build()['requests']:
        rows.append({key: request[key] for key in ('request_id', 'provider', 'repeat', 'case_id')})
        rows[-1].update(native_status='valid', transport_status='json_received', ambiguous_posts=0,
                        duplicate_execution_possible=False, usage=None,
                        prediction=parse_response(canonical(response_for(request['wire_json'])),
                            provider=request['provider'], model=request['requested_model'], questions=QUESTIONS))
    return {'planned_requests': 48, 'received_rows': 48, 'native_valid': 48, 'native_invalid': 0,
            'rows': rows, 'attempt_ledger_complete': True, 'operationally_complete': True,
            'missing_result_request_ids': [], 'unattempted_request_ids': [],
            'attempt_status_unknown_request_ids': [], 'attempted_without_result_request_ids': []}


def selected(native, role, repeat=1, pair='pair-01'):
    cid = next(r['case_id'] for r in MAPPING['cases'] if r['stratum'] == role and r['pair_id'] == pair)
    return next(row for row in native['rows']
                if row['case_id'] == cid and row['provider'] == 'jev-coreinfra' and row['repeat'] == repeat)


def change_label(row, axis, label):
    answer = row['prediction']['answers'][axis]
    answer['choice'] = label
    answer['probabilities'] = {option: float(option == label) for option in answer['probabilities']}


def summary(native):
    return summarize(native, ANNOTATIONS, MAPPING)


class HypothesisScoring(unittest.TestCase):
    def test_perfect_contrasts_and_abstention_pass_separately(self):
        report = summary(native_fixture())
        self.assertEqual(report['planned_requests'], 48)
        self.assertFalse(report['inference_performed_by_scorer'])
        self.assertEqual(report['metric_effect'], 'none')
        for provider in report['providers']:
            self.assertTrue(provider['repeat_consistency']['supported'])
            self.assertEqual(provider['repeat_consistency']['planned_axis_pairs'], 24)
            for repeat in provider['repeats']:
                for hypothesis in ('H1', 'H2', 'H3_secondary'):
                    self.assertTrue(repeat[hypothesis]['supported'])
                self.assertEqual(repeat['eligible_policy_recall'], {'recovered': 4, 'planned': 4})
                self.assertEqual(repeat['mechanical_false_positives']['case_ids'], [])
                self.assertEqual(repeat['full_context_axes']['opportunity']['matched'], 8)
                self.assertEqual(len(repeat['pairs']), 4)
                self.assertEqual(len(repeat['withheld_controls']), 4)

    def test_mechanics_false_positive_fails_complete_pair_but_not_abstention(self):
        native = native_fixture()
        row = selected(native, 'mechanics'); change_label(row, 'opportunity', 'eligible')
        repeat = summary(native)['providers'][0]['repeats'][0]
        self.assertEqual(repeat['H1']['correct_pairs'], 3)
        self.assertFalse(repeat['H1']['supported'])
        self.assertTrue(repeat['H2']['supported'])
        self.assertEqual(repeat['mechanical_false_positives']['case_ids'], [row['case_id']])

    def test_wrong_concern_kind_fails_h1_even_with_perfect_eligible_recall(self):
        native = native_fixture()
        change_label(selected(native, 'policy'), 'concern_kind', 'mechanics')
        repeat = summary(native)['providers'][0]['repeats'][0]
        self.assertEqual(repeat['eligible_policy_recall']['recovered'], 4)
        self.assertEqual(repeat['full_context_axes']['opportunity']['matched'], 8)
        self.assertFalse(repeat['H1']['supported'])

    def test_withheld_error_fails_h2_without_changing_full_context_endpoint(self):
        native = native_fixture()
        change_label(selected(native, 'withheld'), 'opportunity', 'eligible')
        repeat = summary(native)['providers'][0]['repeats'][0]
        self.assertTrue(repeat['H1']['supported'])
        self.assertFalse(repeat['H2']['supported'])
        self.assertEqual(repeat['H2']['correct_controls'], 3)
        self.assertEqual(repeat['full_context_axes']['opportunity']['planned'], 8)

    def test_h3_requires_both_strict_deltas_in_three_pairs_ties_do_not_count(self):
        native = native_fixture()
        for index, pair in enumerate(('pair-01', 'pair-02'), 1):
            for role in ('mechanics', 'policy'):
                answer = selected(native, role, pair=pair)['prediction']['answers']['opportunity']
                answer['probabilities'] = {'eligible': 0.5, 'excluded': 0.5, 'needs_review': 0}
            repeat = summary(native)['providers'][0]['repeats'][0]
            self.assertEqual(repeat['H3_secondary']['directional_pairs'], 4 - index)
            self.assertEqual(repeat['H3_secondary']['supported'], index == 1)
            self.assertTrue(repeat['H1']['supported'])

    def test_missing_and_invalid_results_keep_planned_denominators(self):
        for kind in ('missing', 'invalid'):
            with self.subTest(kind=kind):
                native = native_fixture(); row = selected(native, 'policy')
                if kind == 'missing':
                    native['rows'].remove(row)
                    native['received_rows'] -= 1
                    native['missing_result_request_ids'] = [row['request_id']]
                    native['attempt_status_unknown_request_ids'] = [row['request_id']]
                else:
                    row['native_status'] = 'invalid'; row['prediction'] = None
                    native['native_invalid'] = 1
                native['native_valid'] -= 1
                native['operationally_complete'] = False
                repeat = summary(native)['providers'][0]['repeats'][0]
                self.assertEqual(repeat['planned_cases'], 12)
                self.assertEqual(repeat['eligible_policy_recall'], {'recovered': 3, 'planned': 4})
                self.assertEqual(repeat['H1']['planned'], 4)
                self.assertEqual(repeat['H2']['planned'], 4)
                self.assertEqual(repeat['H3_secondary']['planned'], 4)
                self.assertEqual(repeat['unavailable_or_ambiguous_case_ids'], [row['case_id']])
                self.assertFalse(repeat['H1']['supported'])
                self.assertFalse(repeat['H2']['supported'])
                self.assertFalse(repeat['H3_secondary']['supported'])

    def test_ambiguous_success_is_retained_but_cannot_support_hypothesis(self):
        native = native_fixture(); row = selected(native, 'policy')
        row.update(ambiguous_posts=1, duplicate_execution_possible=True)
        native['operationally_complete'] = False
        report = summary(native)
        self.assertEqual(report['native_valid'], 48)
        repeat = report['providers'][0]['repeats'][0]
        policy = repeat['pairs'][0]['policy']
        self.assertIsNotNone(policy['prediction'])
        self.assertFalse(policy['usable_for_criteria'])
        self.assertFalse(repeat['H1']['supported'])
        self.assertFalse(report['providers'][0]['repeat_consistency']['supported'])

    def test_unknown_execution_status_cannot_support_completed_claim(self):
        native = native_fixture(); native['attempt_ledger_complete'] = False
        native['operationally_complete'] = False
        report = summary(native)
        repeat = report['providers'][0]['repeats'][0]
        self.assertTrue(repeat['H1']['criterion_met'])
        self.assertFalse(repeat['H1']['supported'])
        self.assertFalse(report['providers'][0]['repeat_consistency']['supported'])

    def test_repeat_disagreement_is_separate_from_numeric_variation(self):
        native = native_fixture()
        row = selected(native, 'policy', repeat=2)
        change_label(row, 'opportunity', 'excluded')
        row['prediction']['answers']['opportunity']['confidence'] = 0.6
        result = summary(native)['providers'][0]['repeat_consistency']
        self.assertEqual(len(result['label_disagreements']), 1)
        self.assertEqual(result['label_disagreements'][0]['case_id'], row['case_id'])
        self.assertAlmostEqual(result['max_native_confidence_delta'], 0.2)
        self.assertEqual(result['max_option_probability_delta'], 1)
        self.assertFalse(result['supported'])

    def test_incomplete_mapping_and_duplicate_results_fail_closed(self):
        native = native_fixture(); native['rows'].append(copy.deepcopy(native['rows'][0]))
        with self.assertRaises(ValueError):
            summary(native)
        mapping = copy.deepcopy(MAPPING); mapping['cases'][0]['stratum'] = 'other'
        with self.assertRaises(ValueError):
            summarize(native_fixture(), ANNOTATIONS, mapping)

    def test_offline_empty_run_records_unknowns_and_exact_reference_review_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / 'manifest.json').write_bytes(canonical(build()))
            result = score(run)
            self.assertEqual(result['native_valid'], 0)
            self.assertEqual(len(result['attempt_status_unknown_request_ids']), 48)
            self.assertEqual(result['unattempted_request_ids'], [])
            self.assertFalse(result['operationally_complete'])
            self.assertEqual(result['reference_sha256'], digest((REFERENCE / 'independent-annotations.json').read_bytes()))
            self.assertEqual(result['reference_review_sha256'], digest((REFERENCE / 'reference-review.json').read_bytes()))


if __name__ == '__main__':
    unittest.main()
