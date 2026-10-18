from specification_core import Specification

from .context import RoutingContext


class AnalysisUnavailableSpec(Specification[RoutingContext]):
    """Incomplete evidence must take precedence over any semantic suggestion."""

    def details(self, candidate):
        assessment = candidate.assessment
        issues = []
        if assessment.status != 'valid':
            issues.append('response_' + assessment.status)
        if assessment.labels is None:
            issues.append('labels_missing')
        if assessment.response_sha256 is None:
            issues.append('response_digest_missing')
        if assessment.binding != candidate.expected:
            issues.append('decision_binding_mismatch')
        if assessment.provider != candidate.expected_provider:
            issues.append('provider_identity_mismatch')
        if (assessment.requested_model != candidate.expected_model
                or assessment.returned_model != candidate.expected_model):
            issues.append('model_identity_mismatch')
        if any(c.binding_sha256 != candidate.expected.fingerprint() for c in candidate.checked_claims):
            issues.append('checked_claim_binding_mismatch')
        return tuple(issues)

    def _evaluate(self, candidate, recorder):
        return bool(self.details(candidate))
