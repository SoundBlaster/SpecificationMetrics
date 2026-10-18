"""Categorical SDK -> unchanged routing Specifications -> optional rich-review task."""
from dataclasses import dataclass

import httpx2
from mellea_jev import CategoricalResult, JevError, TypeSafeProvider, project_choice_results

from semantic_review_routing_v1 import evaluate
from semantic_review_routing_v1.context import CapturedAssessment, Labels, RoutingContext
from structured_semantic_review_v1 import inspect as inspect_review
from structured_semantic_review_v1.preparation import (
    MAX_RESPONSE_BYTES, PreparedReview, encoded, load, prepare, request_body, request_sha256, sha,
    verify as verify_review,
)

from .inputs import BoundTask, bind, verify
from .native_batch import NativeBatchCategoricalProvider

CONTRACT = 'specmetrics.categorical-review-bridge/v1'
JEV_ENDPOINT = 'https://hub.coreinfra.ai/typesafe/api/v1/systemone'


@dataclass(frozen=True)
class CascadePlan:
    context_json: str
    categorical_json: str
    review: PreparedReview | None

    def __post_init__(self):
        self._validated()

    def _validated(self):
        # Request identity deliberately excludes the first-stage labels. The
        # resolution context must nevertheless retain that exact assessment.
        load(self.context_json)
        context = RoutingContext.model_validate_json(self.context_json)
        summary = load(self.categorical_json)
        assessment = context.assessment
        if (not isinstance(summary, dict) or summary.get('status') != assessment.status
                or summary.get('response_sha256') != assessment.response_sha256):
            raise ValueError('categorical plan capture differs from its assessment')
        if assessment.labels is not None and summary.get('answers') != assessment.labels.model_dump(mode='json'):
            raise ValueError('categorical plan labels differ from its assessment')
        if assessment.status == 'valid' and any(
                key not in summary or summary[key] != getattr(assessment, key)
                for key in ('requested_model', 'returned_model')):
            raise ValueError('categorical plan model metadata differs from its assessment')
        route = evaluate(context)
        if (self.review is not None) != (route['route'] == 'ordinary_review'):
            raise ValueError('categorical plan review selection differs from its route')
        if self.review is not None:
            if not isinstance(self.review, PreparedReview) or self.review.original != context:
                raise ValueError('categorical plan review context differs from its assessment')
            verify_review(self.review)
        return context, summary, route

    @property
    def context(self):
        return self._validated()[0]

    def report(self):
        _, summary, route = self._validated()
        return dict(contract=CONTRACT, original_route=route,
            categorical=summary,
            review_request_sha256=request_sha256(self.review) if self.review else None,
            review_status=route['review_status'],
            hosted_requests=0, hosted_request_count_scope='adapter_only_not_upstream_capture',
            automatic_fact_acceptance=False, write_authority=False,
            metric_effect='none', transport_verified=False,
            provenance_scope='caller_bound_categorical_capture_not_authenticated_transport')

    def review_request(self):
        self._validated()
        return request_body(self.review) if self.review else None

    def inspect_review(self, raw=None, *, captured_request_sha256=None, execution_status='not_run'):
        self._validated()
        if self.review is None:
            raise ValueError('ordinary review was not selected')
        return inspect_review(self.review, raw, captured_request_sha256=captured_request_sha256,
                              execution_status=execution_status)


