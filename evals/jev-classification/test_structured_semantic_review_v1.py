import copy
import base64
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from typing import get_args

from recommendation_policy_v1.context import Source
from semantic_review_routing_v1.context import (
    CapturedAssessment, CheckedClaim, DecisionBinding, EvidenceGap, Labels, RoutingContext,
)
from structured_semantic_review_v1 import inspect
from structured_semantic_review_v1.preparation import (
    CONTRACT, MAX_RESPONSE_BYTES, MODEL, encoded, prepare, request_body, request_sha256, sha,
)


def inputs(*, role='policy', support='insufficient', owner='unknown', tool='unknown', missing=(), action='assess_role'):
    code = 'def publish(record):\n    return record["approved"] and record["active"]\n'
    state = dict(architecture_profile=dict(goal='Uniform named and observable domain decisions.'),
        evaluation_scope=dict(repository='example/project', revision='a' * 40),
        target=dict(id='publication-rule', source=dict(code=code, path='src/publication.py', revision='a' * 40,
            start_line=10, end_line=11, excerpt_sha256='sha256:' + sha(code.encode()))), retrieved_context=[])
    questions = {axis: dict(instructions='Classify the exact decision from the supplied evidence.',
                            criteria={value: 'Definition of ' + value for value in get_args(field.annotation)})
                 for axis, field in Labels.model_fields.items()}
    raw_state, raw_questions = encoded(state), encoded(questions)
    binding = DecisionBinding(repository='example/project', revision='a' * 40, path='src/publication.py',
        start_line=10, end_line=11, decision_id='publication-rule', evidence_sha256=sha(raw_state.encode()),
        rubric_version='fixture-v1', category_version='four-axis-choice-v1',
        prompt_config_sha256=sha(json.dumps(questions, sort_keys=True).encode()), action=action)
    captured = CapturedAssessment(status='valid', provider='jev-coreinfra', requested_model='jev-1.13.0',
        returned_model='jev-1.13.0', binding=binding, response_sha256='d' * 64,
        labels=Labels(concern_kind=role, evidence_confidence=support, ownership=owner, tool_responsibility=tool))
    context = RoutingContext(expected=binding, expected_provider='jev-coreinfra', expected_model='jev-1.13.0',
                             assessment=captured, missing_premises=missing)
    return context, raw_state, raw_questions


def task(**kwargs):
    original, state, questions = inputs(**kwargs)
    return prepare(original, state_json=state, questions_json=questions)


def answer(prepared, **labels):
    source = prepared.fragments[0]
    values = dict(concern_kind='policy', evidence_confidence='supported', ownership='unknown', tool_responsibility='unknown')
    values.update(labels)
    return dict(contract=CONTRACT, task_sha256=prepared.task_sha256(),
        decision_binding_sha256=prepared.original.expected.fingerprint(), labels=values,
        citations=[dict(axis='concern_kind', fragment_id='target/source', start_line=source.start_line,
                        end_line=source.end_line, quote=source.code)],
        missing_evidence=[], rationale='The supplied scenario makes publication conditional on approval and active state.')


def response(value):
    return dict(id='synthetic-response', object='response', model=MODEL, status='completed',
        usage=dict(input_tokens=100, output_tokens=50),
        output=[dict(type='message', role='assistant', status='completed',
                     content=[dict(type='output_text', text=encoded(value))])])


def inspect_answer(prepared, value):
    return inspect(prepared, encoded(response(value)).encode(), captured_request_sha256=request_sha256(prepared))


