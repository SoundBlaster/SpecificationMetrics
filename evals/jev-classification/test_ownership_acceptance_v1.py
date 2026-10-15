import copy
import itertools
import json
import unittest

from pydantic import ValidationError

from recommendation_policy_v1 import evaluate
from recommendation_policy_v1.context import Facts
from recommendation_policy_v1.proposals import fingerprint
from ownership_acceptance_v1.adapters import pinned_bdd, reviewed_search, sha
from ownership_acceptance_v1.context import Trust
from test_recommendation_policy_v1 import facts


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def bundle(candidate=None):
    """Synthetic trusted-boundary fixture, never an actual approved source review."""
    candidate = candidate or facts(ownership='unknown')
    sources = {'rules.py': b'class ExistingRule:\n    pass\n', 'other.py': b'x = 1\n'}
    files = [dict(path=p, sha256=sha(raw)) for p, raw in sorted(sources.items())]
    scope = dict(contract='specmetrics.ownership-scope/v1', facts_sha256=fingerprint(candidate),
                 repository='fixture-only', revision='a' * 40, description='explicit two-file test scope', files=files)
    search = dict(contract='specmetrics.ownership-search/v1', facts_sha256=fingerprint(candidate),
                  scope_sha256='', producer='synthetic-test-catalogue-not-a-real-scanner', status='complete',
                  retrieval=dict(kind='exhaustive_catalogue', query_sha256='b' * 64,
                                 index_sha256='c' * 64, configuration_sha256='d' * 64, limit=None),
                  processed_files=copy.deepcopy(files), unresolved=[], candidates=[dict(
                      candidate_id='rule', kind='specification', path='rules.py', symbol='ExistingRule', start_line=1, end_line=2,
                      excerpt_sha256=sha(sources['rules.py']))])
    review = dict(contract='specmetrics.ownership-review/v1', facts_sha256=fingerprint(candidate),
                  search_sha256='', reviewer='synthetic-fixture-not-a-human-approval', status='complete',
                  catalogue_closure='complete_in_declared_scope', unresolved=[], comparisons=[dict(
                      candidate_id='rule', relation='different_decision', rationale='fixture judgment only')])
    return candidate, scope, search, review, sources


def seal(scope, search, review, approved=True):
    scope_raw = encoded(scope)
    search = dict(search, scope_sha256=sha(scope_raw))
    search_raw = encoded(search)
    review_raw = encoded(dict(review, search_sha256=sha(search_raw)))
    trust = Trust(sha(scope_raw), frozenset([sha(search_raw)]) if approved else frozenset(),
                  frozenset([sha(review_raw)]) if approved else frozenset())
    return dict(scope_raw=scope_raw, search_raw=search_raw, review_raw=review_raw, trust=trust)


def run(parts, approved=True):
    candidate, scope, search, review, sources = parts
    return reviewed_search(candidate, source_files=sources, **seal(scope, search, review, approved))


