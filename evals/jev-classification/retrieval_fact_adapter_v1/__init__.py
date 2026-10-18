"""Associate a locally selected raw response with verified preparation; accept no facts."""
import hashlib
from pathlib import Path

from specification_core import TraceRecorder
from decision_choice_contract_v2 import ChoiceContractError, ResponseIdentityError
from prepare_retrieval_context_v1 import PROVIDERS, verify_bundle
from recommendation_policy_v1.context import Facts
from recommendation_policy_v1.proposals import fingerprint, questions
from retrieval_index_v1.source import digest, encoded

from .context import NativeProposal
from .dependencies import producer_inventory
from .native import parse_response
from .responsibilities_compatible import ResponsibilitiesCompatibleSpec
from .role_support_consistent import RoleSupportConsistentSpec

CONTRACT = 'specmetrics.retrieval-native-fact-adaptation/v1'
RULES = ((RoleSupportConsistentSpec(), 'unknown_requires_insufficient_and_vice_versa'),
         (ResponsibilitiesCompatibleSpec(), 'specification_and_tool_ownership_conflict'))


def producer_digests():
    root = Path(__file__).resolve().parent.parent
    return producer_inventory(root)


def adapt_response(preparation, provider, raw):
    if provider not in PROVIDERS:
        raise ValueError('unknown selected provider')
    if not isinstance(raw, bytes):
        raise TypeError('raw response must be exact captured bytes')
    packet = verify_bundle(Path(preparation))
    facts = Facts.model_validate_json(encoded(packet['state']['accepted_facts']))
    if (packet['fact_plan']['facts_sha256'] != fingerprint(facts)
            or packet['fact_plan']['accepted_facts'] != packet['state']['accepted_facts']
            or packet['fact_plan']['questions'] != questions(facts)
            or facts.role.kind != 'unknown' or facts.role.support != 'insufficient'
            or facts.ownership.value != 'unknown' or facts.tool_responsibility.value != 'unknown'
            or set(questions(facts)) != {'role', 'ownership', 'tool_responsibility'}):
        raise ValueError('fact plan is not bound to the four unresolved questions')
    request = next(r for r in packet['requests'] if r['provider'] == provider)
    report = dict(contract=CONTRACT, provider=provider, requested_model=request['requested_model'],
                  case_id=facts.case_id, facts_sha256=fingerprint(facts),
                  target_state_sha256=facts.state_sha256, scope_binding_sha256=facts.scope_binding_sha256,
                  wire_state_sha256=packet['state_sha256'], wire_sha256=request['wire_sha256'],
                  preparation_sha256=digest(encoded(packet)),
                  response_sha256=hashlib.sha256(raw).hexdigest(), adapter_producer_sha256=producer_digests(),
                  attribution='operator_selected_response_not_authenticated_transport',
                  transport_verified=False, automatic_fact_acceptance=False, write_authority=False,
                  source_locators_verified=False, semantic_correctness_verified=False,
                  rich_proposal_compatible=False, metric_effect='none', hosted_requests_by_adapter=0)
    try:
        prediction = parse_response(raw, provider=provider, model=request['requested_model'])
    except ChoiceContractError as error:
        return dict(report, status='rejected', native_status='invalid', rejection_code=error.code,
                    stop_required=isinstance(error, ResponseIdentityError), prediction=None,
                    proposed_facts=None, consistency_violations=[], consistency_trace=[])
    labels = prediction['labels']
    candidate = NativeProposal(labels['concern_kind'], labels['evidence_confidence'],
                               labels['ownership'], labels['tool_responsibility'])
    recorder = TraceRecorder()
    violations = [code for spec, code in RULES if not spec.is_satisfied_by(candidate, recorder=recorder)]
    proposals = dict(role=dict(kind=candidate.role, support=candidate.support),
                     ownership=candidate.ownership, tool_responsibility=candidate.tool)
    return dict(report, status='needs_review' if violations else 'proposed_not_accepted',
                native_status='valid', prediction=prediction, rejection_code=None, stop_required=False,
                consistency_violations=violations, proposed_facts=None if violations else proposals,
                consistency_trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events])
