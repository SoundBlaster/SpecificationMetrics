from specification_core import Specification

from .context import ResolutionContext


class UnresolvedRoutingSpec(Specification[ResolutionContext]):
    def _evaluate(self, candidate, recorder):
        return bool(candidate.routing_issues)

    def details(self, candidate):
        return candidate.routing_issues