class PreparationTests(unittest.TestCase):
    def test_real_selected_specgraph_view_prepares_without_relabeling_or_inference(self):
        from replay_semantic_review_routing_v1 import read_pinned_run, replay
        row = next(c for c in replay()['cases'] if c['provider'] == 'jev-coreinfra'
                   and c['route']['route'] == 'ordinary_review')
        routing = row['route']
        context = RoutingContext.model_validate_json(encoded(dict(expected=routing['binding'],
            expected_provider=routing['expected_provider'], expected_model=routing['expected_model'],
            assessment=routing['original_assessment'])))
        requests, _ = read_pinned_run()
        wire = json.loads(requests[row['request_id']]['wire_json'])
        with patch('socket.socket.connect', side_effect=AssertionError('offline only')):
            prepared = prepare(context, state_json=wire['state'], questions_json=encoded(wire['questions']))
        self.assertEqual(prepared.original.assessment.labels.evidence_confidence, 'insufficient')
        self.assertEqual(prepared.fragments[0].path, 'tools/product_workspace_next_moves_support.py')
        self.assertEqual(len(prepared.fragments), 1)
        self.assertEqual(json.loads(request_body(prepared)['input'])['state'], json.loads(wire['state']))
        # A hand-authored response exercises structural resolution, not model quality.
        self.assertEqual(inspect_answer(prepared, answer(prepared))['status'], 'resolved_proposal')

    def test_request_keeps_original_evidence_and_guidance_without_previous_answers(self):
        prepared = task()
        payload = request_body(prepared)
        state = json.loads(payload['input'])
        self.assertEqual(state['state'], json.loads(prepared.state_json))
        self.assertNotIn('original_assessment', state)
        self.assertNotIn('labels', state)
        self.assertNotIn('sol_labels', state)
        self.assertIn('Uniform named and observable', payload['input'])
        self.assertIn(prepared.questions_json, payload['instructions'])
        self.assertEqual(payload['model'], MODEL)
        self.assertEqual(payload['reasoning'], {'effort': 'low'})
        self.assertFalse(payload['store'])
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['truncation'], 'disabled')
        self.assertTrue(payload['text']['format']['strict'])
        schema = payload['text']['format']['schema']
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(schema['required']), set(schema['properties']))
        self.assertEqual(payload, request_body(prepared))
        payload['input'] = 'modified by caller'
        self.assertNotEqual(payload, request_body(prepared))

    def test_non_selected_or_operationally_incomplete_input_is_rejected(self):
        for support, change in [('supported', {}), ('insufficient', {'status': 'transport_failed'})]:
            original, state, questions = inputs(support=support)
            if change:
                original = original.model_copy(update={'assessment': original.assessment.model_copy(update=change)})
            with self.assertRaisesRegex(ValueError, 'not selected'):
                prepare(original, state_json=state, questions_json=questions)

    def test_state_question_and_preparation_tampering_is_rejected(self):
        original, state, questions = inputs()
        for kwargs in [dict(state_json=state + ' ', questions_json=questions),
                       dict(state_json=state, questions_json='{}')]:
            with self.assertRaises(ValueError):
                prepare(original, **kwargs)
        prepared = prepare(original, state_json=state, questions_json=questions)
        with self.assertRaisesRegex(ValueError, 'modified'):
            request_body(replace(prepared, fragments=()))

    def test_source_identity_span_digest_and_architectural_goal_are_required(self):
        original, state, questions = inputs()
        raw = json.loads(state)
        mutations = [lambda s: s['target']['source'].update(excerpt_sha256='f' * 64),
                     lambda s: s['target']['source'].update(end_line=12),
                     lambda s: s['target']['source'].update(revision='f' * 40),
                     lambda s: s['target'].update(id='other'),
                     lambda s: s.update(architecture_profile={})]
        for mutate in mutations:
            altered = copy.deepcopy(raw)
            mutate(altered)
            changed_state = encoded(altered)
            binding = original.expected.model_copy(update={'evidence_sha256': sha(changed_state.encode())})
            context = original.model_copy(update={'expected': binding, 'assessment':
                                                  original.assessment.model_copy(update={'binding': binding})})
            with self.assertRaises(ValueError):
                prepare(context, state_json=changed_state, questions_json=questions)

    def test_category_drift_cannot_hide_behind_a_valid_configuration_hash(self):
        original, state, questions = inputs()
        values = json.loads(questions)
        values['ownership']['criteria']['absent_in_scope'] = 'Not a supported model label'
        binding = original.expected.model_copy(update={'prompt_config_sha256':
            sha(json.dumps(values, sort_keys=True).encode())})
        context = original.model_copy(update={'expected': binding,
            'assessment': original.assessment.model_copy(update={'binding': binding})})
        with self.assertRaisesRegex(ValueError, 'category set'):
            prepare(context, state_json=state, questions_json=encoded(values))

    def test_malformed_captured_state_fails_at_preparation(self):
        original, state, questions = inputs()
        incomplete = json.loads(state)
        incomplete['target']['source'].pop('excerpt_sha256')
        bad_span = json.loads(state)
        bad_span['target']['source']['start_line'] = '10'
        for raw in ('[]', encoded(incomplete), encoded(bad_span)):
            binding = original.expected.model_copy(update={'evidence_sha256': sha(raw.encode())})
            context = original.model_copy(update={'expected': binding,
                'assessment': original.assessment.model_copy(update={'binding': binding})})
            with self.assertRaises(ValueError):
                prepare(context, state_json=raw, questions_json=questions)


