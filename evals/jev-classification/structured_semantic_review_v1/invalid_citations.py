from specification_core import Specification

from .context import ResolutionContext


class InvalidCitationsSpec(Specification[ResolutionContext]):
    def _evaluate(self, candidate, recorder):
        return bool(candidate.invalid_citation_indices)

    def details(self, candidate):
        return tuple(str(index) for index in candidate.invalid_citation_indices)
