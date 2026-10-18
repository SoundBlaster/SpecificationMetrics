from specification_core import Specification

from .context import ResolutionContext


class MissingCitationCoverageSpec(Specification[ResolutionContext]):
    def details(self, candidate):
        labels = candidate.review.labels
        missing = []
        if labels.concern_kind != 'unknown' and not any(
                c.axis == 'concern_kind' and c.fragment_id == 'target/source'
                for c in candidate.valid_citations):
            missing.append('target_role_citation')
        for axis, unknown in [('ownership', 'unknown'), ('tool_responsibility', 'unknown')]:
            if getattr(labels, axis) != unknown and not any(c.axis == axis for c in candidate.valid_citations):
                missing.append(axis)
        return tuple(missing)

    def _evaluate(self, candidate, recorder):
        return bool(self.details(candidate))
