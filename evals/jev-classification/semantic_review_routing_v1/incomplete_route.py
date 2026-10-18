from specification_core import Specification

from .context import RouteFacts


class IncompleteRouteSpec(Specification[RouteFacts]):
    def _evaluate(self, candidate, recorder):
        return candidate.incomplete
