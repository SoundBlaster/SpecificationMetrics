"""Pure ownership transition policy; I/O and witness verification live in adapters."""
from specification_core import FirstMatch, TraceRecorder

from recommendation_policy_v1.context import Facts, OwnershipFact, Source
from recommendation_policy_v1.proposals import fingerprint
from .blocked_transition import BlockedOwnershipTransitionSpec
from .context import AcceptanceContext
from .scoped_absence import ReviewedScopedAbsenceSpec
from .verified_ownership import VerifiedSameDecisionOwnershipSpec

POLICY = 'specmetrics.ownership-acceptance/v1'
DECISION = FirstMatch.with_fallback((
    (BlockedOwnershipTransitionSpec(), None),
    (VerifiedSameDecisionOwnershipSpec(), 'existing_specification'),
    (ReviewedScopedAbsenceSpec(), 'absent_in_scope'),
), None, name=POLICY)


def transition(context: AcceptanceContext, sources: tuple[Source, ...]):
    """Internal policy application. Only adapters may establish verified flags."""
    recorder = TraceRecorder()
    facts = context.facts
    selected = DECISION.decide(context, recorder=recorder).value
    updated = facts
    if selected is not None:
        values = facts.model_dump()
        values['ownership'] = OwnershipFact(value=selected, sources=sources).model_dump()
        updated = Facts.model_validate(values)
    return dict(policy=POLICY, status='accepted' if selected else 'needs_review',
                accepted_value=selected, prior_facts_sha256=fingerprint(facts),
                next_facts_sha256=fingerprint(updated), facts=updated.model_dump(mode='json'),
                reasons=list(context.reasons),
                trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events],
                metric_effect='none', write_authority=False, runtime_identity_verified=False)
