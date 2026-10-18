import itertools
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from semantic_review_routing_v1 import evaluate
from semantic_review_routing_v1.context import (
    CapturedAssessment, CheckedClaim, DecisionBinding, EvidenceGap, Labels, RoutingContext,
)
from recommendation_policy_v1.context import Source


def candidate(*, role='policy', support='supported', owner='unknown', tool='unknown',
              action='assess_role', required_axes=(), status='valid', missing=(), claims=()):
    binding = DecisionBinding(repository='example/project', revision='a' * 40, path='src/rules.py',
        start_line=12, end_line=18, decision_id='decision-1', evidence_sha256='b' * 64,
        rubric_version='rubric-1', category_version='categories-1', prompt_config_sha256='c' * 64,
        action=action, required_axes=required_axes)
    assessment = CapturedAssessment(status=status, provider='jev-coreinfra', requested_model='jev-1.13.0',
        returned_model='jev-1.13.0', response_sha256='d' * 64, binding=binding,
        labels=Labels(concern_kind=role, evidence_confidence=support,
                      ownership=owner, tool_responsibility=tool))
    return RoutingContext(expected=binding, expected_provider='jev-coreinfra', expected_model='jev-1.13.0', assessment=assessment,
                          missing_premises=missing, checked_claims=claims)


def claim(context, axis='ownership', value='existing_specification', relation='exact_decision'):
    return CheckedClaim(binding_sha256=context.expected.fingerprint(), axis=axis, value=value,
        relation=relation, subject='BoundRule',
        source=Source(artifact='source.py', sha256='e' * 64, locator='BoundRule:10', authority='source_binding'))


