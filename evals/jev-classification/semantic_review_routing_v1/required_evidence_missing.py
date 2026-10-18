from specification_core import Specification

from .context import RoutingContext


class RequiredEvidenceMissingSpec(Specification[RoutingContext]):
    """Recommendations need action-specific decision bindings, not just labels."""

    def details(self, candidate):
        labels = candidate.assessment.labels
        if labels is None:
            return ()
        issues = []
        claims = [c for c in candidate.checked_claims
                  if c.binding_sha256 == candidate.expected.fingerprint()]
        action = candidate.expected.action
        if action in ('reuse_specification', 'exclude_owned'):
            if not any(c.axis == 'ownership' and c.relation == 'exact_decision'
                       and c.value == labels.ownership for c in claims):
                issues.append('exact_specification_binding')
        elif action == 'delegate_tool':
            if not any(c.axis == 'tool_responsibility' and c.relation == 'tool_rule' for c in claims):
                issues.append('tool_rule_binding')
        elif action == 'create_specification':
            if not any(c.axis == 'ownership' and c.value == 'absent_in_scope'
                       and c.relation == 'scoped_absence' for c in claims):
                issues.append('scoped_ownership_absence')
        return tuple(dict.fromkeys(issues))

    def _evaluate(self, candidate, recorder):
        return bool(self.details(candidate))
