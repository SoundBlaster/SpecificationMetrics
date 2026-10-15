"""Typed evidence for a bounded ownership adjudication, not a search engine."""
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator
from recommendation_policy_v1.context import Digest, Facts, Frozen, Text


class FileIdentity(Frozen):
    path: Text
    sha256: Digest


class Scope(Frozen):
    contract: Literal['specmetrics.ownership-scope/v1']
    facts_sha256: Digest
    repository: Text
    revision: Text
    description: Text
    files: tuple[FileIdentity, ...] = Field(min_length=1)


class Declaration(Frozen):
    candidate_id: Text
    kind: Literal['specification', 'code_candidate', 'intent_document', 'unknown']
    path: Text
    symbol: Text
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    excerpt_sha256: Digest


class Retrieval(Frozen):
    kind: Literal['exhaustive_catalogue', 'ranked_candidates']
    query_sha256: Digest
    index_sha256: Digest
    configuration_sha256: Digest
    limit: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def bounded_ranking(self):
        if (self.kind == 'ranked_candidates') != (self.limit is not None):
            raise ValueError('ranked retrieval requires a limit; exhaustive catalogue cannot have one')
        return self


class Search(Frozen):
    contract: Literal['specmetrics.ownership-search/v1']
    facts_sha256: Digest
    scope_sha256: Digest
    producer: Text
    status: Literal['complete', 'partial', 'failed']
    retrieval: Retrieval
    processed_files: tuple[FileIdentity, ...]
    candidates: tuple[Declaration, ...]
    unresolved: tuple[Text, ...]


class Comparison(Frozen):
    candidate_id: Text
    relation: Literal['same_decision', 'different_decision', 'unknown', 'conflicting']
    rationale: Text


class Review(Frozen):
    contract: Literal['specmetrics.ownership-review/v1']
    facts_sha256: Digest
    search_sha256: Digest
    reviewer: Text
    status: Literal['complete', 'partial']
    # A separately approved judgment about coverage, not a scanner's self-rating.
    catalogue_closure: Literal['complete_in_declared_scope', 'not_established']
    comparisons: tuple[Comparison, ...]
    unresolved: tuple[Text, ...]


@dataclass(frozen=True)
class Trust:
    """Caller-selected exact artifacts. Never load this authority from the submitted bundle."""
    scope_sha256: str
    approved_searches: frozenset[str] = frozenset()
    approved_reviews: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AcceptanceContext:
    facts: Facts
    source_proof: bool = False
    search_approved: bool = False
    review_approved: bool = False
    search_failed: bool = False
    search_complete: bool = False
    inventory_complete: bool = False
    search_limitations: bool = False
    review_complete: bool = False
    comparisons_complete: bool = False
    review_limitations: bool = False
    comparison_conflict: bool = False
    catalogue_closed: bool = False
    ranked: bool = True
    same_decision_specification: bool = False
    all_candidates_different: bool = False
    reasons: tuple[str, ...] = ()
