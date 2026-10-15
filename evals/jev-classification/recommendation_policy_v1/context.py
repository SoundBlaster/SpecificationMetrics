"""Immutable, scope-bound premises. Provenance is not semantic proof by itself."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Digest = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
Kind = Literal['policy', 'variant_behavior', 'mechanics', 'unknown']
Support = Literal['supported', 'limited', 'insufficient']
Ownership = Literal['existing_specification', 'simple_composition', 'absent_in_scope', 'unknown', 'conflicting']
Tool = Literal['yes', 'no_in_scope', 'unknown', 'conflicting']
Lookup = Literal['completed', 'not_done', 'conflicting']
Action = Literal['formalize', 'reuse_specification', 'use_tool_rules', 'keep_procedural']


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class Source(Frozen):
    artifact: Text
    sha256: Digest
    locator: Text
    authority: Literal['development_premise', 'reviewed_fact', 'source_binding']


class Role(Frozen):
    kind: Kind
    support: Support
    sources: tuple[Source, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def consistent_support(self):
        if (self.kind == 'unknown') != (self.support == 'insufficient'):
            raise ValueError('unknown role requires insufficient support and vice versa')
        return self


class OwnershipFact(Frozen):
    value: Ownership
    sources: tuple[Source, ...] = ()

    @model_validator(mode='after')
    def provenance(self):
        if self.value != 'unknown' and not self.sources:
            raise ValueError('ownership claims need provenance, including scoped absence')
        return self


class ToolFact(Frozen):
    value: Tool
    sources: tuple[Source, ...] = ()

    @model_validator(mode='after')
    def provenance(self):
        if self.value != 'unknown' and not self.sources:
            raise ValueError('tool responsibility claims need provenance')
        return self


class LookupFact(Frozen):
    value: Lookup
    sources: tuple[Source, ...] = ()

    @model_validator(mode='after')
    def provenance(self):
        if self.value != 'not_done' and not self.sources:
            raise ValueError('completed/conflicting bounded lookup needs provenance')
        return self


class ConflictFact(Frozen):
    """A reviewable disagreement, not an untraceable instruction to stop."""
    contract: Literal['specmetrics.explicit-conflict/v1'] = 'specmetrics.explicit-conflict/v1'
    description: Text
    sources: tuple[Source, ...] = Field(min_length=1)


class Facts(Frozen):
    contract: Literal['specmetrics.recommendation-facts/v1'] = 'specmetrics.recommendation-facts/v1'
    case_id: Text
    state_sha256: Digest
    scope_binding_sha256: Digest
    role: Role
    ownership: OwnershipFact
    tool_responsibility: ToolFact
    intent_lookup: LookupFact
    conflicts: tuple[ConflictFact, ...] = ()

    @property
    def has_conflict(self):
        return bool(self.conflicts) or 'conflicting' in (
            self.ownership.value, self.tool_responsibility.value, self.intent_lookup.value
        ) or (self.ownership.value in ('existing_specification', 'simple_composition')
              and self.tool_responsibility.value == 'yes')