class AcceptanceTests(unittest.TestCase):
    def test_approved_complete_negative_review_accepts_only_scoped_absence(self):
        parts = bundle()
        before = fingerprint(parts[0])
        result = run(parts)
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['accepted_value'], 'absent_in_scope')
        self.assertEqual(fingerprint(parts[0]), before)
        updated = Facts.model_validate_json(json.dumps(result['facts']))
        self.assertEqual(updated.ownership.value, 'absent_in_scope')
        self.assertEqual(updated.role, parts[0].role)
        self.assertEqual(updated.scope_binding_sha256, parts[0].scope_binding_sha256)
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertFalse(result['write_authority'])

    def test_approval_is_not_self_asserted(self):
        parts = bundle()
        result = run(parts, approved=False)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['facts']['ownership']['value'], 'unknown')
        self.assertEqual(result['prior_facts_sha256'], result['next_facts_sha256'])
        self.assertIn('review_not_approved', result['reasons'])
        parts[3]['approved'] = True
        with self.assertRaises(ValidationError):
            run(parts)

    def test_256_coverage_readiness_combinations(self):
        # Absence requires all eight independent gates, not merely a present artifact.
        for flags in itertools.product([False, True], repeat=8):
            parts = bundle()
            _, _, search, review, _ = parts
            if not flags[0]: search['status'] = 'partial'
            if not flags[1]: search['processed_files'] = [f for f in search['processed_files'] if f['path'] == 'rules.py']
            if not flags[2]: search['unresolved'] = ['dynamic export not resolved']
            if not flags[3]: review['status'] = 'partial'
            if not flags[4]: review['comparisons'] = []
            if not flags[5]: review['comparisons'][0:1] = [dict(candidate_id='rule', relation='unknown', rationale='unresolved')]
            if not flags[6]: review['catalogue_closure'] = 'not_established'
            if not flags[7]: search['retrieval'].update(kind='ranked_candidates', limit=20)
            result = run(parts)
            with self.subTest(flags=flags):
                self.assertEqual(result['status'] == 'accepted', all(flags))

    def test_positive_match_does_not_need_negative_search_completeness(self):
        parts = bundle()
        parts[2]['status'] = 'partial'
        parts[2]['retrieval'].update(kind='ranked_candidates', limit=10)
        parts[3]['catalogue_closure'] = 'not_established'
        parts[3]['comparisons'][0]['relation'] = 'same_decision'
        result = run(parts)
        self.assertEqual(result['accepted_value'], 'existing_specification')
        self.assertEqual(evaluate(Facts.model_validate_json(json.dumps(result['facts'])))['recommendation'], 'reuse_specification')
        self.assertIn('ranked_retrieval_cannot_establish_absence', result['reasons'])
        self.assertEqual([r['outcome'] for r in result['trace']], ['selected', 'unsatisfied', 'satisfied', 'skipped'])

    def test_matching_intent_or_procedural_code_is_not_an_existing_specification(self):
        for kind in ('code_candidate', 'intent_document', 'unknown'):
            parts = bundle()
            parts[2]['candidates'][0]['kind'] = kind
            parts[3]['comparisons'][0]['relation'] = 'same_decision'
            result = run(parts)
            self.assertEqual(result['status'], 'needs_review')
            self.assertIn('same_decision_without_confirmed_specification', result['reasons'])

    def test_failed_search_or_conflicting_review_never_establishes_positive(self):
        for mode in ('failed', 'review_conflict', 'pending_review', 'review_limitation'):
            parts = bundle()
            parts[3]['comparisons'][0]['relation'] = 'same_decision'
            if mode == 'failed': parts[2]['status'] = 'failed'
            if mode == 'review_conflict': parts[3]['comparisons'][0]['relation'] = 'conflicting'
            if mode == 'pending_review': parts[3]['status'] = 'partial'
            if mode == 'review_limitation': parts[3]['unresolved'] = ['target meaning not settled']
            self.assertEqual(run(parts)['status'], 'needs_review')

    def test_empty_ranked_results_cannot_prove_absence_even_with_approved_review(self):
        parts = bundle()
        parts[2]['candidates'] = []
        parts[2]['retrieval'].update(kind='ranked_candidates', limit=20)
        parts[3]['comparisons'] = []
        result = run(parts)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('ranked_retrieval_cannot_establish_absence', result['reasons'])

    def test_empty_exhaustive_catalogue_still_needs_approved_closure(self):
        parts = bundle()
        parts[4]['rules.py'] = b'x = 1\n'
        for rows in (parts[1]['files'], parts[2]['processed_files']):
            for row in rows:
                row['sha256'] = sha(parts[4][row['path']])
        parts[2]['candidates'] = []
        parts[3]['comparisons'] = []
        self.assertEqual(run(parts)['accepted_value'], 'absent_in_scope')
        parts[3]['catalogue_closure'] = 'not_established'
        self.assertEqual(run(parts)['status'], 'needs_review')

    def test_ranked_limit_is_explicit_and_enforced(self):
        parts = bundle()
        parts[2]['retrieval'].update(kind='ranked_candidates', limit=None)
        with self.assertRaises(ValidationError): run(parts)
        parts[2]['retrieval']['limit'] = 1
        parts[2]['candidates'].append(dict(parts[2]['candidates'][0], candidate_id='second'))
        with self.assertRaisesRegex(ValueError, 'declared limit'): run(parts)

    def test_known_ownership_and_fact_conflicts_are_not_overwritten(self):
        for candidate in (facts(ownership='existing_specification'), facts(ownership='absent_in_scope'),
                          facts(ownership='unknown', conflicts=('conflict',))):
            result = run(bundle(candidate))
            self.assertEqual(result['status'], 'needs_review')
            self.assertEqual(result['facts'], candidate.model_dump(mode='json'))

    def test_positive_ownership_cannot_create_tool_conflict(self):
        parts = bundle(facts(ownership='unknown', tool='yes'))
        parts[3]['comparisons'][0]['relation'] = 'same_decision'
        self.assertEqual(run(parts)['status'], 'needs_review')

    def test_stale_review_and_source_swaps_rejected(self):
        parts = bundle()
        candidate, scope, search, review, sources = parts
        args = seal(scope, search, review)
        for replacement in (facts(ownership='unknown', kind='mechanics'),
                            Facts.model_validate(dict(candidate.model_dump(), scope_binding_sha256='f' * 64))):
            with self.assertRaisesRegex(ValueError, 'stale'):
                reviewed_search(replacement, source_files=sources, **args)
        sources['rules.py'] += b'# change\n'
        with self.assertRaisesRegex(ValueError, 'content'):
            reviewed_search(candidate, source_files=sources, **args)

    def test_source_inventory_missing_or_unexpected_files_rejected(self):
        for mode in ('missing', 'extra'):
            parts = bundle()
            if mode == 'missing': del parts[4]['other.py']
            else: parts[4]['unscoped.py'] = b'pass\n'
            with self.assertRaisesRegex(ValueError, 'inventory'):
                run(parts)

    def test_candidate_and_review_integrity(self):
        changes = [
            lambda p: p[2]['candidates'].append(p[2]['candidates'][0]),
            lambda p: p[2]['candidates'][0].update(path='missing.py'),
            lambda p: p[2]['candidates'][0].update(end_line=99),
            lambda p: p[2]['candidates'][0].update(excerpt_sha256='0' * 64),
            lambda p: p[3]['comparisons'][0].update(candidate_id='unknown-id'),
            lambda p: p[3]['comparisons'].append(p[3]['comparisons'][0]),
            lambda p: p[1]['files'].append(p[1]['files'][0]),
            lambda p: p[1]['files'][0].update(path='../outside.py'),
        ]
        for mutate in changes:
            parts = bundle()
            mutate(parts)
            with self.assertRaises(ValueError): run(parts)

    def test_review_byte_tampering_cannot_reuse_prior_approval(self):
        candidate, scope, search, review, sources = bundle()
        args = seal(scope, search, review)
        altered = json.loads(args['review_raw'])
        altered['comparisons'][0]['relation'] = 'same_decision'
        args['review_raw'] = encoded(altered)
        result = reviewed_search(candidate, source_files=sources, **args)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('review_not_approved', result['reasons'])

    def test_wrong_binding_duplicate_keys_and_unselected_scope_rejected(self):
        candidate, scope, search, review, sources = bundle()
        args = seal(scope, search, review)
        altered = json.loads(args['review_raw'])
        altered['search_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'binding'):
            reviewed_search(candidate, source_files=sources, **dict(args, review_raw=encoded(altered)))
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
            reviewed_search(candidate, source_files=sources, **dict(args, review_raw=b'{"x":1,"x":2}'))
        with self.assertRaisesRegex(ValueError, 'caller-selected'):
            reviewed_search(candidate, source_files=sources, **dict(args, trust=Trust('0' * 64)))

    def test_pinned_bdd_proof_and_wrong_case(self):
        from replay_ownership_acceptance_v1 import replay
        result = replay()
        self.assertEqual(result['acceptance']['accepted_value'], 'existing_specification')
        self.assertEqual(result['before']['recommendation'], 'formalize')
        self.assertEqual(result['after']['recommendation'], 'reuse_specification')
        with self.assertRaisesRegex(ValueError, 'target/scope'):
            pinned_bdd(facts(ownership='unknown'))
        accepted = Facts.model_validate_json(json.dumps(result['acceptance']['facts']))
        self.assertEqual(pinned_bdd(accepted)['status'], 'needs_review')


if __name__ == '__main__':
    unittest.main()
