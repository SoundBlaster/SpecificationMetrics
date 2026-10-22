from specification_core import Specification

from .context import RoutingFacts


class IncompleteCaptureSpec(Specification[RoutingFacts]):
    def _evaluate(self, candidate, recorder):
        return candidate.incomplete or candidate.baseline_route == 'stop_incomplete'
