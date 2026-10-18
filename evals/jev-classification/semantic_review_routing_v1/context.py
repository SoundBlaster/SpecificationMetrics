"""Immutable inputs to an offline policy; checked claims are caller premises."""
import hashlib
import json
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from recommendation_policy_v1.context import Digest, Frozen, Kind, Source, Support, Text

Axis = Literal['concern_kind', 'evidence_confidence', 'ownership', 'tool_responsibility']
Action = Literal['assess_role', 'reuse_specification', 'exclude_owned', 'delegate_tool', 'create_specification']


class DecisionBinding(Frozen):
    repository: Text
    revision: Annotated[str, StringConstraints(pattern=r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$')]
    path: Text
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    decision_id: Text
    evidence_sha256: Digest
    rubric_version: Text
    category_version: Text
    prompt_config_sha256: Digest
    action: Action = 'assess_role'
    required_axes: tuple[Axis, ...] = ()

    @model_validator(mode='after')
    def scope(self):
        if self.end_line < self.start_line:
            raise ValueError('decision span is reversed')
        if self.path.startswith('/') or '\\' in self.path or any(p in ('', '.', '..') for p in self.path.split('/')):
            raise ValueError('source path must be repository relative and normalized')
        if len(set(self.required_axes)) != len(self.required_axes):
            raise ValueError('required axes must be unique')
        return self

    def fingerprint(self):
        raw = json.dumps(self.model_dump(mode='json'), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()


class Labels(Frozen):
    # Contradictory but well-shaped answers must survive for consistency review.
    concern_kind: Kind
    evidence_confidence: Support
    ownership: Literal['existing_specification', 'simple_composition', 'unknown']
    tool_responsibility: Literal['yes', 'unknown']


class CapturedAssessment(Frozen):
    status: Literal['valid', 'invalid', 'missing', 'transport_failed', 'refused', 'truncated', 'not_run']
    provider: Text
    requested_model: Text
    returned_model: Text | None = None
    response_sha256: Digest | None = None
    binding: DecisionBinding | None = None
    labels: Labels | None = None


class CheckedClaim(Frozen):
    """A source-bound adapter assertion, never a model-created accepted fact."""
    binding_sha256: Digest
    axis: Literal['concern_kind', 'ownership', 'tool_responsibility']
    value: Literal['policy', 'mechanics', 'variant_behavior', 'existing_specification',
                   'simple_composition', 'absent_in_scope', 'yes', 'no_in_scope']
    relation: Literal['label_evidence', 'exact_decision', 'tool_rule', 'scoped_absence']
    subject: Text
    source: Source

    @model_validator(mode='after')
    def checked_source(self):
        allowed = {
            'concern_kind': {'policy', 'mechanics', 'variant_behavior'},
            'ownership': {'existing_specification', 'simple_composition', 'absent_in_scope'},
            'tool_responsibility': {'yes', 'no_in_scope'},
        }
        if self.value not in allowed[self.axis]:
            raise ValueError('claim value is incompatible with its axis')
        if self.source.authority not in ('source_binding', 'reviewed_fact'):
            raise ValueError('checked claims require source-bound or reviewed premises')
        relations = {
            'label_evidence': self.axis == 'concern_kind',
            'exact_decision': self.axis == 'ownership' and self.value != 'absent_in_scope',
            'tool_rule': self.axis == 'tool_responsibility' and self.value == 'yes',
            'scoped_absence': self.value in ('absent_in_scope', 'no_in_scope'),
        }
        if not relations[self.relation]:
            raise ValueError('claim relation is incompatible with its value')
        return self


class EvidenceGap(Frozen):
    id: Text
    description: Text


class RoutingContext(Frozen):
    expected: DecisionBinding
    expected_provider: Text
    expected_model: Text
    assessment: CapturedAssessment
    missing_premises: tuple[EvidenceGap, ...] = ()
    checked_claims: tuple[CheckedClaim, ...] = ()


@dataclass(frozen=True)
class RouteFacts:
    incomplete: bool
    semantic_review: bool
