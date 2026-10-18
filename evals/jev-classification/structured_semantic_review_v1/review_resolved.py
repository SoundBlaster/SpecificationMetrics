from specification_core import Specification

from .context import ResolutionFacts


class ReviewResolvedSpec(Specification[ResolutionFacts]):
    """Resolution is provisional and requires every resolution check to pass."""

    def _evaluate(self, candidate, recorder):
        return not candidate.unresolved
