from specification_core import Specification

from .context import RoutingFacts


class NoStrictMajoritySpec(Specification[RoutingFacts]):
    """A plurality or tie is insufficient to bypass independent review."""

    def _evaluate(self, candidate, recorder):
        return any(axis.selected_mass <= axis.alternative_mass for axis in candidate.axes)