class ResolutionTests(unittest.TestCase):
    def test_exact_retrieval_quote_alone_cannot_establish_the_target_role(self):
        original, state, questions = inputs()
        raw = json.loads(state)
        source = dict(raw['target']['source'], path='src/similar_rule.py')
        raw['retrieved_context'] = [dict(source=source)]
        state = encoded(raw)
        binding = original.expected.model_copy(update={'evidence_sha256': sha(state.encode())})
        context = original.model_copy(update={'expected': binding,
            'assessment': original.assessment.model_copy(update={'binding': binding})})
        prepared = prepare(context, state_json=state, questions_json=questions)
        value = answer(prepared)
        value['citations'][0]['fragment_id'] = 'retrieved_context/0/source'
        result = inspect_answer(prepared, value)
        self.assertTrue(result['source_locators_verified'])
        self.assertFalse(result['required_citation_coverage_verified'])
        self.assertEqual(result['status'], 'needs_review')

    def test_supported_same_role_with_exact_quote_resolves_only_a_proposal(self):
        prepared = task()
        with patch('socket.socket.connect', side_effect=AssertionError('offline only')):
            result = inspect_answer(prepared, answer(prepared))
        self.assertEqual(result['status'], 'resolved_proposal')
        self.assertEqual(result['disposition'], 'proposed_not_accepted')
        self.assertEqual(result['review_status'], 'completed')
        self.assertTrue(result['source_locators_verified'])
        self.assertTrue(result['required_citation_coverage_verified'])
        self.assertEqual(result['findings'], [])
        self.assertFalse(result['automatic_fact_acceptance'])
        self.assertFalse(result['write_authority'])
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertFalse(result['transport_verified'])
        self.assertEqual(result['metric_effect'], 'none')
        self.assertEqual(result['hosted_requests'], 0)
        self.assertEqual(result['returned_model'], MODEL)
        self.assertEqual(result['reported_usage'], {'input_tokens': 100, 'output_tokens': 50})
        self.assertIsNone(result['billed_cost'])
        self.assertIn({'name': 'ReviewResolvedSpec', 'outcome': 'satisfied'}, result['trace'])
        self.assertEqual(result['original_assessment']['labels']['evidence_confidence'], 'insufficient')

    def test_unknown_role_can_be_resolved_with_new_supported_evidence(self):
        prepared = task(role='unknown')
        result = inspect_answer(prepared, answer(prepared))
        self.assertEqual(result['status'], 'resolved_proposal')
        self.assertNotIn('material_disagreement', [f['reason'] for f in result['findings']])

    def test_known_role_disagreement_is_not_resolved_by_a_larger_model(self):
        prepared = task()
        result = inspect_answer(prepared, answer(prepared, concern_kind='mechanics'))
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('material_disagreement', [f['reason'] for f in result['findings']])

    def test_unknown_or_limited_reviewer_support_remains_unresolved(self):
        for role, support in [('unknown', 'insufficient'), ('policy', 'limited'), ('policy', 'insufficient')]:
            prepared = task()
            result = inspect_answer(prepared, answer(prepared, concern_kind=role, evidence_confidence=support))
            self.assertEqual(result['status'], 'needs_review')
            self.assertEqual(result['review_status'], 'completed')
            self.assertIn('unresolved_review_assessment', [f['reason'] for f in result['findings']])

    def test_original_and_new_missing_evidence_are_preserved(self):
        gap = EvidenceGap(id='intent', description='Original intent is missing')
        prepared = task(missing=(gap,))
        value = answer(prepared)
        value['missing_evidence'] = [dict(id='intent', description='Different model description'),
                                     dict(id='owner', description='Owner definition is missing')]
        result = inspect_answer(prepared, value)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual({g['id']: g['description'] for g in result['preserved_missing_evidence']},
                         {'intent': gap.description, 'owner': 'Owner definition is missing'})

    def test_colliding_original_gap_ids_do_not_discard_original_descriptions(self):
        gaps = (EvidenceGap(id='intent', description='Publication intent is missing'),
                EvidenceGap(id='intent', description='Workspace intent is missing'))
        prepared = task(missing=gaps)
        value = answer(prepared)
        value['missing_evidence'] = [dict(id='intent', description='Model replacement')]
        result = inspect_answer(prepared, value)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['preserved_missing_evidence'], [g.model_dump() for g in gaps])

    def test_new_missing_evidence_cannot_resolve_even_with_supported_labels(self):
        prepared = task()
        value = answer(prepared)
        value['missing_evidence'] = [dict(id='intent', description='More intent is needed')]
        self.assertEqual(inspect_answer(prepared, value)['status'], 'needs_review')

    def test_invalid_or_unbound_citations_never_resolve(self):
        prepared = task()
        for change in [dict(quote='hallucinated quote'), dict(fragment_id='not-supplied'),
                       dict(start_line=9), dict(end_line=12), dict(start_line=11, end_line=10),
                       dict(quote=' '), dict(quote=prepared.fragments[0].code.rstrip('\n'))]:
            with self.subTest(change=change):
                value = answer(prepared)
                value['citations'][0].update(change)
                result = inspect_answer(prepared, value)
                self.assertEqual(result['status'], 'needs_review')
                self.assertFalse(result['source_locators_verified'])
                self.assertIn('invalid_citations', [f['reason'] for f in result['findings']])

    def test_no_quotes_do_not_claim_locator_verification(self):
        prepared = task()
        value = answer(prepared)
        value['citations'] = []
        result = inspect_answer(prepared, value)
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse(result['source_locators_verified'])
        self.assertFalse(result['required_citation_coverage_verified'])

    def test_owner_and_tool_claims_need_coverage_and_required_structural_binding(self):
        prepared = task(action='reuse_specification', owner='existing_specification')
        value = answer(prepared, ownership='existing_specification')
        value['citations'].append(dict(value['citations'][0], axis='ownership'))
        result = inspect_answer(prepared, value)
        self.assertTrue(result['source_locators_verified'])
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('required_evidence_missing', [f['reason'] for f in result['review_route']['findings']])
        value = answer(task(), tool_responsibility='yes')
        ordinary = task()
        result = inspect_answer(ordinary, value)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('missing_citation_coverage', [f['reason'] for f in result['findings']])

    def test_losing_a_known_owner_remains_a_material_disagreement(self):
        prepared = task(owner='existing_specification')
        result = inspect_answer(prepared, answer(prepared))
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('material_disagreement', [f['reason'] for f in result['findings']])

    def test_checked_structural_role_can_settle_material_disagreement(self):
        original, state, questions = inputs()
        checked = CheckedClaim(binding_sha256=original.expected.fingerprint(), axis='concern_kind', value='mechanics',
            relation='label_evidence', subject='publication-rule', source=Source(artifact='fixture-contract',
                sha256='e' * 64, locator='scenario-1', authority='reviewed_fact'))
        original = original.model_copy(update={'checked_claims': (checked,)})
        prepared = prepare(original, state_json=state, questions_json=questions)
        result = inspect_answer(prepared, answer(prepared, concern_kind='mechanics'))
        self.assertEqual(result['status'], 'resolved_proposal')
        self.assertFalse(result['semantic_correctness_verified'])


