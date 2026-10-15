"""Offline architecture recommendation contract; no provider or production wiring."""
import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CONTRACT_ID = 'specification_metrics.intent-first.v4'
HexDigest = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
AXES = ('concern_kind', 'evidence_confidence', 'recommendation')
PROFILE = {
    'id': 'specification-centric-intent-first-v1',
    'goal': 'Uniform, addressable, composable and observable domain rules for human and AI SDLC; preserve product behavior.',
    'intent_first': 'Inspect supplied intent, proposal and spec documents before guessing purpose from syntax. Record missing or conflicting context. Documents retain their declared authority.',
    'ambiguity': 'After bounded intent lookup, prefer formalization if the architecture choice remains ambiguous. This preference does not prove a domain role.',
    'reuse': 'Reuse existing same-decision Specifications and their simple NOT/AND/OR compositions; no wrapper solely for a Boolean operator. An arbitrary Boolean fact is not automatically a Specification.',
    'tools': 'Formatting/linting responsibilities belong to formatter/linter rule sets. This responsibility does not prove an exact rule is configured or already enforced.',
    'mechanics': 'Keep demonstrated parsing, representation, transport and adaptation mechanics procedural when they define no distinct domain rule.',
    'composition_complexity_limit': None,
}
INSTRUCTIONS = """Judge the exact expression in the selected shared_definition or
bound_application scope, not a later dispatch, caller or isolated clause.
The permitted semantic inputs are ONLY the supplied state.target,
state.bounded_context, state.architecture_profile, state.evaluation_scope and
the supplied contract/profile instructions. Inspect the available intent,
proposal and spec fragments; list their IDs in intent_review.checked_document_ids.
Record missing material context or conflicts. Missing documents are not a universal
reason to abstain when code already establishes the contract. Never import documents
or expected labels from another view. A proposal is not a canonical Requirement.

Classify concern_kind: policy decides admissibility, authority, lifecycle or which
obligation has precedence; variant_behavior selects HOW an established domain
activity is implemented; mechanics handles representation/parsing/transport/
adaptation without a distinct domain decision; unknown retains unresolved primary
role. Names, rejection, branch count, imports and file location alone do not prove it.

evidence_confidence describes support for concern_kind, not native provider
probability: supported = direct contract/code witness; limited = relevant but
incomplete or conflicting evidence; insufficient = primary role cannot be settled.
Use unknown with insufficient. These ordinal self-reports are not calibrated scores.

Choose recommendation after inspecting intent and existing responsibilities:
- reuse_specification for explicit same-decision ownership through evaluation or
  recognized simple Specification composition. Do not create a wrapper for NOT/AND/OR.
- use_tool_rules for formatter/linter responsibilities; do not claim configured
  enforcement unless the supplied evidence establishes it.
- keep_procedural for affirmatively established ordinary mechanics.
- formalize for an inline domain decision, including pure contracts with one use;
  also prefer formalize if meaningful architectural ambiguity remains after lookup.
  In that fallback use basis=formalization_preference and retain role uncertainty.

Use basis=domain_contract, formalization_preference, existing_specification,
simple_composition, tool_responsibility or mechanics as appropriate. Give a reason
for each axis, exact source quotes supporting concern_kind and recommendation,
and uncertainties. A source quote proves association, not semantic correctness.
Preserve case/task/state/scope/contract identities. No change in target boundaries,
new composition threshold, refactor, write authority or production S/U follows.
"""
PROMPT = """Use ONLY packet.json, contract.json and template.json from your assigned
directory. Inspect each case independently under the complete contract instructions.
The contract/profile supplies the global SpecificationCore goal and style preference;
the case supplies the exact target, scope and bounded evidence. Do not read the source
repository, other evidence views, source-bindings, integrator examples, prior labels,
memory, credentials or network. Inspect supplied documents and disclose missing intent
context; this bounded task does not authorize external lookup. Fill each template row
with concern_kind, evidence_confidence, recommendation, basis, intent_review,
rationales, evidence_quotes and uncertainties. Preserve every identity field.
Return strict JSON with an annotations array. Do not refactor or count S/U.
"""


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class IntentReview(StrictModel):
    checked_document_ids: list[Text]
    missing_context: list[Text]


class Rationales(StrictModel):
    concern_kind: Text
    evidence_confidence: Text
    recommendation: Text


class EvidenceQuote(StrictModel):
    axis: Literal['concern_kind', 'recommendation']
    fragment_id: Text
    quote: Annotated[str, StringConstraints(min_length=1)]


