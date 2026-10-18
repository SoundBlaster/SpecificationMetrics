from specification_core import Specification

from .context import RoutingContext


class RequiredAxisUnknownSpec(Specification[RoutingContext]):
    def details(self, candidate):
        labels = candidate.assessment.labels
        if labels is None:
            return ()
        axes = ['concern_kind', *candidate.expected.required_axes]
        if candidate.expected.action in ('reuse_specification', 'exclude_owned'):
            axes.append('ownership')
        if candidate.expected.action == 'delegate_tool':
            axes.append('tool_responsibility')
        return tuple(dict.fromkeys(axis for axis in axes if getattr(labels, axis) == 'unknown'))

    def _evaluate(self, candidate, recorder):
        return bool(self.details(candidate))
