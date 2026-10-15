from specification_core import Specification

from .context import Facts


class ToolResponsibilitySpec(Specification[Facts]):
    """Formatting/linting belongs to tool rules; this does not prove configuration."""

    def _evaluate(self, candidate, recorder):
        return candidate.tool_responsibility.value == 'yes'