class RoutingTests(unittest.TestCase):
    def test_known_role_unknown_optional_responsibilities_do_not_escalate(self):
        result = evaluate(candidate())
        self.assertEqual(result['route'], 'retain_proposal')
        self.assertEqual(result['status'], 'proposed_not_accepted')
        self.assertEqual(result['review_status'], 'not_needed')
        self.assertEqual(result['findings'], [])
        self.assertFalse(result['write_authority'])
        self.assertFalse(result['automatic_fact_acceptance'])
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertFalse(result['transport_verified'])
        self.assertFalse(result['source_locators_verified'])
        self.assertEqual(result['metric_effect'], 'none')

    def test_all_semantic_reasons_survive_without_repair(self):
        context = candidate(role='unknown', support='supported', owner='existing_specification', tool='yes',
                            action='reuse_specification', missing=(EvidenceGap(id='intent', description='Missing intent'),))
        before = context.model_dump_json()
        result = evaluate(context)
        reasons = {f['reason'] for f in result['findings']}
        self.assertTrue({'missing_premises', 'inconsistent_answers', 'unresolved_role',
                         'required_axis_unknown', 'required_evidence_missing'} <= reasons)
        self.assertEqual(result['route'], 'ordinary_review')
        self.assertEqual(result['review_status'], 'not_run')
        self.assertEqual(result['original_assessment']['labels']['evidence_confidence'], 'supported')
        self.assertEqual(context.model_dump_json(), before)
        self.assertEqual(evaluate(context), result)

    def test_limited_and_insufficient_evidence_escalate(self):
        for support in ('limited', 'insufficient'):
            with self.subTest(support=support):
                result = evaluate(candidate(support=support))
                self.assertEqual(result['route'], 'ordinary_review')
                self.assertIn('insufficient_evidence', [f['reason'] for f in result['findings']])

    def test_missing_documents_are_not_filled_by_a_supported_label(self):
        gap = EvidenceGap(id='publication-intent', description='Publication intent was not supplied')
        result = evaluate(candidate(missing=(gap,)))
        self.assertEqual(result['route'], 'ordinary_review')
        self.assertEqual(result['missing_premises'], [gap.model_dump()])

    def test_required_axes_cannot_be_cleared_by_an_action_default(self):
        for axis in ('ownership', 'tool_responsibility'):
            with self.subTest(axis=axis):
                result = evaluate(candidate(required_axes=(axis,)))
                self.assertEqual(result['route'], 'ordinary_review')
                self.assertIn(axis, next(f['details'] for f in result['findings']
                                        if f['reason'] == 'required_axis_unknown'))

    def test_reuse_and_exclusion_require_same_decision_evidence(self):
        for action in ('reuse_specification', 'exclude_owned'):
            for owner in ('existing_specification', 'simple_composition'):
                with self.subTest(action=action, owner=owner):
                    context = candidate(action=action, owner=owner)
                    self.assertEqual(evaluate(context)['route'], 'ordinary_review')
                    bound = context.model_copy(update={'checked_claims': (claim(context, value=owner),)})
                    self.assertEqual(evaluate(bound)['route'], 'retain_proposal')
        self.assertEqual(evaluate(candidate(action='reuse_specification'))['route'], 'ordinary_review')

    def test_tool_delegation_requires_tool_rule_binding(self):
        context = candidate(role='mechanics', action='delegate_tool', tool='yes')
        self.assertEqual(evaluate(context)['route'], 'ordinary_review')
        bound = context.model_copy(update={'checked_claims': (
            claim(context, axis='tool_responsibility', value='yes', relation='tool_rule'),)})
        self.assertEqual(evaluate(bound)['route'], 'retain_proposal')

    def test_creation_requires_checked_scoped_absence_never_unknown_as_absence(self):
        context = candidate(action='create_specification')
        self.assertEqual(evaluate(context)['route'], 'ordinary_review')
        checked = context.model_copy(update={'checked_claims': (
            claim(context, value='absent_in_scope', relation='scoped_absence'),)})
        result = evaluate(checked)
        self.assertEqual(result['route'], 'retain_proposal')
        self.assertEqual(result['original_assessment']['labels']['ownership'], 'unknown')

    def test_checked_fact_conflicts_are_visible(self):
        context = candidate()
        wrong = claim(context, axis='concern_kind', value='mechanics', relation='label_evidence')
        result = evaluate(context.model_copy(update={'checked_claims': (wrong,)}))
        self.assertEqual(result['route'], 'ordinary_review')
        self.assertIn('evidence_conflict', [f['reason'] for f in result['findings']])
        first = claim(context)
        second = claim(context, value='absent_in_scope', relation='scoped_absence')
        result = evaluate(context.model_copy(update={'checked_claims': (first, second)}))
        self.assertIn('evidence_conflict', [f['reason'] for f in result['findings']])

    def test_operational_failure_precedes_semantic_reasons_and_skips_later_route(self):
        context = candidate(status='transport_failed', role='unknown', support='insufficient')
        result = evaluate(context)
        self.assertEqual((result['route'], result['status']), ('stop_incomplete', 'analysis_incomplete'))
        self.assertTrue(any(f['kind'] == 'semantic' for f in result['findings']))
        self.assertIn({'name': 'pair[1]:OrdinaryReviewRouteSpec', 'outcome': 'skipped'}, result['trace'])
        self.assertEqual(result['review_status'], 'not_run')

    def test_invalid_missing_refused_truncated_and_not_run_are_not_clean(self):
        for status in ('invalid', 'missing', 'transport_failed', 'refused', 'truncated', 'not_run'):
            with self.subTest(status=status):
                result = evaluate(candidate(status=status))
                self.assertEqual(result['route'], 'stop_incomplete')
                self.assertEqual(result['hosted_requests'], 0)

    def test_identity_and_scope_changes_make_analysis_incomplete(self):
        context = candidate()
        updates = {'repository': 'different/repo', 'revision': 'f' * 40, 'path': 'other.py',
                   'start_line': 13, 'end_line': 19, 'decision_id': 'other', 'evidence_sha256': 'f' * 64,
                   'rubric_version': 'other', 'category_version': 'other', 'prompt_config_sha256': 'f' * 64,
                   'action': 'reuse_specification', 'required_axes': ('ownership',)}
        for key, value in updates.items():
            with self.subTest(field=key):
                altered = context.expected.model_copy(update={key: value})
                result = evaluate(context.model_copy(update={'assessment': context.assessment.model_copy(
                    update={'binding': altered})}))
                self.assertEqual(result['route'], 'stop_incomplete')
        for change in ({'binding': None}, {'labels': None}, {'response_sha256': None},
                       {'provider': 'other'}, {'requested_model': 'other'},
                       {'returned_model': 'other'}, {'returned_model': None}):
            with self.subTest(change=change):
                self.assertEqual(evaluate(context.model_copy(update={'assessment':
                    context.assessment.model_copy(update=change)}))['route'], 'stop_incomplete')
        stale = claim(context).model_copy(update={'binding_sha256': 'f' * 64})
        self.assertEqual(evaluate(context.model_copy(update={'checked_claims': (stale,)}))['route'], 'stop_incomplete')

    def test_small_exhaustive_label_and_operational_space(self):
        count = 0
        for role, support, owner, tool, status in itertools.product(
                ('policy', 'variant_behavior', 'mechanics', 'unknown'),
                ('supported', 'limited', 'insufficient'),
                ('existing_specification', 'simple_composition', 'unknown'),
                ('yes', 'unknown'), ('valid', 'transport_failed')):
            context = candidate(role=role, support=support, owner=owner, tool=tool, status=status)
            result = evaluate(context)
            expected = ('stop_incomplete' if status != 'valid' else
                        'ordinary_review' if role == 'unknown' or support != 'supported'
                        or (owner != 'unknown' and tool == 'yes') else 'retain_proposal')
            self.assertEqual(result['route'], expected, (role, support, owner, tool, status))
            self.assertFalse(result['automatic_fact_acceptance'])
            count += 1
        self.assertEqual(count, 144)

    def test_trace_uses_shared_consistency_specs_and_named_routing(self):
        result = evaluate(candidate(support='insufficient'))
        names = [e['name'] for e in result['trace']]
        self.assertIn('RoleSupportConsistentSpec', names)
        self.assertIn('ResponsibilitiesCompatibleSpec', names)
        self.assertIn('OrdinaryReviewRouteSpec', names)
        self.assertIn('specmetrics.semantic-review-routing/v1', names)

    def test_schema_and_immutability_reject_untyped_or_fabricated_inputs(self):
        context = candidate()
        with self.assertRaises(TypeError):
            evaluate(context.model_dump())
        with self.assertRaises(ValidationError):
            context.assessment.labels.concern_kind = 'mechanics'
        raw = context.model_dump(mode='json')
        for update in ({'confidence': 0.99}, {'concern_kind': 'magic'}, {'ownership': 'absent_in_scope'}):
            data = json.loads(json.dumps(raw))
            data['assessment']['labels'].update(update)
            with self.assertRaises(ValidationError):
                RoutingContext.model_validate_json(json.dumps(data))
        for path in ('../rules.py', '/rules.py', 'src/./rules.py', 'src//rules.py'):
            with self.assertRaises(ValidationError):
                DecisionBinding.model_validate_json(context.expected.model_dump_json().replace('src/rules.py', path))
        source = claim(context).model_dump(mode='json')
        source['source']['authority'] = 'development_premise'
        with self.assertRaises(ValidationError):
            CheckedClaim.model_validate_json(json.dumps(source))
        source = claim(context).model_dump(mode='json')
        source['relation'] = 'tool_rule'
        with self.assertRaises(ValidationError):
            CheckedClaim.model_validate_json(json.dumps(source))


