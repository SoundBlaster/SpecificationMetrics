from specification_core import Specification

from .context import RouteFacts


class OrdinaryReviewRouteSpec(Specification[RouteFacts]):
    def _evaluate(self, candidate, recorder):
        return candidate.semantic_review
