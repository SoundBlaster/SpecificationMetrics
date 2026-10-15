from specification_core import Specification
from .context import AcceptanceContext


class BlockedOwnershipTransitionSpec(Specification[AcceptanceContext]):
    """An ownership supplement cannot rewrite established or conflicting facts."""

    def _evaluate(self, candidate, recorder):
        return (candidate.facts.has_conflict or candidate.facts.ownership.value != 'unknown'
                or (candidate.facts.tool_responsibility.value == 'yes'
                    and (candidate.source_proof or candidate.same_decision_specification)))
