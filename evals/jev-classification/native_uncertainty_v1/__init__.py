"""Offline shadow policy; never prepares or dispatches an ordinary review."""
from decimal import Decimal

from specification_core import FirstMatch, TraceRecorder

from categorical_review_bridge_v1 import replay_jev_capture
from .context import AxisMass, RoutingFacts
from .existing_review import ExistingReviewSpec
from .incomplete_capture import IncompleteCaptureSpec
from .no_strict_majority import NoStrictMajoritySpec

POLICY = 'specmetrics.native-uncertainty-shadow/v1'
PROFILE = ('jev-coreinfra', 'jev-1.13.0')
DECISION = FirstMatch.with_fallback(
    ((IncompleteCaptureSpec(), 'stop_incomplete'),
     (ExistingReviewSpec(), 'ordinary_review'),
     (NoStrictMajoritySpec(), 'ordinary_review')),
    fallback='retain_proposal', name=POLICY)


def required_axes(binding):
    axes = ['concern_kind', 'evidence_confidence', *binding.required_axes]
    if binding.action in ('reuse_specification', 'exclude_owned'):
        axes.append('ownership')
    if binding.action == 'delegate_tool':
        axes.append('tool_responsibility')
    return tuple(dict.fromkeys(axes))


def evaluate(bound, raw, *, http_status=200):
    """Reparse exact capture through the SDK before applying a new shadow rule.

    Reject unsupported provider profiles instead of inventing native metadata for
    ordinary models. Invalid native captures remain incomplete, not semantic doubt.
    """
    if (bound.context.expected_provider, bound.context.expected_model) != PROFILE:
        raise ValueError('native uncertainty profile is unsupported')
    baseline = replay_jev_capture(bound, raw, http_status=http_status).report()
    original = baseline['original_route']
    native = baseline['categorical'].get('native_results')
    axes, issues = [], []
    if original['route'] != 'stop_incomplete':
        for axis in required_axes(bound.context.expected):
            answer = native.get(axis) if isinstance(native, dict) else None
            if answer is None:
                issues.append('native_metadata_missing:' + axis)
                continue
            choice, probabilities = answer['choice'], answer['probabilities']
            # SDK validates catalog, finite values and its mass contract. Compare
            # reported decimals directly; never normalize or treat them as truth.
            selected = Decimal(str(probabilities[choice]))
            alternatives = sum((Decimal(str(value)) for key, value in probabilities.items()
                                if key != choice), Decimal(0))
            axes.append(AxisMass(axis, choice, selected, alternatives, answer['confidence']))
    facts = RoutingFacts(original['route'], bool(issues), tuple(axes))
    recorder = TraceRecorder()
    route = DECISION.decide(facts, recorder=recorder).value
    return dict(policy=POLICY, mode='offline_shadow', profile=dict(provider=PROFILE[0], model=PROFILE[1]),
        binding=original['binding'], binding_sha256=original['binding_sha256'],
        response_sha256=baseline['categorical']['response_sha256'], baseline_route=original['route'],
        baseline_findings=original['findings'], route=route,
        status={'stop_incomplete': 'analysis_incomplete', 'ordinary_review': 'needs_review',
                'retain_proposal': 'proposed_not_accepted'}[route],
        issues=issues, axes=[dict(axis=a.axis, choice=a.choice, selected_mass=str(a.selected_mass),
            alternative_mass=str(a.alternative_mass), strict_majority=a.selected_mass > a.alternative_mass,
            reported_confidence=a.reported_confidence) for a in axes],
        trace=[dict(name=event.name, outcome=event.outcome.value) for event in recorder.events],
        review_execution='not_run', shadow_review_request_prepared=False,
        baseline_review_request_prepared=baseline['review_request_sha256'] is not None, hosted_requests=0,
        automatic_fact_acceptance=False, write_authority=False, metric_effect='none',
        semantic_accuracy=None, transport_verified=False)
