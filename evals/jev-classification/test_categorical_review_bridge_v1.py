import base64
import copy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx2
from mellea_jev import (
    CapabilityMismatchError, CategoricalResult, ResponsesChoiceProvider,
    TypeSafeCategoricalProvider, TypeSafeProvider,
)

import categorical_luna_pilot_v1 as ordinary
from categorical_review_bridge_v1 import bind, categorical_plan, replay_jev_capture
from categorical_review_bridge_v1.native_batch import NativeBatchCategoricalProvider
from replay_categorical_review_v1 import case_input, replay, saved_review
from replay_semantic_review_routing_v1 import read_pinned_run
from semantic_review_routing_v1.context import CapturedAssessment, EvidenceGap
from structured_semantic_review_v1.preparation import encoded, request_sha256, sha


ROOT = Path(__file__).resolve().parent


class CategoricalBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests, responses = read_pinned_run()
        cls.item = next(v for v in requests.values() if v['provider'] == 'jev-coreinfra'
                        and v['case_id'] == 'R04' and v['arm'] == 'baseline')
        cls.row = next(r for r in responses if r['request_id'] == cls.item['request_id'])
        cls.raw = base64.b64decode(cls.row['raw_body_base64'], validate=True)

    def bound(self):
        return case_input(self.item)

    def sdk_result(self):
        return CategoricalResult(answers=dict(concern_kind='policy', evidence_confidence='insufficient',
            ownership='unknown', tool_responsibility='unknown'),
            requested_model='jev-1.13.0', returned_model='jev-1.13.0')

    def test_saved_cohort_keeps_seven_proposals_and_one_review_without_network(self):
        with patch.dict('os.environ', {}, clear=True), patch('socket.socket.connect', side_effect=AssertionError('offline')):
            report, plans = replay()
        self.assertEqual(report['counts'], dict(retain_proposal=7, ordinary_review=1, stop_incomplete=0))
        self.assertEqual(len(plans), 8)
        self.assertEqual(report['hosted_requests'], 0)
        for case in report['cases']:
            result = case['report']
            self.assertFalse(result['automatic_fact_acceptance'])
            self.assertFalse(result['transport_verified'])
            self.assertEqual(set(result['categorical']['native_results']), set(self.sdk_result().answers))
            self.assertEqual(result['categorical']['reported_usage']['cost_usd'], None)
            if result['original_route']['route'] == 'retain_proposal':
                self.assertEqual(result['review_status'], 'not_needed')
                self.assertIsNone(plans[case['request_id']].review_request())

    def test_batch_is_one_request_preserves_native_evidence_and_borrows_lifetime(self):
        calls = []
        task = self.bound().sdk_task()

        def handle(request):
            calls.append(json.loads(request.content))
            return httpx2.Response(200, content=self.raw, headers={'x-typesafe-request-id': 'offline-native-id'})

        with TypeSafeProvider(api_key='offline-fixture', model='jev-1.13.0',
                transport=httpx2.MockTransport(handle)) as provider:
            with patch.object(provider, 'close', wraps=provider.close) as close:
                adapter = NativeBatchCategoricalProvider(provider)
                result = adapter.classify(task)
                close.assert_not_called()
            # The adapter has neither closed the caller's provider nor split the batch.
            self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['state'], task.state)
        self.assertEqual(list(calls[0]['questions']), list(task.questions))
        self.assertEqual(result.request_id, 'offline-native-id')
        body = json.loads(self.raw)
        self.assertEqual(result.usage.input_tokens, body['usage']['input_tokens'])
        for axis, native in result.native_results.items():
            self.assertEqual(native.probabilities, body['answers'][axis]['probabilities'])
            self.assertEqual(native.confidence, body['answers'][axis]['confidence'])
        self.assertTrue(adapter.capabilities.shared_state_batch)

    def test_sdk_single_question_wrapper_rejects_four_axes_before_dispatch(self):
        calls = []
        with TypeSafeProvider(api_key='offline-fixture', transport=httpx2.MockTransport(
                lambda request: calls.append(request))) as provider:
            with self.assertRaises(CapabilityMismatchError):
                TypeSafeCategoricalProvider(provider).classify(self.bound().sdk_task())
        self.assertEqual(calls, [])

    def test_selected_task_matches_previous_rich_pilot_and_replays_its_real_response(self):
        plan = replay_jev_capture(self.bound(), self.raw)
        run = ROOT / 'runs/2026-10-18-structured-luna-review-live-v1'
        receipt = (run / 'result-receipt.json').read_bytes()
        self.assertEqual(sha(receipt), '25bc5df1412d62b8daf1ee2d129bc9e3e39161c4816d486e5dea36f905eedcbd')
        files = json.loads(receipt)['file_sha256']
        for name in ('manifest.json', 'response.json'):
            self.assertEqual(sha((run / name).read_bytes()), files[name])
        manifest = json.loads((run / 'manifest.json').read_bytes())
        self.assertEqual(request_sha256(plan.review), manifest['request_sha256'])
        self.assertEqual(encoded(plan.review_request()), manifest['request_json'])
        row = json.loads((run / 'response.json').read_bytes())
        result = plan.inspect_review(base64.b64decode(row['raw_body_base64']),
            captured_request_sha256=row['request_sha256'], execution_status='completed')
        self.assertEqual((result['status'], result['review_status']), ('needs_review', 'completed'))
        self.assertEqual(result['review']['labels']['evidence_confidence'], 'limited')
        self.assertTrue(result['source_locators_verified'])
        self.assertEqual(plan.inspect_review()['review_status'], 'not_run')

    def test_complete_cascade_reuses_only_matching_saved_review_without_dispatch(self):
        with patch('socket.socket.connect', side_effect=AssertionError('offline only')):
            report, _ = replay(reuse_saved_review=True)
        self.assertEqual(report['reused_reviews'], 1)
        self.assertEqual(report['hosted_requests'], 0)
        reviewed = next(c['report'] for c in report['cases'] if 'review_inspection' in c['report'])
        self.assertEqual(reviewed['review_status'], 'completed')
        self.assertEqual(reviewed['review_inspection']['status'], 'needs_review')

    def test_native_distribution_mutation_does_not_become_a_valid_categorical_capture(self):
        bound = self.bound()
        with TypeSafeProvider(api_key='offline-fixture', model='jev-1.13.0',
                transport=httpx2.MockTransport(lambda request: httpx2.Response(200, content=self.raw))) as provider:
            result = NativeBatchCategoricalProvider(provider).classify(bound.sdk_task())
        result.native_results['concern_kind'].probabilities['policy'] = float('nan')
        plan = categorical_plan(bound, result, response_sha256=sha(self.raw))
        self.assertEqual(plan.report()['original_route']['status'], 'analysis_incomplete')
        self.assertEqual(plan.report()['categorical']['diagnostic'], 'invalid_native_projection')
        self.assertIsNone(plan.review)

    def test_changed_task_cannot_reuse_previous_rich_review(self):
        bound = self.bound()
        context = bound.context.model_copy(update=dict(missing_premises=(
            EvidenceGap(id='new-gap', description='Different task evidence requirement.'),)))
        changed = bind(context, state_json=bound.state_json, questions_json=bound.questions_json)
        plan = replay_jev_capture(changed, self.raw)
        with self.assertRaisesRegex(ValueError, 'different task'):
            saved_review(plan)

    def test_same_review_request_cannot_replace_the_original_assessment(self):
        from test_rich_review_pilot_v1 import response
        known = categorical_plan(self.bound(), self.sdk_result(), response_sha256=sha(self.raw))
        unknown_result = replace(self.sdk_result(), answers=dict(self.sdk_result().answers, concern_kind='unknown'))
        unknown = categorical_plan(self.bound(), unknown_result, response_sha256=sha(self.raw))
        self.assertEqual(request_sha256(known.review), request_sha256(unknown.review))
        raw = response(unknown.review, role='mechanics')
        for plan, status in ((known, 'needs_review'), (unknown, 'resolved_proposal')):
            result = plan.inspect_review(raw, captured_request_sha256=request_sha256(plan.review),
                                         execution_status='completed')
            self.assertEqual(result['status'], status)
        with self.assertRaisesRegex(ValueError, 'review context differs'):
            replace(known, review=unknown.review)
        # Every consumer revalidates even an object mutated outside frozen APIs.
        mixed = copy.copy(known)
        object.__setattr__(mixed, 'review', unknown.review)
        for consume in (mixed.report, mixed.review_request, mixed.inspect_review, lambda: mixed.context):
            with self.subTest(consumer=consume), self.assertRaisesRegex(ValueError, 'review context differs'):
                consume()

    def test_plan_rejects_capture_snapshot_and_route_selection_mixups(self):
        plan = categorical_plan(self.bound(), self.sdk_result(), response_sha256=sha(self.raw))
        original = json.loads(plan.categorical_json)
        changes = (dict(status='not_run'), dict(response_sha256='f' * 64), dict(requested_model='other'),
                   dict(answers=dict(original['answers'], concern_kind='unknown')))
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(plan, categorical_json=encoded(dict(original, **change)))
        with self.assertRaisesRegex(ValueError, 'review selection differs'):
            replace(plan, review=None)
        retained = categorical_plan(self.bound(), replace(self.sdk_result(), answers=dict(
            self.sdk_result().answers, evidence_confidence='supported')), response_sha256=sha(self.raw))
        with self.assertRaisesRegex(ValueError, 'review selection differs'):
            replace(retained, review=plan.review)

    def test_sdk_mass_rejection_is_not_normalized_or_escalated_as_semantic_doubt(self):
        body = json.loads(self.raw)
        answer = body['answers']['concern_kind']
        answer['probabilities'][answer['choice']] -= 0.005
        raw = encoded(body).encode()
        # The historical parser has a distinct, explicitly scoped 1% allowance.
        from retrieval_fact_adapter_v1.native import parse_response
        old = parse_response(raw, provider='jev-coreinfra', model='jev-1.13.0')
        self.assertTrue(old['warnings'])
        plan = replay_jev_capture(self.bound(), raw)
        self.assertEqual(plan.report()['categorical']['diagnostic'], 'JevProtocolError')
        self.assertEqual(plan.report()['original_route']['route'], 'stop_incomplete')
        self.assertIsNone(plan.review)

    def test_model_http_and_sdk_failures_stop_without_semantic_fallback(self):
        wrong_model = json.loads(self.raw)
        wrong_model['model'] = 'other-model'
        wrong_catalog = json.loads(self.raw)
        del wrong_catalog['answers']['ownership']
        for raw, kwargs in ((encoded(wrong_model).encode(), {}), (encoded(wrong_catalog).encode(), {}),
                            (b'secret must not be logged', dict(http_status=401)), (None, {}),
                            (b'{"model":1,"model":2}', {})):
            with self.subTest(kwargs=kwargs, raw=raw is None):
                plan = replay_jev_capture(self.bound(), raw, **kwargs)
                report = plan.report()
                self.assertEqual(report['original_route']['route'], 'stop_incomplete')
                self.assertEqual(report['review_status'], 'not_run')
                self.assertIsNone(plan.review_request())
                self.assertNotIn('secret must not be logged', encoded(report))
                with self.assertRaises(ValueError):
                    plan.inspect_review()

    def test_categorical_label_or_metadata_errors_are_incomplete(self):
        for result in (replace(self.sdk_result(), answers={'wrong_axis': 'policy'}),
                       replace(self.sdk_result(), requested_model=None),
                       replace(self.sdk_result(), returned_model=None),
                       replace(self.sdk_result(), requested_model='wrong-model')):
            plan = categorical_plan(self.bound(), result, response_sha256=sha(self.raw))
            self.assertEqual(plan.report()['original_route']['status'], 'analysis_incomplete')
            self.assertIsNone(plan.review)

    def test_stale_task_source_and_question_inputs_fail_before_replay(self):
        original = self.bound()
        for state, questions in ((original.state_json + ' ', original.questions_json),
                                 (original.state_json, '{}')):
            with self.assertRaises(ValueError):
                bind(original.context, state_json=state, questions_json=questions)
        state = json.loads(original.state_json)
        state['target']['source']['path'] = 'different.py'
        raw = encoded(state)
        expected = original.context.expected.model_copy(update=dict(evidence_sha256=sha(raw.encode())))
        with self.assertRaises(ValueError):
            bind(original.context.model_copy(update=dict(expected=expected)),
                 state_json=raw, questions_json=original.questions_json)
        with self.assertRaises(ValueError):
            replay_jev_capture(replace(original, state_json=original.state_json + ' '), self.raw)

    def test_unresolved_premises_and_original_labels_survive_categorical_adaptation(self):
        bound = self.bound()
        context = bound.context.model_copy(update=dict(missing_premises=(
            EvidenceGap(id='intent', description='Intent document is missing.'),)))
        bound = bind(context, state_json=bound.state_json, questions_json=bound.questions_json)
        plan = categorical_plan(bound, self.sdk_result(), response_sha256=sha(self.raw))
        self.assertEqual(plan.report()['original_route']['original_assessment']['labels']['evidence_confidence'], 'insufficient')
        self.assertEqual(plan.review.original.missing_premises[0].id, 'intent')
        request = plan.review_request()
        state = json.loads(request['input'])
        self.assertNotIn('original_assessment', state)
        self.assertNotIn('labels', state)
        self.assertIn('Intent document is missing.', request['input'])
        detached = plan.report()
        detached['categorical']['answers']['concern_kind'] = 'mechanics'
        self.assertEqual(plan.report()['categorical']['answers']['concern_kind'], 'policy')

    def test_ordinary_sdk_results_use_same_router_without_native_probabilities(self):
        original = self.bound()
        context = original.context.model_copy(update=dict(expected_provider='luna-responses-coreinfra',
            expected_model='gpt-6-luna', assessment=CapturedAssessment(status='not_run',
                provider='luna-responses-coreinfra', requested_model='gpt-6-luna')))
        bound = bind(context, state_json=original.state_json, questions_json=original.questions_json)
        labels = dict(self.sdk_result().answers)
        raw = ordinary.envelope(labels)
        with ordinary.provider(key=ordinary.OFFLINE_KEY,
                transport=httpx2.MockTransport(lambda request: httpx2.Response(200, content=raw))) as client:
            result = client.classify(bound.sdk_task())
        self.assertIsInstance(client, ResponsesChoiceProvider)
        plan = categorical_plan(bound, result, response_sha256=sha(raw))
        self.assertEqual(plan.report()['original_route']['route'], 'ordinary_review')
        self.assertIsNone(plan.report()['categorical']['native_results'])
        self.assertNotIn('confidence', plan.report()['categorical'])


def load_tests(loader, tests, pattern):
    # Named current-SDK CI invocation also checks the new offline source packets.
    # Discovery already finds that module, so do not duplicate it there.
    if pattern is None:
        from test_specgraph_pr714_preparation_v1 import BridgePreparationTests
        tests.addTests(loader.loadTestsFromTestCase(BridgePreparationTests))
        from test_specgraph_pr714_preparation_v2 import BridgePreparationTests as V2BridgePreparationTests
        tests.addTests(loader.loadTestsFromTestCase(V2BridgePreparationTests))
    return tests


if __name__ == '__main__':
    unittest.main()
