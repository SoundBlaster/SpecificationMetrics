"""Offline recommendation policy; never edits facts or performs inference."""
from dataclasses import dataclass

from specification_core import FirstMatch, TraceRecorder

from .context import Action, Facts
from .conflicting_facts import ConflictingFactsSpec
from .domain_contract import DomainContractSpec
from .existing_specification import ExistingSpecificationSpec
from .formalization_preference import FormalizationPreferenceSpec
from .ordinary_mechanics import OrdinaryMechanicsSpec
from .tool_responsibility import ToolResponsibilitySpec

POLICY = 'specmetrics.recommendation-policy/v1'


@dataclass(frozen=True)
class Selection:
    action: Action | None
    basis: str


RULES = (
    (ConflictingFactsSpec(), Selection(None, 'conflicting_facts')),
    (ExistingSpecificationSpec(), Selection('reuse_specification', 'existing_specification')),
    (ToolResponsibilitySpec(), Selection('use_tool_rules', 'tool_responsibility')),
    (DomainContractSpec(), Selection('formalize', 'domain_contract')),
    (OrdinaryMechanicsSpec(), Selection('keep_procedural', 'mechanics')),
    (FormalizationPreferenceSpec(), Selection('formalize', 'formalization_preference')),
)
DECISION = FirstMatch.with_fallback(RULES, Selection(None, 'missing_facts'), name=POLICY)


def evaluate(facts: Facts):
    """Recommendation is conditional on caller-established facts, not a semantic proof."""
    if not isinstance(facts, Facts):
        raise TypeError('evaluate requires validated Facts')
    recorder = TraceRecorder()
    selected = DECISION.decide(facts, recorder=recorder).value
    unresolved = []
    if facts.role.support != 'supported':
        unresolved.append('role_not_established')
    if facts.ownership.value == 'unknown':
        unresolved.append('same_decision_ownership_not_checked')
    if facts.tool_responsibility.value == 'unknown':
        unresolved.append('tool_responsibility_not_checked')
    if facts.intent_lookup.value == 'not_done':
        unresolved.append('bounded_intent_lookup_not_completed')
    if facts.has_conflict:
        unresolved.append('conflicting_facts')
    # Ownership settles reuse even if role or other responsibilities remain unknown.
    # Preserve unresolved facts in all cases; no result authorizes code changes.
    decisive = selected.action == 'reuse_specification' or not unresolved
    status = ('needs_review' if selected.action is None else
              'recommended_in_scope' if decisive else 'provisional')
    return dict(policy=POLICY, case_id=facts.case_id, state_sha256=facts.state_sha256,
                scope_binding_sha256=facts.scope_binding_sha256,
                recommendation=selected.action, basis=selected.basis, status=status,
                unresolved=unresolved, facts=facts.model_dump(mode='json'),
                trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events],
                semantic_correctness_verified=False, metric_effect='none', write_authority=False)
