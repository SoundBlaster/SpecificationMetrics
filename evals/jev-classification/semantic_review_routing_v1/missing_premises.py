from specification_core import Specification

from .context import RoutingContext


class MissingPremisesSpec(Specification[RoutingContext]):
    """A model cannot supply a required document that is absent from its evidence."""

    def _evaluate(self, candidate, recorder):
        return bool(candidate.missing_premises)

    def details(self, candidate):
        return tuple(gap.id for gap in candidate.missing_premises)
