from specification_core import Specification

from .context import NativeProposal


class ResponsibilitiesCompatibleSpec(Specification[NativeProposal]):
    """Conflicting Specification/tool ownership requires adjudication."""

    def _evaluate(self, candidate, recorder):
        return not (candidate.ownership in ('existing_specification', 'simple_composition')
                    and candidate.tool == 'yes')
