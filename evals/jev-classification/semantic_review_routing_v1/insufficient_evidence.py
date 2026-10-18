from specification_core import Specification

from .context import RoutingContext


class InsufficientEvidenceSpec(Specification[RoutingContext]):
    def _evaluate(self, candidate, recorder):
        labels = candidate.assessment.labels
        return labels is not None and labels.evidence_confidence != 'supported'

    def details(self, candidate):
        return ('evidence_confidence',)
