from specification_core import Specification
from .context import AcceptanceContext


class ReviewedScopedAbsenceSpec(Specification[AcceptanceContext]):
    """No match counts only after complete scoped search and complete adjudication."""

    def _evaluate(self, candidate, recorder):
        return (candidate.search_approved and candidate.review_approved
                and candidate.search_complete and candidate.inventory_complete
                and not candidate.search_limitations and candidate.review_complete
                and candidate.comparisons_complete and not candidate.review_limitations
                and not candidate.comparison_conflict and candidate.catalogue_closed
                and not candidate.ranked and candidate.all_candidates_different)
