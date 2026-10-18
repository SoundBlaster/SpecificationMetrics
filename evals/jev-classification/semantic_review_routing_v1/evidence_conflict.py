from specification_core import Specification

from .context import RoutingContext


class EvidenceConflictSpec(Specification[RoutingContext]):
    def details(self, candidate):
        labels = candidate.assessment.labels
        claims = [c for c in candidate.checked_claims
                  if c.binding_sha256 == candidate.expected.fingerprint()]
        conflicts = []
        for claim in claims:
            others = {c.value for c in claims if c.axis == claim.axis}
            value = getattr(labels, claim.axis) if labels is not None else 'unknown'
            if len(others) > 1 or (value != 'unknown' and value != claim.value):
                conflicts.append(claim.axis)
        return tuple(dict.fromkeys(conflicts))

    def _evaluate(self, candidate, recorder):
        return bool(self.details(candidate))
