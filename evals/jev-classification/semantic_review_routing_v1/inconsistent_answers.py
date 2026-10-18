from specification_core import Specification

from retrieval_fact_adapter_v1 import RULES
from retrieval_fact_adapter_v1.context import NativeProposal

from .context import RoutingContext


class InconsistentAnswersSpec(Specification[RoutingContext]):
    """Delegate tuple consistency to the existing shared SpecificationCore rules."""

    def _evaluate(self, candidate, recorder):
        labels = candidate.assessment.labels
        if labels is None:
            return False
        proposal = NativeProposal(labels.concern_kind, labels.evidence_confidence,
                                  labels.ownership, labels.tool_responsibility)
        outcomes = [rule.is_satisfied_by(proposal, recorder=recorder) for rule, _ in RULES]
        return not all(outcomes)

    def details(self, candidate):
        return ('shared_tuple_consistency',)
