"""Versioned repair: affirmative mechanics and a strict annotations envelope."""
from typing import Literal

from pydantic import Field, model_validator

import intent_first_contract_v4 as previous

CONTRACT_ID = 'specification_metrics.intent-first.v4.1'
PROFILE = previous.PROFILE
encoded, digest, task_digest = previous.encoded, previous.digest, previous.task_digest


class Annotation(previous.Annotation):
    contract_id: Literal['specification_metrics.intent-first.v4.1']

    @model_validator(mode='after')
    def affirmative_mechanics(self):
        if self.recommendation == 'keep_procedural' and (
                self.concern_kind != 'mechanics' or self.evidence_confidence != 'supported'):
            raise ValueError('keep_procedural requires mechanics with supported evidence')
        return self


class Response(previous.StrictModel):
    annotations: list[Annotation] = Field(min_length=1)


def contract():
    result = previous.contract()
    result.update(id=CONTRACT_ID, version='4.1', supersedes_for_future_tasks=previous.CONTRACT_ID,
                  output_schema=Response.model_json_schema())
    result['instructions'] += (
        '\nV4.1 consistency clarification: keep_procedural requires concern_kind=mechanics '
        'AND evidence_confidence=supported. Unknown, policy, variant_behavior or merely '
        'limited support cannot justify procedural mechanics. '
        'formalization_preference specifically covers limited/insufficient support for '
        'the primary role after bounded intent lookup. For a supported inline domain '
        'rule use domain_contract; describe uncertainty about implementation separately '
        'without lowering role confidence. Return the strict object {"annotations": [...]} '
        'described by output_schema, not a bare annotation row.'
    )
    result['consistency_policy'] = {
        'keep_procedural_requires': {'concern_kind': 'mechanics', 'evidence_confidence': 'supported'},
        'formalization_preference_scope': 'limited_or_insufficient_support_for_primary_role',
        'response_envelope': 'strict_annotations_array',
    }
    return result


def validate(case, answer, contract_sha256):
    """Keep historical v4 executable and bytes unchanged; validate new v4.1 IDs."""
    if contract_sha256 != digest(encoded(contract())):
        raise ValueError('not the current v4.1 contract bytes')
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
    return {'status': 'contract_valid_not_semantically_adjudicated', 'case_id': row.case_id,
            'semantic_correctness_verified': False, 'provider_scoring_enabled': False, 'metric_effect': 'none'}


def validate_response(packet, answer, contract_sha256):
    if packet['contract_id'] != CONTRACT_ID or packet['contract_sha256'] != contract_sha256:
        raise ValueError('packet contract identity mismatch')
    response = Response.model_validate(answer)
    cases = {c['case_id']: c for c in packet['cases']}
    if len(cases) != len(packet['cases']):
        raise ValueError('duplicate packet case identity')
    if len(response.annotations) != len(cases) or {r.case_id for r in response.annotations} != set(cases):
        raise ValueError('response case set mismatch')
    return [validate(cases[row.case_id], row.model_dump(), contract_sha256) for row in response.annotations]
