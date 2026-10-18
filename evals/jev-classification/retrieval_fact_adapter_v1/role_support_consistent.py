from specification_core import Specification

from .context import NativeProposal


class RoleSupportConsistentSpec(Specification[NativeProposal]):
    """An unsettled primary role and insufficient support must remain paired."""

    def _evaluate(self, candidate, recorder):
        return (candidate.role == 'unknown') == (candidate.support == 'insufficient')
