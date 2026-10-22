import base64
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from categorical_review_bridge_v1 import bind, replay_jev_capture
from native_review_cascade_v1 import plan_capture
from semantic_review_routing_v1.context import EvidenceGap
import specgraph_pr714_live_v1 as historical
import specgraph_pr714_live_v2 as runtime
from pr714_transport_v1 import send as profile_send
from structured_semantic_review_v1.preparation import encoded, prepare, sha
from test_structured_semantic_review_v1 import answer, response
from test_coreinfra_transport import FakeConnection


def captured(case):
    row = historical.read(historical.RUN / f'{case}-jev/response.json')
    raw = base64.b64decode(row['raw_body_base64'], validate=True)
    assert sha(raw) == row['raw_body_sha256']
    return raw


def review_value(plan, **labels):
    values = dict(plan.report()['categorical']['answers'])
    values.update(labels)
    value = answer(plan.review, **values)
    target = next(f for f in plan.review.fragments if f.id == 'target/source')
    value['citations'] = [dict(axis='concern_kind', fragment_id=target.id,
        start_line=target.start_line, end_line=target.end_line, quote=target.code)]
    return value


def rich(plan, **labels):
    return encoded(response(review_value(plan, **labels))).encode()


class NativeCascadeTests(unittest.TestCase):
    def setUp(self):
        network = patch('socket.socket.connect', side_effect=AssertionError('offline only'))
        network.start()
        self.addCleanup(network.stop)
        self.bound = historical.bound_task('D01')
        self.plan = plan_capture(self.bound, captured('D01'))

    def inspect(self, raw, *, plan=None, **kwargs):
        plan = plan or self.plan
        return plan.inspect_review(raw, execution_status='completed',
            captured_request_sha256=plan.report()['review_request_sha256'], **kwargs)

    def test_real_captures_prepare_three_reviews_with_exact_independent_wires(self):
        manifest = historical.expected()
        for case, selected in [('D01', True), ('D02', True), ('D03', True), ('D04', False)]:
            with self.subTest(case=case):
                plan = plan_capture(historical.bound_task(case), captured(case))
                report = plan.report()
                self.assertEqual(report['original_route']['route'], 'retain_proposal')
                self.assertEqual(report['routing']['route'], 'ordinary_review' if selected else 'retain_proposal')
                self.assertEqual(plan.review is not None, selected)
                if selected:
                    frozen = next(r for r in manifest['requests'] if r['id'] == f'{case}-review')
                    self.assertEqual(encoded(plan.review_request()), frozen['wire_json'])
                    payload = json.loads(plan.review_request()['input'])
                    for key in ('labels', 'confidence', 'native_results', 'original_assessment', 'probabilities'):
                        self.assertNotIn(key, payload)
                    self.assertEqual(plan.review.original.assessment.labels.model_dump(mode='json'),
                                     report['categorical']['answers'])
                else:
                    self.assertIsNone(plan.review_request())
                    with self.assertRaisesRegex(ValueError, 'not selected'):
                        plan.inspect_review()

    def test_new_selection_reaches_review_without_faking_old_context(self):
        baseline = replay_jev_capture(self.bound, captured('D01'))
        with self.assertRaisesRegex(ValueError, 'not selected'):
            prepare(baseline.context, state_json=self.bound.state_json, questions_json=self.bound.questions_json)
        self.assertEqual(self.plan.review.original, baseline.context)
        self.assertEqual(self.plan.review.original.missing_premises, ())
        self.assertEqual(self.inspect(rich(self.plan))['status'], 'resolved_proposal')

    def test_material_disagreement_is_explicit_and_keeps_original_assessment(self):
        result = self.inspect(rich(self.plan, concern_kind='policy'))
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('material_disagreement', [f['reason'] for f in result['findings']])
        self.assertEqual(result['original_assessment']['labels']['concern_kind'], 'variant_behavior')
        self.assertEqual(result['review']['labels']['concern_kind'], 'policy')

    def test_same_review_wire_resolves_against_each_actual_first_stage(self):
        body = json.loads(captured('D01'))
        axis = body['answers']['concern_kind']
        axis.update(choice='unknown', probabilities={key: float(key == 'unknown') for key in axis['probabilities']})
        unknown = replace(self.plan, raw=encoded(body).encode())
        self.assertEqual(self.plan.review_request(), unknown.review_request())
        raw = rich(self.plan, concern_kind='policy')
        self.assertEqual(self.inspect(raw)['status'], 'needs_review')
        self.assertEqual(self.inspect(raw, plan=unknown)['status'], 'resolved_proposal')

    def test_missing_evidence_and_invalid_citations_never_resolve(self):
        context = self.bound.context.model_copy(update=dict(missing_premises=(EvidenceGap(
            id='unavailable-intent', description='Intent premise is unavailable.'),)))
        bound = bind(context, state_json=self.bound.state_json, questions_json=self.bound.questions_json)
        plan = plan_capture(bound, captured('D01'))
        self.assertIn('Intent premise is unavailable.', plan.review_request()['input'])
        result = self.inspect(rich(plan), plan=plan)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['preserved_missing_evidence'][0]['id'], 'unavailable-intent')
        value = review_value(self.plan)
        value['citations'][0]['quote'] = 'Not an exact source quote.'
        result = self.inspect(encoded(response(value)).encode())
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse(result['source_locators_verified'])

    def test_unrun_failed_wrong_request_and_bad_task_remain_incomplete(self):
        for status in ('not_run', 'budget_exhausted', 'transport_failed', 'refused', 'truncated', 'invalid'):
            with self.subTest(status=status):
                result = self.plan.inspect_review(execution_status=status)
                self.assertEqual(result['status'], 'analysis_incomplete')
                self.assertEqual(result['disposition'], 'needs_review')
        result = self.plan.inspect_review(rich(self.plan), execution_status='completed', captured_request_sha256='a'*64)
        self.assertEqual(result['findings'][0]['reason'], 'review_request_mismatch')
        value = review_value(self.plan)
        value['task_sha256'] = 'a'*64
        self.assertEqual(self.inspect(encoded(response(value)).encode())['status'], 'analysis_incomplete')

    def test_invalid_native_capture_cannot_prepare_a_paid_fallback(self):
        for raw, status in [(b'{}', 200), (captured('D01'), 500), (None, 200)]:
            plan = plan_capture(self.bound, raw, http_status=status)
            self.assertEqual(plan.report()['routing']['route'], 'stop_incomplete')
            self.assertIsNone(plan.review_request())

    def test_detached_requests_and_stale_binding_cannot_replace_plan_state(self):
        request = self.plan.review_request()
        request['input'] = 'caller mutation'
        self.assertNotEqual(request, self.plan.review_request())
        bound = replace(self.bound, state_json=self.bound.state_json + ' ')
        with self.assertRaises(ValueError):
            replace(self.plan, bound=bound)


