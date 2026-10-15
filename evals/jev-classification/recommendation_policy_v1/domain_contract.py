from specification_core import Specification

from .context import Facts


class DomainContractSpec(Specification[Facts]):
    """Supported inline policy or variant behavior deserves formalization."""

    def _evaluate(self, candidate, recorder):
        return candidate.role.support == 'supported' and candidate.role.kind in ('policy', 'variant_behavior')
