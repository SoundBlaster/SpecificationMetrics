from specification_core import Specification

from .context import Facts


class FormalizationPreferenceSpec(Specification[Facts]):
    """After bounded lookup, prefer formalization while retaining uncertainty."""

    def _evaluate(self, candidate, recorder):
        return candidate.role.support != 'supported' and candidate.intent_lookup.value == 'completed'
