"""Inspect bounded captured Responses reviews and resolve suggestions offline."""
from specification_core import TraceRecorder

from semantic_review_routing_v1 import evaluate as route
from semantic_review_routing_v1.context import CapturedAssessment

from .citation_matches_source import CitationMatchesSourceSpec
from .context import CitationContext, ResolutionContext, ResolutionFacts, ReviewEnvelope
from .invalid_citations import InvalidCitationsSpec
from .material_disagreement import MaterialDisagreementSpec
from .missing_citation_coverage import MissingCitationCoverageSpec
from .missing_review_evidence import MissingReviewEvidenceSpec
from .preparation import (CONTRACT, MAX_RESPONSE_BYTES, MODEL, PROVIDER, load, request_sha256, sha, verify)
from .review_resolved import ReviewResolvedSpec
from .unresolved_routing import UnresolvedRoutingSpec

RULES = (
    (InvalidCitationsSpec(), 'invalid_citations'),
    (MissingCitationCoverageSpec(), 'missing_citation_coverage'),
    (MaterialDisagreementSpec(), 'material_disagreement'),
    (UnresolvedRoutingSpec(), 'unresolved_review_assessment'),
    (MissingReviewEvidenceSpec(), 'missing_evidence'),
)


class ResponseShapeError(ValueError):
    """Only fixed local diagnostic codes, never raw provider exception text."""


def output_text(body):
    if not isinstance(body, dict) or body.get('model') != MODEL:
        raise ResponseShapeError('model_identity_mismatch')
    if (body.get('status') != 'completed' or body.get('error') is not None
            or body.get('incomplete_details') is not None):
        raise ResponseShapeError('response_incomplete')
    output = body.get('output')
    if not isinstance(output, list):
        raise ResponseShapeError('invalid_output')
    messages = []
    for item in output:
        if not isinstance(item, dict):
            raise ResponseShapeError('invalid_output')
        if item.get('type') == 'reasoning':
            continue
        if item.get('type') != 'message' or item.get('role') != 'assistant' or item.get('status') != 'completed':
            raise ResponseShapeError('invalid_output')
        content = item.get('content')
        if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
            raise ResponseShapeError('invalid_output')
        part = content[0]
        if part.get('type') == 'refusal':
            raise ResponseShapeError('response_refused')
        if part.get('type') != 'output_text' or not isinstance(part.get('text'), str):
            raise ResponseShapeError('invalid_output')
        messages.append(part['text'])
    if len(messages) != 1:
        raise ResponseShapeError('ambiguous_output')
    return messages[0]


def inspect(prepared, raw: bytes | None, *, captured_request_sha256: str | None,
            execution_status='completed'):
    """A caller-selected capture is not authenticated transport or semantic truth."""
    verify(prepared)
    original = prepared.original
    report = dict(contract=CONTRACT, task_sha256=prepared.task_sha256(),
        decision_binding_sha256=original.expected.fingerprint(), request_sha256=request_sha256(prepared),
        captured_request_sha256=captured_request_sha256, response_sha256=sha(raw) if type(raw) is bytes else None,
        original_assessment=original.assessment.model_dump(mode='json'),
        original_route=route(original), review=None, review_route=None, findings=[], trace=[],
        preserved_missing_evidence=[g.model_dump(mode='json') for g in original.missing_premises],
        provider=PROVIDER, requested_model=MODEL, hosted_requests=0,
        returned_model=None, reported_usage=None, billed_cost=None,
        required_citation_coverage_verified=False,
        automatic_fact_acceptance=False, metric_effect='none', write_authority=False,
        semantic_correctness_verified=False, transport_verified=False,
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
    if captured_request_sha256 != report['request_sha256']:
        return incomplete('review_request_mismatch')
    if type(raw) is not bytes or not raw or len(raw) > MAX_RESPONSE_BYTES:
        return incomplete('missing_or_oversized_response')
    try:
        body = load(raw)
        text = output_text(body)
        load(text)  # Reject duplicate keys/nonfinite values before Pydantic parsing.
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
    captured = CapturedAssessment(status='valid', provider=PROVIDER, requested_model=MODEL, returned_model=MODEL,
        response_sha256=sha(raw), binding=original.expected, labels=review.labels)
    reviewed = original.model_copy(update=dict(expected_provider=PROVIDER, expected_model=MODEL, assessment=captured))
    review_route = route(reviewed)
    context = ResolutionContext(original, review, tuple(valid), tuple(invalid),
                                tuple(f['reason'] for f in review_route['findings']))
    findings = [dict(rule=type(rule).__name__, reason=reason, details=list(rule.details(context)))
                for rule, reason in RULES if rule.is_satisfied_by(context, recorder=recorder)]
    resolved = ReviewResolvedSpec().is_satisfied_by(ResolutionFacts(bool(findings)), recorder=recorder)
    original_gap_ids = {g.id for g in original.missing_premises}
    gaps = [g.model_dump(mode='json') for g in original.missing_premises]
    gaps.extend(g.model_dump(mode='json') for g in review.missing_evidence if g.id not in original_gap_ids)
    return dict(report, status='resolved_proposal' if resolved else 'needs_review',
        disposition='proposed_not_accepted' if resolved else 'needs_review', review_status='completed',
        review=review.model_dump(mode='json'), review_route=review_route, findings=findings,
        returned_model=body['model'], reported_usage=body.get('usage'),
        preserved_missing_evidence=gaps, source_locators_verified=bool(valid) and not invalid,
        required_citation_coverage_verified=not any(f['reason'] == 'missing_citation_coverage' for f in findings),
        trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events])
