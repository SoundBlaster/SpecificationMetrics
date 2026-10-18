import itertools
import json
import unittest

from pydantic import ValidationError

from recommendation_policy_v1 import evaluate
from recommendation_policy_v1.context import ConflictFact, Facts, LookupFact, OwnershipFact, Role, Source, ToolFact
from recommendation_policy_v1.proposals import fingerprint, inspect_proposals, questions, task

SOURCE = Source(artifact='fixture.json', sha256='a' * 64, locator='case-1', authority='development_premise')


def facts(kind='policy', support='supported', ownership='absent_in_scope', tool='no_in_scope',
          lookup='completed', conflicts=()):
    return Facts(case_id='test', state_sha256='b' * 64, scope_binding_sha256='c' * 64,
                 role=Role(kind=kind, support=support, sources=(SOURCE,)),
                 ownership=OwnershipFact(value=ownership, sources=(SOURCE,)),
                 tool_responsibility=ToolFact(value=tool, sources=(SOURCE,)),
                 intent_lookup=LookupFact(value=lookup, sources=(SOURCE,)),
                 conflicts=tuple(ConflictFact(description=text, sources=(SOURCE,)) for text in conflicts))


class PolicyTests(unittest.TestCase):
    def test_explicit_conflicts_require_bound_immutable_provenance(self):
        raw = facts().model_dump(mode='json')
        invalid = ['unbound conflict', {'description': 'unbound conflict'},
                   {'description': 'unbound conflict', 'sources': []},
                   {'description': 'conflict', 'sources': [dict(artifact='x')]}]
        for conflict in invalid:
            with self.subTest(conflict=conflict), self.assertRaises(ValidationError):
                Facts.model_validate_json(json.dumps(dict(raw, conflicts=[conflict])))
        candidate = facts(conflicts=('sources disagree',))
        restored = Facts.model_validate_json(candidate.model_dump_json())
        decision = evaluate(restored)
        self.assertEqual(decision['status'], 'needs_review')
        self.assertEqual(decision['facts']['conflicts'][0]['sources'][0], SOURCE.model_dump())
        with self.assertRaises(ValidationError):
            restored.conflicts[0].sources[0].locator = 'changed'
        changed = json.loads(candidate.model_dump_json())
        changed['conflicts'][0]['sources'][0]['sha256'] = 'f' * 64
        self.assertNotEqual(fingerprint(candidate), fingerprint(Facts.model_validate_json(json.dumps(changed))))

    def test_exhaustive_safety_invariants(self):
        roles = [('policy', 'supported'), ('variant_behavior', 'supported'), ('mechanics', 'supported'),
                 ('policy', 'limited'), ('variant_behavior', 'limited'), ('mechanics', 'limited'),
                 ('unknown', 'insufficient')]
        owners = ['existing_specification', 'simple_composition', 'absent_in_scope', 'unknown', 'conflicting']
        tools = ['yes', 'no_in_scope', 'unknown', 'conflicting']
        lookups = ['completed', 'not_done', 'conflicting']
        count = 0
        for (kind, support), owner, tool, lookup, conflict in itertools.product(
                roles, owners, tools, lookups, [(), ('sources disagree',)]):
            candidate = facts(kind, support, owner, tool, lookup, conflict)
            before = candidate.model_dump_json()
            result = evaluate(candidate)
            count += 1
            with self.subTest(kind=kind, support=support, owner=owner, tool=tool, lookup=lookup, conflict=conflict):
                self.assertEqual(before, candidate.model_dump_json())
                self.assertEqual(result, evaluate(candidate))
                self.assertFalse(result['write_authority'])
                self.assertEqual(result['metric_effect'], 'none')
                if conflict or 'conflicting' in (owner, tool, lookup) or (owner in owners[:2] and tool == 'yes'):
                    self.assertIsNone(result['recommendation'])
                    self.assertEqual(result['status'], 'needs_review')
                    continue
                if owner in owners[:2]:
                    self.assertEqual(result['recommendation'], 'reuse_specification')
                if result['recommendation'] == 'keep_procedural':
                    self.assertEqual((kind, support), ('mechanics', 'supported'))
                if result['recommendation'] == 'formalize':
                    self.assertFalse(kind == 'mechanics' and support == 'supported')
                    if support != 'supported':
                        self.assertEqual(lookup, 'completed')
                        self.assertEqual(result['status'], 'provisional')
                        self.assertIn('role_not_established', result['unresolved'])
                if owner == 'unknown' and result['recommendation'] is not None:
                    self.assertEqual(result['status'], 'provisional')
                if tool == 'yes':
                    self.assertEqual(result['recommendation'], 'use_tool_rules')
        self.assertEqual(count, 840)

    def test_decision_table(self):
        rows = [
            (facts(), 'formalize', 'domain_contract', 'recommended_in_scope'),
            (facts(kind='variant_behavior'), 'formalize', 'domain_contract', 'recommended_in_scope'),
            (facts(ownership='existing_specification'), 'reuse_specification', 'existing_specification', 'recommended_in_scope'),
            (facts(ownership='simple_composition'), 'reuse_specification', 'existing_specification', 'recommended_in_scope'),
            (facts(kind='mechanics', tool='yes'), 'use_tool_rules', 'tool_responsibility', 'recommended_in_scope'),
            (facts(kind='mechanics'), 'keep_procedural', 'mechanics', 'recommended_in_scope'),
            (facts(kind='unknown', support='insufficient'), 'formalize', 'formalization_preference', 'provisional'),
            (facts(kind='unknown', support='insufficient', lookup='not_done'), None, 'missing_facts', 'needs_review'),
            (facts(ownership='existing_specification', tool='yes'), None, 'conflicting_facts', 'needs_review'),
        ]
        for candidate, action, basis, status in rows:
            result = evaluate(candidate)
            self.assertEqual((result['recommendation'], result['basis'], result['status']), (action, basis, status))

    def test_unknown_ownership_never_becomes_absence(self):
        result = evaluate(facts(ownership='unknown'))
        self.assertEqual(result['status'], 'provisional')
        self.assertEqual(result['facts']['ownership']['value'], 'unknown')
        self.assertIn('same_decision_ownership_not_checked', result['unresolved'])

    def test_reuse_trace_skips_all_later_rules(self):
        result = evaluate(facts(ownership='existing_specification'))
        trace = result['trace']
        self.assertEqual(trace[1:3], [dict(name='ConflictingFactsSpec', outcome='unsatisfied'),
                                     dict(name='ExistingSpecificationSpec', outcome='satisfied')])
        self.assertEqual([r['name'] for r in trace[3:]], [
            'pair[2]:ToolResponsibilitySpec', 'pair[3]:DomainContractSpec',
            'pair[4]:OrdinaryMechanicsSpec', 'pair[5]:FormalizationPreferenceSpec'])
        self.assertTrue(all(r['outcome'] == 'skipped' for r in trace[3:]))

    def test_invalid_and_mutable_facts_rejected(self):
        for values in [dict(kind='unknown', support='supported'), dict(kind='policy', support='insufficient')]:
            with self.assertRaises(ValidationError):
                facts(**values)
        for cls, value in [(OwnershipFact, 'absent_in_scope'), (ToolFact, 'yes'), (LookupFact, 'completed')]:
            with self.assertRaises(ValidationError):
                cls(value=value)
        candidate = facts()
        with self.assertRaises(ValidationError):
            candidate.role.kind = 'mechanics'
        with self.assertRaises(ValidationError):
            candidate.role.sources[0].locator = 'changed'
        with self.assertRaises(TypeError):
            evaluate(candidate.model_dump())


