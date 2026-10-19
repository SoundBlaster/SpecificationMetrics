"""Enforce the native uncertainty policy before preparing independent Luna review."""
from dataclasses import dataclass

from categorical_review_bridge_v1 import replay_jev_capture
from categorical_review_bridge_v1.inputs import BoundTask
from native_uncertainty_v1 import evaluate
from structured_semantic_review_v1.preparation import (
    GUIDANCE, MAX_OUTPUT_TOKENS, MODEL, PreparedReview, encoded, fragments_from, load, sha,
)
from structured_semantic_review_v1.context import ReviewEnvelope

from .inspection import _inspect_selected

CONTRACT = 'specmetrics.native-review-cascade/v1'


def _routing(selection):
    return dict(contract=CONTRACT, uncertainty_policy=selection['policy'], mode='enforced_review_selection',
        **{key: selection[key] for key in ('route', 'status', 'axes', 'issues', 'trace', 'baseline_findings',
                                          'binding', 'binding_sha256', 'response_sha256', 'baseline_route')})


def _wire(prepared):
    # The independent task/schema are identical to rich review v1. Its frozen
    # prepare/verify entry points intentionally accept only the old route, so the
    # new consumer owns selection validation instead of falsifying that context.
    return dict(model=MODEL, store=False, stream=False, truncation='disabled',
        reasoning=dict(effort='low'), max_output_tokens=MAX_OUTPUT_TOKENS,
        instructions=GUIDANCE + '\nOriginal questions: ' + prepared.questions_json,
        input=encoded(dict(task_sha256=prepared.task_sha256(),
            decision_binding_sha256=prepared.original.expected.fingerprint(),
            decision_binding=prepared.original.expected.model_dump(mode='json'),
            state=load(prepared.state_json), fragments=[f.model_dump(mode='json') for f in prepared.fragments],
            known_missing_evidence=[g.model_dump(mode='json') for g in prepared.original.missing_premises])),
        text=dict(format=dict(type='json_schema', name='semantic_review', strict=True,
                              schema=ReviewEnvelope.model_json_schema())))


@dataclass(frozen=True)
class NativeCascadePlan:
    """Rebuild derived state at each seam; callers cannot mix labels/review plans."""

    bound: BoundTask
    raw: bytes | None
    http_status: int = 200

    def __post_init__(self):
        self._parts()

    def _parts(self):
        baseline = replay_jev_capture(self.bound, self.raw, http_status=self.http_status)
        selection = evaluate(self.bound, self.raw, http_status=self.http_status)
        context = baseline.context
        prepared = (PreparedReview(context, self.bound.state_json, self.bound.questions_json,
                    fragments_from(load(self.bound.state_json), context))
                    if selection['route'] == 'ordinary_review' else None)
        return baseline, selection, prepared

    @property
    def review(self):
        return self._parts()[2]

    def report(self):
        baseline, selection, prepared = self._parts()
        return dict(contract=CONTRACT, original_route=baseline.report()['original_route'],
            categorical=baseline.report()['categorical'],
            routing=_routing(selection),
            review_request_sha256=sha(encoded(_wire(prepared)).encode()) if prepared else None,
            review_status='not_run' if prepared else 'not_needed' if selection['route'] == 'retain_proposal' else 'unavailable',
            hosted_requests=0, automatic_fact_acceptance=False, write_authority=False,
            metric_effect='none', transport_verified=False, semantic_accuracy=None)

    def review_request(self):
        prepared = self.review
        return _wire(prepared) if prepared else None

    def inspect_review(self, raw=None, *, captured_request_sha256=None, execution_status='not_run'):
        baseline, selection, prepared = self._parts()
        if prepared is None:
            raise ValueError('ordinary review was not selected')
        return _inspect_selected(prepared, baseline.report()['original_route'], _routing(selection),
            request_sha256=sha(encoded(_wire(prepared)).encode()), raw=raw,
            captured_request_sha256=captured_request_sha256, execution_status=execution_status)


def plan_capture(bound, raw, *, http_status=200):
    return NativeCascadePlan(bound, raw, http_status)
