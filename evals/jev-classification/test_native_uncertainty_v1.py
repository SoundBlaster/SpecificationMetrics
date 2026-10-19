import copy
import json
import unittest
from unittest.mock import patch

from categorical_review_bridge_v1 import bind
from native_uncertainty_v1 import evaluate
from specgraph_pr714_live_v1 import bound_task
from structured_semantic_review_v1.preparation import encoded


class NativeUncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.network = patch('socket.socket.connect', side_effect=AssertionError('offline only'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.bound = bound_task('D01')
        labels = dict(concern_kind='policy', evidence_confidence='supported',
                      ownership='unknown', tool_responsibility='unknown')
        self.body = dict(model='jev-1.13.0', answers={
            axis: dict(type='choice', choice=labels[axis], confidence=0.9,
                       probabilities={key: float(key == labels[axis]) for key in question.criteria})
            for axis, question in self.bound.sdk_task().questions.items()})

    def masses(self, axis, **values):
        self.body['answers'][axis]['probabilities'] = values

    def result(self, **kwargs):
        return evaluate(self.bound, encoded(self.body).encode(), **kwargs)

    def test_plurality_tie_and_strict_majority_boundaries(self):
        for selected, alternatives, route in [
            (0.49, (0.30, 0.20, 0.01), 'ordinary_review'),
            (0.50, (0.30, 0.19, 0.01), 'ordinary_review'),
            (0.51, (0.30, 0.18, 0.01), 'retain_proposal'),
        ]:
            with self.subTest(selected=selected):
                self.masses('concern_kind', policy=selected, mechanics=alternatives[0],
                            variant_behavior=alternatives[1], unknown=alternatives[2])
                row = self.result()
                self.assertEqual(row['baseline_route'], 'retain_proposal')
                self.assertEqual(row['route'], route)

    def test_weak_evidence_axis_escalates_even_when_role_is_certain(self):
        self.masses('evidence_confidence', supported=0.48, limited=0.45, insufficient=0.07)
        row = self.result()
        self.assertEqual(row['route'], 'ordinary_review')
        self.assertEqual([a['axis'] for a in row['axes'] if not a['strict_majority']],
                         ['evidence_confidence'])

    def test_irrelevant_unknown_axes_do_not_force_role_review(self):
        self.masses('ownership', unknown=0.34, existing_specification=0.33, simple_composition=0.33)
        self.assertEqual(self.result()['route'], 'retain_proposal')
        self.body['answers']['ownership']['choice'] = 'existing_specification'
        self.masses('ownership', unknown=0.35, existing_specification=0.45, simple_composition=0.20)
        self.assertEqual(self.result()['route'], 'retain_proposal')
        context = self.bound.context.model_copy(update=dict(expected=
            self.bound.context.expected.model_copy(update=dict(required_axes=('ownership',)))))
        self.bound = bind(context, state_json=self.bound.state_json, questions_json=self.bound.questions_json)
        row = self.result()
        self.assertEqual(row['baseline_route'], 'retain_proposal')
        self.assertEqual(row['route'], 'ordinary_review')
        self.assertIn('ownership', [a['axis'] for a in row['axes']])

    def test_existing_review_cannot_be_cancelled_by_concentrated_masses(self):
        answer = self.body['answers']['evidence_confidence']
        answer['choice'] = 'limited'
        answer['probabilities'] = dict(supported=0.0, limited=1.0, insufficient=0.0)
        row = self.result()
        self.assertEqual(row['baseline_route'], 'ordinary_review')
        self.assertEqual(row['route'], 'ordinary_review')
        self.assertIn(dict(name='ExistingReviewSpec', outcome='satisfied'), row['trace'])
        self.assertFalse(any(event['name'] == 'NoStrictMajoritySpec'
                             and event['outcome'] in ('satisfied', 'unsatisfied') for event in row['trace']))
        self.assertTrue(row['baseline_review_request_prepared'])
        self.assertFalse(row['shadow_review_request_prepared'])

    def test_protocol_failure_stops_before_semantic_review(self):
        for raw, status in [(None, 200), (b'{', 200), (b'{}', 500)]:
            with self.subTest(raw=raw, status=status):
                row = evaluate(self.bound, raw, http_status=status)
                self.assertEqual(row['route'], 'stop_incomplete')
                self.assertIn(dict(name='IncompleteCaptureSpec', outcome='satisfied'), row['trace'])
                self.assertFalse(row['shadow_review_request_prepared'])

    def test_invalid_native_metadata_is_not_semantic_doubt(self):
        original = copy.deepcopy(self.body)
        for mutation in ('missing_axis', 'wrong_model', 'bad_mass', 'nonfinite', 'wrong_choice'):
            self.body = copy.deepcopy(original)
            if mutation == 'missing_axis':
                del self.body['answers']['concern_kind']
            elif mutation == 'wrong_model':
                self.body['model'] = 'another-model'
            elif mutation == 'bad_mass':
                self.masses('concern_kind', policy=0.1, mechanics=0.0, variant_behavior=0.0, unknown=0.0)
            elif mutation == 'nonfinite':
                self.body['answers']['concern_kind']['probabilities']['policy'] = float('nan')
            else:
                self.body['answers']['concern_kind']['choice'] = 'invented'
            with self.subTest(mutation=mutation):
                row = evaluate(self.bound, json.dumps(self.body).encode())
                self.assertEqual(row['route'], 'stop_incomplete')

    def test_unknown_category_keeps_original_review_even_with_full_mass(self):
        answer = self.body['answers']['concern_kind']
        answer['choice'] = 'unknown'
        answer['probabilities'] = dict(policy=0.0, mechanics=0.0, variant_behavior=0.0, unknown=1.0)
        self.assertEqual(self.result()['route'], 'ordinary_review')

    def test_low_native_scalar_alone_is_explicitly_not_a_v1_signal(self):
        for answer in self.body['answers'].values():
            answer['confidence'] = 0.01
        row = self.result()
        self.assertEqual(row['route'], 'retain_proposal')
        self.assertEqual(row['axes'][0]['reported_confidence'], 0.01)

    def test_profile_and_source_binding_cannot_be_silently_changed(self):
        self.bound = type(self.bound)(self.bound.context, self.bound.state_json + ' ', self.bound.questions_json)
        with self.assertRaises(ValueError):
            self.result()
        self.bound = bound_task('D01')
        self.bound = type(self.bound)(self.bound.context.model_copy(update=dict(expected_model='ordinary')),
                                     self.bound.state_json, self.bound.questions_json)
        with self.assertRaises(ValueError):
            self.result()

    def test_new_route_has_no_dispatch_or_acceptance_authority(self):
        row = self.result()
        self.assertEqual(row['hosted_requests'], 0)
        self.assertEqual(row['review_execution'], 'not_run')
        self.assertFalse(row['shadow_review_request_prepared'])
        self.assertFalse(row['automatic_fact_acceptance'])
        self.assertFalse(row['write_authority'])
        self.assertFalse(row['transport_verified'])
        self.assertEqual(row['metric_effect'], 'none')
        self.assertIsNone(row['semantic_accuracy'])


if __name__ == '__main__':
    unittest.main()
