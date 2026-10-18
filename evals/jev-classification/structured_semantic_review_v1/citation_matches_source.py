from specification_core import Specification

from .context import CitationContext


class CitationMatchesSourceSpec(Specification[CitationContext]):
    """An exact quote must match the declared whole-line span of a bound fragment."""

    def _evaluate(self, candidate, recorder):
        citation, fragment = candidate.citation, candidate.fragment
        if fragment is None or citation.start_line > citation.end_line:
            return False
        if citation.start_line < fragment.start_line or citation.end_line > fragment.end_line:
            return False
        lines = fragment.code.splitlines(keepends=True)
        start = citation.start_line - fragment.start_line
        end = citation.end_line - fragment.start_line + 1
        return bool(citation.quote.strip()) and citation.quote == ''.join(lines[start:end])
