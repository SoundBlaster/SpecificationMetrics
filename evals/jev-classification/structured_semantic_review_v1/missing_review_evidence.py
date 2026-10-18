from specification_core import Specification

from .context import ResolutionContext


class MissingReviewEvidenceSpec(Specification[ResolutionContext]):
    def _evaluate(self, candidate, recorder):
        return bool(candidate.original.missing_premises or candidate.review.missing_evidence)

    def details(self, candidate):
        return tuple(dict.fromkeys(g.id for g in (
            *candidate.original.missing_premises, *candidate.review.missing_evidence)))
