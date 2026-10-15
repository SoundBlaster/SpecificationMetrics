from specification_core import Specification

from .context import Facts


class ExistingSpecificationSpec(Specification[Facts]):
    """Reuse proven same-decision ownership, including simple composition."""

    def _evaluate(self, candidate, recorder):
        return candidate.ownership.value in ('existing_specification', 'simple_composition')
