"""Strict review output and immutable, source-bound resolution inputs."""
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from recommendation_policy_v1.context import Digest, Frozen, Text
from semantic_review_routing_v1.context import Axis, EvidenceGap, Labels, RoutingContext

ExactText = Annotated[str, StringConstraints(min_length=1, max_length=100000)]


class Citation(Frozen):
    axis: Axis
    fragment_id: Text
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: ExactText


class ReviewEnvelope(Frozen):
    contract: Literal['specmetrics.structured-semantic-review/v1']
    task_sha256: Digest
    decision_binding_sha256: Digest
    labels: Labels
    citations: tuple[Citation, ...] = Field(max_length=16)
    missing_evidence: tuple[EvidenceGap, ...] = Field(max_length=16)
    rationale: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class Fragment(Frozen):
    id: Text
    path: Text
    revision: Text
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    code: ExactText
    sha256: Digest


@dataclass(frozen=True)
class CitationContext:
    citation: Citation
    fragment: Fragment | None


@dataclass(frozen=True)
class ResolutionContext:
    original: RoutingContext
    review: ReviewEnvelope
    valid_citations: tuple[Citation, ...]
    invalid_citation_indices: tuple[int, ...]
    routing_issues: tuple[str, ...]


@dataclass(frozen=True)
class ResolutionFacts:
    unresolved: bool
