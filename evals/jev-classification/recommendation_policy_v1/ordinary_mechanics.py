from specification_core import Specification

from .context import Facts


class OrdinaryMechanicsSpec(Specification[Facts]):
    """Procedural mechanics needs affirmative role evidence."""

    def _evaluate(self, candidate, recorder):
        return candidate.role.kind == 'mechanics' and candidate.role.support == 'supported'
