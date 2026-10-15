from specification_core import Specification

from .context import Facts


class ConflictingFactsSpec(Specification[Facts]):
    """Never turn conflicting authorities into an automatic recommendation."""

    def _evaluate(self, candidate, recorder):
        return candidate.has_conflict
