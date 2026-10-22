from specification_core import Specification

from .context import RoutingFacts


class ExistingReviewSpec(Specification[RoutingFacts]):
    def _evaluate(self, candidate, recorder):
        return candidate.baseline_route == 'ordinary_review'
