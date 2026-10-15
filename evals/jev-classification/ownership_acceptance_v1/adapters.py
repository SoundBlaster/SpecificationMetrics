"""Validate content/authority bindings before invoking the acceptance policy.

Trusted caller supplies exact source scope, source bytes and approved artifact
digests. This module does not authenticate reviewers or establish search coverage
from arbitrary scanner JSON. Approval is a separate application responsibility.
"""
import hashlib
import json
from pathlib import PurePosixPath

from recommendation_policy_v1.context import Facts, Source
from recommendation_policy_v1.proposals import fingerprint
from . import transition
from .context import AcceptanceContext, Review, Scope, Search, Trust


def sha(raw: bytes):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode(cls, raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    json.loads(raw, object_pairs_hook=unique)
    return cls.model_validate_json(raw)


def index_files(rows):
    result = {}
    for row in rows:
        path = PurePosixPath(row.path)
        require(not path.is_absolute() and '..' not in path.parts and str(path) == row.path
                and row.path != '.', 'invalid scope-relative file path')
        require(row.path not in result, 'duplicate file identity')
        result[row.path] = row.sha256
    return result


def reviewed_search(facts: Facts, *, scope_raw: bytes, search_raw: bytes, review_raw: bytes,
                    source_files: dict[str, bytes], trust: Trust):
    """Return a new snapshot only when separately approved evidence suffices.

Unknown authority/readiness => needs_review; malformed/stale evidence => ValueError.
No source path is opened from the submitted payload.
"""
    scope, search, review = decode(Scope, scope_raw), decode(Search, search_raw), decode(Review, review_raw)
    scope_hash, search_hash, review_hash = sha(scope_raw), sha(search_raw), sha(review_raw)
    require(scope_hash == trust.scope_sha256, 'scope is not the caller-selected scope')
    prior = fingerprint(facts)
    require(all(item.facts_sha256 == prior for item in (scope, search, review)), 'stale or substituted facts')
    require(search.scope_sha256 == scope_hash and review.search_sha256 == search_hash,
            'search/review artifact binding differs')
    expected, processed = index_files(scope.files), index_files(search.processed_files)
    require(set(source_files) == set(expected), 'source inventory differs from selected scope')
    require(all(sha(source_files[p]) == h for p, h in expected.items()), 'source content differs')
    require(all(p in expected and h == expected[p] for p, h in processed.items()), 'processed source identity differs')
    candidates = {}
    require(search.retrieval.limit is None or len(search.candidates) <= search.retrieval.limit,
            'ranked result exceeds declared limit')
    for candidate in search.candidates:
        require(candidate.candidate_id not in candidates, 'duplicate candidate identity')
        require(candidate.path in processed, 'candidate is outside processed files')
        lines = source_files[candidate.path].decode('utf-8').splitlines(keepends=True)
        require(1 <= candidate.start_line <= candidate.end_line <= len(lines), 'invalid declaration span')
        excerpt = ''.join(lines[candidate.start_line - 1:candidate.end_line]).encode()
        require(sha(excerpt) == candidate.excerpt_sha256, 'candidate source excerpt differs')
        candidates[candidate.candidate_id] = candidate
    comparisons = {}
    for comparison in review.comparisons:
        require(comparison.candidate_id in candidates, 'review references unknown candidate')
        require(comparison.candidate_id not in comparisons, 'duplicate candidate comparison')
        comparisons[comparison.candidate_id] = comparison.relation

    reasons = []
    if facts.has_conflict or facts.ownership.value != 'unknown':
        reasons.append('existing_or_conflicting_facts_require_separate_adjudication')
    if search_hash not in trust.approved_searches:
        reasons.append('search_not_approved')
    if review_hash not in trust.approved_reviews:
        reasons.append('review_not_approved')
    if search.status != 'complete' or processed != expected:
        reasons.append('incomplete_search_coverage')
    if search.unresolved:
        reasons.append('unresolved_search_limitations')
    if review.status != 'complete' or set(comparisons) != set(candidates):
        reasons.append('incomplete_candidate_adjudication')
    if review.unresolved or any(v in ('unknown', 'conflicting') for v in comparisons.values()):
        reasons.append('unresolved_candidate_adjudication')
    if review.catalogue_closure != 'complete_in_declared_scope':
        reasons.append('catalogue_closure_not_established')
    if search.retrieval.kind != 'exhaustive_catalogue':
        reasons.append('ranked_retrieval_cannot_establish_absence')
    same = [key for key, value in comparisons.items() if value == 'same_decision']
    specification_matches = [key for key in same if candidates[key].kind == 'specification']
    if same and not specification_matches:
        reasons.append('same_decision_without_confirmed_specification')

    if specification_matches and facts.tool_responsibility.value == 'yes':
        reasons.append('ownership_conflicts_with_tool_responsibility')
    context = AcceptanceContext(
        facts=facts, search_approved=search_hash in trust.approved_searches,
        review_approved=review_hash in trust.approved_reviews,
        search_failed=search.status == 'failed', search_complete=search.status == 'complete',
        inventory_complete=processed == expected, search_limitations=bool(search.unresolved),
        review_complete=review.status == 'complete', comparisons_complete=set(comparisons) == set(candidates),
        review_limitations=bool(review.unresolved), comparison_conflict='conflicting' in comparisons.values(),
        catalogue_closed=review.catalogue_closure == 'complete_in_declared_scope',
        ranked=search.retrieval.kind == 'ranked_candidates',
        same_decision_specification=bool(specification_matches),
        all_candidates_different=all(v == 'different_decision' for v in comparisons.values()),
        reasons=tuple(reasons))
    sources = tuple(Source(artifact='sha256:' + h, sha256=h, locator=locator, authority='reviewed_fact')
                    for h, locator in ((scope_hash, 'source scope'), (search_hash, 'candidate catalogue'),
                                       (review_hash, 'same-decision adjudication')))
    result = transition(context, sources)
    result.update(scope=scope.model_dump(mode='json'), search_sha256=search_hash, review_sha256=review_hash,
                  retrieval=search.retrieval.model_dump(mode='json'),
                  authority='caller_approved_artifacts_not_authenticated_reviewer_identity',
                  semantic_correctness_verified=False, catalogue_completeness='reviewed_not_formally_proven')
    return result


def pinned_bdd(facts: Facts):
    """Only the already-pinned BDD target; no generic name-based ownership inference."""
    import conditional_native_action_v2 as prep
    artifacts = prep.verify()  # Replays full-module containment and exact source binding.
    cases = json.loads(prep.old.previous.source.verify()['packet.json'])['cases']
    case = next(c for c in cases if c['case_id'] == prep.old.BDD)
    require((facts.case_id, facts.state_sha256, facts.scope_binding_sha256) == (
        case['case_id'], case['state_sha256'], case['scope_binding_sha256']), 'not the pinned BDD target/scope')
    blocked = facts.has_conflict or facts.ownership.value != 'unknown' or facts.tool_responsibility.value == 'yes'
    reasons = ('existing_or_conflicting_facts_require_separate_adjudication',) if blocked else ()
    witness = artifacts['ownership-witness.json']
    origin = Source(artifact=str((prep.RUN / 'ownership-witness.json').relative_to(prep.ROOT)),
                    sha256=sha(witness), locator='BDDScenarioValuesSpec.findings -> BDDPolicy._evaluate',
                    authority='source_binding')
    result = transition(AcceptanceContext(facts=facts, source_proof=True, reasons=reasons), (origin,))
    result.update(authority='pinned_static_source_binding', semantic_correctness_verified=False,
                  source_revision=prep.REVISION,
                  limitations=['ordinary static Python bindings and trusted library contract',
                               'not runtime execution or a whole-project ownership proof'])
    return result
