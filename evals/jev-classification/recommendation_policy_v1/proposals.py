"""Offline model boundary: ask unresolved facts, never ask for an action."""
import hashlib
import json
from copy import deepcopy

from intent_first_contract_v4_1 import PROFILE
from .context import Facts, Frozen, Support, Text
from pydantic import model_validator


def fingerprint(facts: Facts):
    raw = json.dumps(facts.model_dump(mode='json'), sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def questions(facts: Facts):
    if facts.has_conflict:
        return {}  # Conflicting accepted facts need adjudication, not a model tie-break.
    pending = {}
    if facts.role.support != 'supported':
        pending['role'] = ['policy', 'variant_behavior', 'mechanics', 'unknown']
    if facts.ownership.value == 'unknown':
        pending['ownership'] = ['existing_specification', 'simple_composition', 'absent_in_scope', 'unknown']
    if facts.tool_responsibility.value == 'unknown':
        pending['tool_responsibility'] = ['yes', 'no_in_scope', 'unknown']
    return pending


def task(facts: Facts):
    return dict(contract='specmetrics.fact-proposal/v1', facts_sha256=fingerprint(facts),
                status='offline_question_plan_not_provider_request',
                accepted_facts=facts.model_dump(mode='json'), questions=questions(facts),
                architecture_profile=deepcopy(PROFILE), response_schema=Response.model_json_schema(),
                instructions='Classify only the requested unresolved facts using the bound evidence. '
                'Do not propose a recommendation, change established facts or claim an unbounded search. '
                'Policy decides admissibility, authority, lifecycle or obligation precedence; '
                'variant_behavior selects HOW an established domain activity is implemented; '
                'mechanics handles representation, parsing, transport or adaptation without a domain decision. '
                'Use unknown/insufficient when primary role cannot be settled. Supported means direct '
                'contract/code witness; limited means incomplete role support. This is not provider probability. '
                'These are proposals for review, never accepted facts. Supply source locators for review. '
                'This question plan still needs the exact bound source evidence attached before execution.',
                inference_authorized=False)


class Proposal(Frozen):
    field: Text
    value: Text
    support: Support | None = None
    source_locators: tuple[Text, ...]

    @model_validator(mode='after')
    def role_support(self):
        if self.field == 'role':
            if self.support is None or ((self.value == 'unknown') != (self.support == 'insufficient')):
                raise ValueError('role proposal requires consistent support')
        elif self.support is not None:
            raise ValueError('only role has ordinal support')
        if self.value != 'unknown' and not self.source_locators:
            raise ValueError('non-unknown proposal needs reviewable source locators')
        return self


class Response(Frozen):
    contract: Text
    facts_sha256: Text
    proposals: tuple[Proposal, ...]


def inspect_proposals(facts: Facts, raw_json: str):
    response = Response.model_validate_json(raw_json)
    if response.contract != 'specmetrics.fact-proposal/v1' or response.facts_sha256 != fingerprint(facts):
        raise ValueError('proposal contract or facts binding differs')
    allowed = questions(facts)
    fields = [p.field for p in response.proposals]
    if len(set(fields)) != len(fields) or set(fields) != set(allowed):
        raise ValueError('response must cover exactly the unresolved questions')
    for proposal in response.proposals:
        if proposal.value not in allowed[proposal.field]:
            raise ValueError('invalid fact proposal value')
    return dict(status='proposed_not_accepted', response=response.model_dump(mode='json'),
                facts_sha256=fingerprint(facts), source_locators_verified=False,
                semantic_correctness_verified=False, metric_effect='none')