class NativeCascadeRuntimeTests(unittest.TestCase):
    def approval(self, prep, path):
        runtime.write(path, dict(schema_version=1, study=runtime.STUDY,
            approval_kind="explicit_user_approval", approved_by="synthetic offline fixture",
            approval_reference="unit test only; not a live approval",
            manifest_sha256=sha((prep/'manifest.json').read_bytes()),
            preparation_identity_sha256=sha(str(prep.resolve()).encode()),
            max_logical_requests=8, max_network_attempts=24, max_possible_posts=8))
        return path

    def synthetic_dispatch(self, directory, timeout):
        request = runtime.read(directory/'request.json')
        case = request['case']
        if request['kind'] == 'jev':
            raw = captured(case)
        else:
            plan = plan_capture(runtime.bound_task(case), captured(case))
            raw = (b'{"status":"incomplete","model":"gpt-6-luna","output":[]}' if case == 'D03'
                   else rich(plan, **(dict(concern_kind='policy') if case == 'D02' else {})))
        def sender(endpoint, wire, key, *, emit):
            self.assertEqual(endpoint, request['endpoint'])
            self.assertEqual(wire.decode(), request['wire_json'])
            return profile_send(endpoint, wire, key, emit=emit,
                connection_factory=lambda timeout: FakeConnection(body=raw))
        # Exercise the actual v2 worker/lease/capture path and bounded transport,
        # substituting only the HTTPS connection; no sockets or provider calls.
        with patch.object(runtime, 'send', side_effect=sender):
            runtime.worker(directory)
        runtime.write(directory/'execution.json', dict(child_exit_code=0, hard_timeout=False,
            wall_seconds=0.01, hard_limit_seconds=timeout))

    def test_full_runtime_selects_three_reviews_and_preserves_all_dispositions(self):
        with tempfile.TemporaryDirectory() as td, patch.dict('os.environ', COREINFRA_API_KEY='unit-test-key-not-in-payloads'), patch(
                'socket.socket.connect', side_effect=AssertionError('offline only')):
            prep, run = Path(td)/'prep', Path(td)/'run'
            runtime.freeze(prep)
            authorization = self.approval(prep, Path(td)/'approval.json')
            self.assertFalse(runtime.run(prep, run)['inference'])
            self.assertFalse(run.exists())
            result = runtime.run(prep, run, live=True, authorization=authorization, dispatcher=self.synthetic_dispatch)
            self.assertEqual(result['logical_requests'], 7)
            report = runtime.analyze(prep, run)
            self.assertEqual(report['selected_reviews'], 3)
            self.assertEqual({row['case']: row['status'] for row in report['cases']}, dict(
                D01='resolved_proposal', D02='needs_review', D03='analysis_incomplete', D04='proposed_not_accepted'))
            self.assertFalse(report['automatic_fact_acceptance'])
            runtime.save_report(prep, run)
            self.assertTrue(runtime.verify_result(prep, run)['verified'])
            saved_approval = (run/'authorization.json').read_bytes()
            changed_approval = runtime.read(run/'authorization.json')
            changed_approval['approval_reference'] = 'different approval'
            (run/'authorization.json').write_text(encoded(changed_approval))
            with patch.object(runtime, 'send') as send:
                with self.assertRaisesRegex(ValueError, 'dispatch lease differs'):
                    runtime.worker(run/'D01-jev')
                send.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'authorization differs'):
                runtime.analyze(prep, run)
            (run/'authorization.json').write_bytes(saved_approval)
            rendered = (run/'report.md').read_text()
            self.assertIn('Axes without strict majority: concern_kind', rendered)
            self.assertIn('material_disagreement', rendered)
            with self.assertRaisesRegex(ValueError, 'already spent'):
                runtime.run(prep, Path(td)/'another', live=True, authorization=authorization, dispatcher=self.synthetic_dispatch)
            (run/'D04-review').mkdir()
            with self.assertRaisesRegex(ValueError, 'unselected review'):
                runtime.analyze(prep, run)

    def test_v1_spent_preparation_is_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as td, patch('socket.socket.connect', side_effect=AssertionError('offline')):
            with self.assertRaisesRegex(ValueError, 'frozen request'):
                runtime.run(historical.PREPARATION, Path(td)/'run')

    def test_live_flag_and_key_do_not_authorize_a_preparation(self):
        with tempfile.TemporaryDirectory() as td, patch.dict('os.environ', COREINFRA_API_KEY='test-key'), patch.object(runtime, 'dispatch') as dispatch:
            prep, run = Path(td)/'prep', Path(td)/'run'
            runtime.freeze(prep)
            with self.assertRaisesRegex(ValueError, 'authorization artifact required'):
                runtime.run(prep, run, live=True, dispatcher=dispatch)
            dispatch.assert_not_called()
            self.assertFalse(run.exists())
            self.assertFalse((prep/'dispatch-reservation.json').exists())
            auth = self.approval(prep, Path(td)/'approval.json')
            good = runtime.read(auth)
            for changes in [dict(manifest_sha256='0'*64), dict(max_logical_requests=9),
                            dict(schema_version=True), dict(approval_reference=''),
                            dict(preparation_identity_sha256='0'*64)]:
                auth.write_text(encoded(dict(good, **changes)))
                with self.assertRaises(ValueError):
                    runtime.run(prep, run, live=True, authorization=auth, dispatcher=dispatch)
                self.assertFalse(run.exists())
                self.assertFalse((prep/'dispatch-reservation.json').exists())
            auth.write_text(encoded(good))
            other = Path(td)/'other-prep'
            runtime.freeze(other)
            with self.assertRaisesRegex(ValueError, 'scope or budget'):
                runtime.run(other, run, live=True, authorization=auth, dispatcher=dispatch)
            dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