class Annotation(StrictModel):
    contract_id: Literal['specification_metrics.intent-first.v4']
    contract_sha256: HexDigest
    case_id: Text
    task_sha256: HexDigest
    state_sha256: HexDigest
    scope_unit: Literal['shared_definition', 'bound_application']
    scope_binding_sha256: HexDigest
    concern_kind: Literal['policy', 'mechanics', 'variant_behavior', 'unknown']
    evidence_confidence: Literal['supported', 'limited', 'insufficient']
    recommendation: Literal['formalize', 'reuse_specification', 'use_tool_rules', 'keep_procedural']
    basis: Literal['domain_contract', 'formalization_preference', 'existing_specification',
                   'simple_composition', 'tool_responsibility', 'mechanics']
    intent_review: IntentReview
    rationales: Rationales
    evidence_quotes: list[EvidenceQuote] = Field(min_length=2)
    uncertainties: list[Text]

    @model_validator(mode='after')
    def consistent_axes(self):
        if (self.concern_kind == 'unknown') != (self.evidence_confidence == 'insufficient'):
            raise ValueError('unknown role requires insufficient support and vice versa')
        required_action = {
            'domain_contract': 'formalize', 'formalization_preference': 'formalize',
            'existing_specification': 'reuse_specification', 'simple_composition': 'reuse_specification',
            'tool_responsibility': 'use_tool_rules', 'mechanics': 'keep_procedural',
        }
        if self.recommendation != required_action[self.basis]:
            raise ValueError('recommendation conflicts with its declared basis')
        if self.evidence_confidence != 'supported' and not self.uncertainties:
            raise ValueError('limited/insufficient support requires explicit uncertainties')
        if self.basis == 'formalization_preference' and self.evidence_confidence == 'supported':
            raise ValueError('ambiguity preference must retain role uncertainty')
        if self.concern_kind == 'mechanics' and self.evidence_confidence == 'supported' and self.recommendation == 'formalize':
            raise ValueError('established mechanics do not justify a new domain Specification')
        if {q.axis for q in self.evidence_quotes} != {'concern_kind', 'recommendation'}:
            raise ValueError('both semantic judgments require source quotes')
        return self


def contract():
    return {'id': CONTRACT_ID, 'version': '4.0',
            'supersedes_for_future_tasks': 'specification_metrics.expression-fit.v3.1-scope-diagnostic',
            'instructions': INSTRUCTIONS, 'annotation_prompt': PROMPT, 'profile': PROFILE,
            'axes': list(AXES), 'output_schema': Annotation.model_json_schema(),
            'confidence_semantics': 'ordinal_evidence_support_not_provider_probability',
            'status': 'offline_development_contract_not_scoring_reference'}


def task_digest(case, contract_sha256):
    return digest(encoded({'contract_sha256': contract_sha256, 'case_id': case['case_id'],
                           'state_sha256': case['state_sha256'],
                           'scope_binding_sha256': case['scope_binding_sha256']}))


def validate(case, answer, contract_sha256):
    """Verify identity, structure and exact quotes, never certify a semantic label."""
    if contract_sha256 != digest(encoded(contract())):
        raise ValueError('not the current v4 contract bytes')
    if case['state_sha256'] != digest(encoded(case['state'])):
        raise ValueError('case state digest mismatch')
    scope = case['state']['evaluation_scope']
    if case['scope_binding_sha256'] != digest(encoded(scope)):
        raise ValueError('case scope digest mismatch')
    if case['state']['architecture_profile'] != PROFILE:
        raise ValueError('case architecture profile mismatch')
    if case['task_sha256'] != task_digest(case, contract_sha256):
        raise ValueError('case task digest mismatch')
    row = Annotation.model_validate(answer)
    for name in ('case_id', 'task_sha256', 'state_sha256', 'scope_binding_sha256'):
        if getattr(row, name) != case[name]:
            raise ValueError('returned case identity mismatch: ' + name)
    if row.contract_sha256 != contract_sha256 or row.scope_unit != scope['unit']:
        raise ValueError('returned contract/scope identity mismatch')
    sources = {'target': case['state']['target']['code']}
    documents = set()
    for fragment in case['state']['bounded_context']['fragments']:
        key = fragment['fragment_id']
        if key in sources:
            raise ValueError('duplicate source fragment identity')
        sources[key] = fragment.get('code', fragment.get('text', ''))
        if fragment['kind'] == 'documented_contract':
            documents.add(key)
    checked = row.intent_review.checked_document_ids
    if len(checked) != len(set(checked)) or set(checked) != documents:
        raise ValueError('document review must acknowledge exactly the supplied document IDs')
    for quote in row.evidence_quotes:
        if not quote.quote.strip() or quote.fragment_id not in sources or quote.quote not in sources[quote.fragment_id]:
            raise ValueError('quote is not an exact source excerpt')
    return {'status': 'contract_valid_not_semantically_adjudicated',
            'case_id': row.case_id, 'semantic_correctness_verified': False,
            'provider_scoring_enabled': False, 'metric_effect': 'none'}