class ResponseFailureTests(unittest.TestCase):
    def test_historical_label_only_response_is_not_a_rich_review(self):
        prepared = task()
        path = Path(__file__).parent / 'runs/2026-10-18-ordinary-luna-live-v1/responses.jsonl'
        old = json.loads(path.read_text().splitlines()[0])
        result = inspect(prepared, base64.b64decode(old['sdk_response_base64']),
                         captured_request_sha256=request_sha256(prepared))
        self.assertEqual(result['status'], 'analysis_incomplete')
        self.assertEqual(result['findings'][0]['reason'], 'invalid_review_response')

    def test_execution_failures_and_budget_exhaustion_are_visible(self):
        prepared = task()
        for status in ('not_run', 'budget_exhausted', 'transport_failed', 'refused', 'truncated', 'invalid'):
            with self.subTest(status=status):
                result = inspect(prepared, None, captured_request_sha256=None, execution_status=status)
                self.assertEqual(result['status'], 'analysis_incomplete')
                self.assertEqual(result['disposition'], 'needs_review')
                self.assertEqual(result['findings'][0]['reason'], status)
                self.assertEqual(result['review_status'], 'not_run' if status in ('not_run', 'budget_exhausted') else 'failed')

    def test_stale_request_task_or_decision_binding_is_rejected(self):
        prepared = task()
        raw = encoded(response(answer(prepared))).encode()
        for digest in (None, 'f' * 64):
            result = inspect(prepared, raw, captured_request_sha256=digest)
            self.assertEqual(result['findings'][0]['reason'], 'review_request_mismatch')
        for field in ('task_sha256', 'decision_binding_sha256'):
            value = answer(prepared)
            value[field] = 'f' * 64
            self.assertEqual(inspect_answer(prepared, value)['findings'][0]['reason'], 'review_binding_mismatch')

    def test_refusal_incomplete_wrong_model_and_multiple_messages_are_distinct(self):
        prepared = task()
        mutations = [
            (lambda b: b.update(model='other'), 'model_identity_mismatch'),
            (lambda b: b.update(status='incomplete'), 'response_incomplete'),
            (lambda b: b.update(incomplete_details={}), 'response_incomplete'),
            (lambda b: b['output'][0]['content'][0].update(type='refusal'), 'response_refused'),
            (lambda b: b['output'].append(copy.deepcopy(b['output'][0])), 'ambiguous_output'),
        ]
        for mutate, reason in mutations:
            body = response(answer(prepared))
            mutate(body)
            result = inspect(prepared, encoded(body).encode(), captured_request_sha256=request_sha256(prepared))
            self.assertEqual(result['status'], 'analysis_incomplete')
            self.assertEqual(result['findings'][0]['reason'], reason)

    def test_malformed_duplicate_nonfinite_and_oversized_response_is_not_an_abstention(self):
        prepared = task()
        valid = encoded(response(answer(prepared))).encode()
        for raw in (None, b'', b'not json', b'\xff', b'{"model":NaN}', b'{"model":0,"model":1}',
                    b' ' * (MAX_RESPONSE_BYTES + 1)):
            result = inspect(prepared, raw, captured_request_sha256=request_sha256(prepared))
            self.assertEqual(result['status'], 'analysis_incomplete')
        body = response(answer(prepared))
        body['output'][0]['content'][0]['text'] = '{"labels":{},"labels":{}}'
        result = inspect(prepared, encoded(body).encode(), captured_request_sha256=request_sha256(prepared))
        self.assertEqual(result['status'], 'analysis_incomplete')
        self.assertEqual(inspect(prepared, valid, captured_request_sha256=request_sha256(prepared))['status'], 'resolved_proposal')

    def test_schema_rejects_synthetic_confidence_invalid_labels_and_blank_rationale(self):
        prepared = task()
        changes = [lambda v: v.update(confidence=0.99), lambda v: v['labels'].update(concern_kind='magic'),
                   lambda v: v.update(rationale=' '), lambda v: v['labels'].update(ownership='absent_in_scope')]
        for mutate in changes:
            value = answer(prepared)
            mutate(value)
            self.assertEqual(inspect_answer(prepared, value)['status'], 'analysis_incomplete')


if __name__ == '__main__':
    unittest.main()
