"""Inspect newly selected rich reviews with unchanged citation/resolution Specs."""
from specification_core import TraceRecorder

from semantic_review_routing_v1 import evaluate as route
from semantic_review_routing_v1.context import CapturedAssessment
from structured_semantic_review_v1 import RULES, ResponseShapeError, output_text
from structured_semantic_review_v1.citation_matches_source import CitationMatchesSourceSpec
from structured_semantic_review_v1.context import CitationContext, ResolutionContext, ResolutionFacts, ReviewEnvelope
from structured_semantic_review_v1.preparation import MAX_RESPONSE_BYTES, MODEL, PROVIDER, load, sha
from structured_semantic_review_v1.review_resolved import ReviewResolvedSpec


def _inspect_selected(prepared, baseline_route, selection, *, request_sha256, raw,
                     captured_request_sha256, execution_status):
    # Internal seam: the public plan reconstructs selection + PreparedReview from
    # the same immutable task/capture. Do not call the old route-only verifier.
    original = prepared.original
    report = dict(contract='specmetrics.native-review-cascade/v1', task_sha256=prepared.task_sha256(),
        decision_binding_sha256=original.expected.fingerprint(), request_sha256=request_sha256,
        captured_request_sha256=captured_request_sha256, response_sha256=sha(raw) if type(raw) is bytes else None,
        original_assessment=original.assessment.model_dump(mode='json'), original_route=baseline_route,
        selection=selection, review=None, review_route=None, findings=[], trace=[],
        preserved_missing_evidence=[g.model_dump(mode='json') for g in original.missing_premises],
        provider=PROVIDER, requested_model=MODEL, returned_model=None, reported_usage=None, billed_cost=None,
        required_citation_coverage_verified=False, hosted_requests=0, automatic_fact_acceptance=False,
        metric_effect='none', write_authority=False, semantic_correctness_verified=False, transport_verified=False,
        source_locator_verification='exact_span_in_supplied_bound_excerpt_not_live_checkout',
        attribution='caller_selected_capture_bound_by_request_digest_not_authenticated_transport')

    def incomplete(reason, *, not_run=False):
        return dict(report, status='analysis_incomplete', disposition='needs_review',
            review_status='not_run' if not_run else 'failed',
            findings=[dict(reason=reason, details=[])], source_locators_verified=False)

    if execution_status in ('not_run', 'budget_exhausted'):
        return incomplete(execution_status, not_run=True)
    if execution_status in ('transport_failed', 'refused', 'truncated', 'invalid'):
        return incomplete(execution_status)
    if execution_status != 'completed':
        raise ValueError('unsupported review execution status')
    if captured_request_sha256 != request_sha256:
        return incomplete('review_request_mismatch')
    if type(raw) is not bytes or not raw or len(raw) > MAX_RESPONSE_BYTES:
        return incomplete('missing_or_oversized_response')
    try:
        body = load(raw)
        text = output_text(body)
        load(text)
        review = ReviewEnvelope.model_validate_json(text)
    except ResponseShapeError as error:
        return incomplete(str(error))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        return incomplete('invalid_review_response')
    if (review.task_sha256 != prepared.task_sha256()
            or review.decision_binding_sha256 != original.expected.fingerprint()):
        return incomplete('review_binding_mismatch')

    recorder = TraceRecorder()
    valid, invalid = [], []
    fragments = {f.id: f for f in prepared.fragments}
    for index, citation in enumerate(review.citations):
        matched = CitationMatchesSourceSpec().is_satisfied_by(
            CitationContext(citation, fragments.get(citation.fragment_id)), recorder=recorder)
        (valid if matched else invalid).append(citation if matched else index)
    captured = CapturedAssessment(status='valid', provider=PROVIDER, requested_model=MODEL,
        returned_model=MODEL, response_sha256=sha(raw), binding=original.expected, labels=review.labels)
    reviewed = original.model_copy(update=dict(expected_provider=PROVIDER, expected_model=MODEL, assessment=captured))
    reviewed_route = route(reviewed)
    context = ResolutionContext(original, review, tuple(valid), tuple(invalid),
                                tuple(f['reason'] for f in reviewed_route['findings']))
    findings = [dict(rule=type(rule).__name__, reason=reason, details=list(rule.details(context)))
                for rule, reason in RULES if rule.is_satisfied_by(context, recorder=recorder)]
    resolved = ReviewResolvedSpec().is_satisfied_by(ResolutionFacts(bool(findings)), recorder=recorder)
    gap_ids = {g.id for g in original.missing_premises}
    gaps = [g.model_dump(mode='json') for g in original.missing_premises]
    gaps.extend(g.model_dump(mode='json') for g in review.missing_evidence if g.id not in gap_ids)
    return dict(report, status='resolved_proposal' if resolved else 'needs_review',
        disposition='proposed_not_accepted' if resolved else 'needs_review', review_status='completed',
        review=review.model_dump(mode='json'), review_route=reviewed_route, findings=findings,
        returned_model=body['model'], reported_usage=body.get('usage'), preserved_missing_evidence=gaps,
        source_locators_verified=bool(valid) and not invalid,
        required_citation_coverage_verified=not any(f['reason'] == 'missing_citation_coverage' for f in findings),
        trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events])
