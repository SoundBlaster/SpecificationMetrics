from specification_core import Specification

from .context import RoutingContext


class UnresolvedRoleSpec(Specification[RoutingContext]):
    def _evaluate(self, candidate, recorder):
        labels = candidate.assessment.labels
        return labels is not None and labels.concern_kind == 'unknown'

    def details(self, candidate):
        return ('concern_kind',)