class ReplayTests(unittest.TestCase):
    def test_native_provider_state_fields_are_explicit(self):
        from replay_semantic_review_routing_v1 import state_text
        for provider, field in [('jev-coreinfra', 'state'), ('luna-decision-coreinfra', 'input')]:
            with self.subTest(provider=provider):
                self.assertEqual(state_text({field: '{}'}, provider), '{}')
                other = 'input' if field == 'state' else 'state'
                with self.assertRaisesRegex(ValueError, 'state field'):
                    state_text({other: '{}'}, provider)

    def test_saved_native_routing_without_network_or_fact_promotion(self):
        from replay_semantic_review_routing_v1 import replay
        with patch('socket.socket.connect', side_effect=AssertionError('offline only')):
            result = replay()
        self.assertEqual(result['summaries'], {
            'jev-coreinfra': {'retain_proposal': 7, 'ordinary_review': 1, 'stop_incomplete': 0},
            'luna-decision-coreinfra': {'retain_proposal': 1, 'ordinary_review': 7, 'stop_incomplete': 0}})
        chosen = [c for c in result['cases'] if c['provider'] == 'jev-coreinfra'
                  and c['route']['route'] == 'ordinary_review']
        self.assertEqual([(c['case_id'], c['arm']) for c in chosen], [('R04', 'baseline')])
        self.assertEqual(result['hosted_requests'], 0)
        self.assertEqual(result['new_sol_calls'], 0)
        self.assertIsNone(result['semantic_accuracy'])
        self.assertFalse(result['calibrated_uncertainty_enabled'])
        self.assertTrue(all(c['route']['review_status'] == 'not_run' for c in chosen))

    def test_mutated_or_replaced_observations_do_not_become_route_evidence(self):
        from replay_semantic_review_routing_v1 import RUN, read_pinned_run
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / 'capture'
            shutil.copytree(RUN, copied)
            path = copied / 'responses.jsonl'
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                read_pinned_run(copied)
            receipt = copied / 'result-receipt.json'
            receipt.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'pinned'):
                read_pinned_run(copied)


if __name__ == '__main__':
    unittest.main()