def categorical_plan(bound: BoundTask, result: CategoricalResult | None, *,
                     response_sha256: str | None, status='valid', diagnostic=None):
    """Adapt caller-bound SDK data; the supplied response hash is not attestation.

    Ordinary categorical results have no native distribution. Rich review is
    independently prepared after routing; categorical labels cannot supply it.
    """
    verify(bound)
    if result is not None and not isinstance(result, CategoricalResult):
        raise TypeError('result must be a CategoricalResult')
    if (status == 'valid') != (result is not None) or (status == 'valid' and response_sha256 is None):
        raise ValueError('valid categorical capture requires a result and response digest')
    summary = dict(status=status, diagnostic=diagnostic, response_sha256=response_sha256)
    assessment = dict(status=status, provider=bound.context.expected_provider,
                      requested_model=bound.context.expected_model, response_sha256=response_sha256)
    if result is not None:
        # Labels validates exact axis coverage and enums; no semantic repair.
        try:
            labels = Labels(**dict(result.answers))
        except (ValueError, TypeError):
            labels = None
            assessment['status'] = summary['status'] = 'invalid'
            summary['diagnostic'] = 'invalid_category_labels'
        if result.requested_model is None:
            assessment['status'] = summary['status'] = 'invalid'
            summary['diagnostic'] = 'missing_requested_model'
        assessment.update(requested_model=result.requested_model or bound.context.expected_model,
                          returned_model=result.returned_model, binding=bound.context.expected, labels=labels)
        native = None
        if result.native_results is not None:
            try:
                projected = project_choice_results(bound.sdk_task(), result.native_results)
                if dict(projected.answers) != dict(result.answers) or projected.returned_model != result.returned_model:
                    raise ValueError('native projection differs')
                native = {name: dict(choice=r.choice, confidence=r.confidence,
                    probabilities=dict(r.probabilities), model=r.model) for name, r in result.native_results.items()}
            except (ValueError, TypeError, KeyError):
                assessment['status'] = summary['status'] = 'invalid'
                summary['diagnostic'] = 'invalid_native_projection'
        summary.update(answers=dict(result.answers), requested_model=result.requested_model,
            returned_model=result.returned_model, request_id=result.request_id, adapter_revision=result.adapter_revision,
            reported_usage=None if result.usage is None else dict(input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens, cost_usd=result.usage.cost_usd),
            settings=dict(result.settings or {}), native_results=native)
    context = bound.context.model_copy(update=dict(assessment=CapturedAssessment(**assessment)))
    route = evaluate(context)
    review = (prepare(context, state_json=bound.state_json, questions_json=bound.questions_json)
              if route['route'] == 'ordinary_review' else None)
    return CascadePlan(context.model_dump_json(), encoded(summary), review)


def replay_jev_capture(bound: BoundTask, raw: bytes | None, *, http_status=200, request_id=None):
    """Parse one caller-selected HTTP capture via SDK mock transport; zero network.

    The observed mock dispatch is a parser exercise, not another hosted call.
    A protocol/model failure stops routing; it never invokes an ordinary model.
    """
    verify(bound)
    if bound.context.expected_provider != 'jev-coreinfra':
        raise ValueError('native replay requires the Jev provider identity')
    if type(http_status) is not int or not 100 <= http_status <= 599:
        raise ValueError('invalid captured HTTP status')
    digest = sha(raw) if type(raw) is bytes else None
    if http_status != 200:
        return categorical_plan(bound, None, response_sha256=digest,
                                status='transport_failed', diagnostic='http_error')
    if type(raw) is not bytes or not raw or len(raw) > MAX_RESPONSE_BYTES:
        return categorical_plan(bound, None, response_sha256=digest,
                                status='invalid', diagnostic='missing_or_oversized_response')
    try:
        load(raw)  # SDK JSON parsing must not silently accept duplicate keys.
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return categorical_plan(bound, None, response_sha256=digest,
                                status='invalid', diagnostic='invalid_response_json')
    task, calls = bound.sdk_task(), []

    def handle(request):
        request.read()
        payload = load(request.content)
        expected = dict(model=bound.context.expected_model, state=task.state,
                        questions={name: q.to_payload() for name, q in task.questions.items()})
        if request.method != 'POST' or str(request.url) != JEV_ENDPOINT or payload != expected or calls:
            raise ValueError('SDK replay request differs or repeats')
        calls.append(sha(request.content))
        headers = {'content-type': 'application/json'}
        if request_id is not None:
            headers['x-typesafe-request-id'] = request_id
        return httpx2.Response(200, content=raw, headers=headers)

    try:
        with TypeSafeProvider(api_key='offline-fixture-not-a-credential',
                model=bound.context.expected_model, endpoint_url=JEV_ENDPOINT,
                transport=httpx2.MockTransport(handle)) as provider:
            result = NativeBatchCategoricalProvider(provider).classify(task)
        if len(calls) != 1:
            raise ValueError('SDK replay dispatch count differs')
    except (JevError, ValueError, TypeError, KeyError) as error:
        return categorical_plan(bound, None, response_sha256=digest,
                                status='invalid', diagnostic=type(error).__name__)
    return categorical_plan(bound, result, response_sha256=digest)