class ProposalTests(unittest.TestCase):
    def candidate(self):
        return facts(kind='unknown', support='insufficient', ownership='unknown', tool='unknown')

    def response(self, candidate):
        return dict(contract='specmetrics.fact-proposal/v1', facts_sha256=fingerprint(candidate), proposals=[
            dict(field='role', value='policy', support='supported', source_locators=['fragment-01']),
            dict(field='ownership', value='unknown', source_locators=[]),
            dict(field='tool_responsibility', value='unknown', source_locators=[]),
        ])

    def test_only_unknown_facts_requested(self):
        self.assertEqual(questions(facts()), {})
        self.assertEqual(questions(facts(ownership='unknown')), {'ownership': [
            'existing_specification', 'simple_composition', 'absent_in_scope', 'unknown']})
        self.assertEqual(questions(facts(conflicts=('conflict',))), {})
        self.assertNotIn('recommendation', task(self.candidate())['questions'])
        self.assertIn('goal', task(self.candidate())['architecture_profile'])
        self.assertIn('response_schema', task(self.candidate()))

    def test_model_cannot_mutate_or_promote_facts(self):
        candidate = self.candidate()
        before = evaluate(candidate)
        response = inspect_proposals(candidate, json.dumps(self.response(candidate)))
        self.assertEqual(response['status'], 'proposed_not_accepted')
        self.assertEqual(evaluate(candidate), before)
        self.assertEqual(candidate.role.kind, 'unknown')
        self.assertFalse(response['source_locators_verified'])

    def test_stale_scope_and_known_field_overwrite_rejected(self):
        raw = json.dumps(self.response(self.candidate()))
        other = self.candidate().model_dump()
        other['scope_binding_sha256'] = 'd' * 64
        with self.assertRaises(ValueError):
            inspect_proposals(Facts.model_validate(other), raw)
        other = self.candidate().model_dump()
        other['ownership']['sources'][0]['sha256'] = 'e' * 64
        with self.assertRaises(ValueError):
            inspect_proposals(Facts.model_validate(other), raw)
        # Even a response with the current fingerprint cannot overwrite a known role.
        known = facts(ownership='unknown', tool='unknown')
        with self.assertRaisesRegex(ValueError, 'exactly'):
            inspect_proposals(known, json.dumps(self.response(known)))

    def test_recommendation_duplicate_missing_and_invalid_values_rejected(self):
        candidate = self.candidate()
        mutations = [
            lambda r: r.update(recommendation='formalize'),
            lambda r: r['proposals'].append(r['proposals'][0]),
            lambda r: r['proposals'].pop(),
            lambda r: r['proposals'][0].update(value='mechanical_magic'),
            lambda r: r['proposals'][0].update(value='unknown'),
            lambda r: r['proposals'][0].update(source_locators=[]),
        ]
        for mutate in mutations:
            response = self.response(candidate)
            mutate(response)
            with self.assertRaises(ValueError):
                inspect_proposals(candidate, json.dumps(response))

    def test_replay_preserves_raw_observations_and_uncertainty(self):
        from replay_recommendation_policy_v1 import replay
        result = replay()
        self.assertEqual(result['provider_requests'], 0)
        self.assertEqual(result['raw_observations'], 18)
        self.assertIsNone(result['semantic_accuracy'])
        rows = result['cases']
        self.assertEqual([r['decision']['recommendation'] for r in rows], [
            'formalize', 'formalize', 'reuse_specification', 'use_tool_rules'])
        self.assertEqual(rows[0]['decision']['facts']['role']['kind'], 'unknown')
        self.assertEqual(rows[1]['decision']['facts']['ownership']['value'], 'unknown')
        self.assertEqual(rows[2]['decision']['facts']['ownership']['sources'][0]['authority'], 'source_binding')
        self.assertEqual(sum(len(r['observations']) for r in rows), 18)
        self.assertEqual(result['source_bound_ownership_case_ids'], ['target-03-cell03'])
        self.assertIn('Only target-03-cell03', result['interpretation'])
        self.assertTrue(result['historical_cases_unchanged'])


def load_tests(loader, tests, pattern):
    """The existing offline policy CI entry point also checks semantic routing."""
    # General discovery already finds that module; avoid adding it twice there.
    if pattern is None:
        tests.addTests(loader.loadTestsFromName('test_semantic_review_routing_v1'))
    return tests


if __name__ == '__main__':
    unittest.main()
