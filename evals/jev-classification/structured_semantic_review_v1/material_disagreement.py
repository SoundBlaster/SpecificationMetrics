from specification_core import Specification

from .context import ResolutionContext


class MaterialDisagreementSpec(Specification[ResolutionContext]):
    """A second model cannot erase a known material claim without checked evidence."""

    def details(self, candidate):
        original = candidate.original.assessment.labels
        proposed = candidate.review.labels
        disagreements = []
        for axis in ('concern_kind', 'ownership', 'tool_responsibility'):
            before, after = getattr(original, axis), getattr(proposed, axis)
            settled = any(c.axis == axis and c.value == after
                          and c.binding_sha256 == candidate.original.expected.fingerprint()
                          for c in candidate.original.checked_claims)
            if before != 'unknown' and before != after and not settled:
                disagreements.append(axis)
        return tuple(disagreements)

    def _evaluate(self, candidate, recorder):
        return bool(self.details(candidate))
