from specification_core import Specification
from .context import AcceptanceContext


class VerifiedSameDecisionOwnershipSpec(Specification[AcceptanceContext]):
    """Positive ownership needs a checked proof or approved, bound adjudication."""

    def _evaluate(self, candidate, recorder):
        return candidate.source_proof or (
            candidate.search_approved and candidate.review_approved
            and not candidate.search_failed and candidate.review_complete
            and not candidate.review_limitations and not candidate.comparison_conflict
            and candidate.same_decision_specification)
