"""Pure routing policy: does not invoke reviewers, accept facts or change S/U."""
from specification_core import FirstMatch, TraceRecorder

from .analysis_unavailable import AnalysisUnavailableSpec
from .context import RouteFacts, RoutingContext
from .evidence_conflict import EvidenceConflictSpec
from .incomplete_route import IncompleteRouteSpec
from .inconsistent_answers import InconsistentAnswersSpec
from .insufficient_evidence import InsufficientEvidenceSpec
from .missing_premises import MissingPremisesSpec
from .ordinary_review_route import OrdinaryReviewRouteSpec
from .required_axis_unknown import RequiredAxisUnknownSpec
from .required_evidence_missing import RequiredEvidenceMissingSpec
from .unresolved_role import UnresolvedRoleSpec

POLICY = 'specmetrics.semantic-review-routing/v1'
OBSERVATIONS = (
    (AnalysisUnavailableSpec(), 'analysis_unavailable', 'operational'),
    (MissingPremisesSpec(), 'missing_premises', 'semantic'),
    (InconsistentAnswersSpec(), 'inconsistent_answers', 'semantic'),
    (UnresolvedRoleSpec(), 'unresolved_role', 'semantic'),
    (InsufficientEvidenceSpec(), 'insufficient_evidence', 'semantic'),
    (RequiredAxisUnknownSpec(), 'required_axis_unknown', 'semantic'),
    (RequiredEvidenceMissingSpec(), 'required_evidence_missing', 'semantic'),
    (EvidenceConflictSpec(), 'evidence_conflict', 'semantic'),
)
DECISION = FirstMatch.with_fallback(
    ((IncompleteRouteSpec(), 'stop_incomplete'), (OrdinaryReviewRouteSpec(), 'ordinary_review')),
    fallback='retain_proposal', name=POLICY)
STATUS = {'stop_incomplete': 'analysis_incomplete', 'ordinary_review': 'needs_review',
          'retain_proposal': 'proposed_not_accepted'}


def evaluate(candidate: RoutingContext):
    if not isinstance(candidate, RoutingContext):
        raise TypeError('evaluate requires validated RoutingContext')
    recorder = TraceRecorder()
    findings = [dict(rule=type(rule).__name__, reason=reason, kind=kind, details=list(rule.details(candidate)))
                for rule, reason, kind in OBSERVATIONS if rule.is_satisfied_by(candidate, recorder=recorder)]
    facts = RouteFacts(incomplete=any(f['kind'] == 'operational' for f in findings),
                       semantic_review=any(f['kind'] == 'semantic' for f in findings))
    route = DECISION.decide(facts, recorder=recorder).value
    return dict(policy=POLICY, route=route, status=STATUS[route], findings=findings,
                binding=candidate.expected.model_dump(mode='json'), binding_sha256=candidate.expected.fingerprint(),
                expected_provider=candidate.expected_provider, expected_model=candidate.expected_model,
                original_assessment=candidate.assessment.model_dump(mode='json'),
                missing_premises=[g.model_dump(mode='json') for g in candidate.missing_premises],
                checked_claims=[c.model_dump(mode='json') for c in candidate.checked_claims],
                trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events],
                review_status='not_needed' if route == 'retain_proposal' else 'not_run',
                hosted_requests=0, automatic_fact_acceptance=False, metric_effect='none',
                write_authority=False, semantic_correctness_verified=False,
                transport_verified=False, source_locators_verified=False,
                provenance_scope='caller_bound_inputs_not_authenticated_transport')
