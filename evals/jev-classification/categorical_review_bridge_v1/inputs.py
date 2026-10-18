"""Bind categorical input to the existing four-axis evidence contract before I/O."""
import json
from dataclasses import dataclass
from typing import get_args

from mellea_jev import CategoricalTask, ChoiceQuestion

from semantic_review_routing_v1.context import Labels, RoutingContext
from structured_semantic_review_v1.preparation import MAX_RESPONSE_BYTES, fragments_from, load, sha


@dataclass(frozen=True)
class BoundTask:
    context: RoutingContext
    state_json: str
    questions_json: str

    def sdk_task(self):
        return CategoricalTask(state=load(self.state_json), questions={
            name: ChoiceQuestion(value['instructions'], value['criteria'])
            for name, value in load(self.questions_json).items()})


def bind(context: RoutingContext, *, state_json: str, questions_json: str):
    if not isinstance(context, RoutingContext):
        raise TypeError('bind requires RoutingContext')
    # Revalidate even instances made with Pydantic model_copy/model_construct.
    context = RoutingContext.model_validate_json(context.model_dump_json())
    if context.assessment.status != 'not_run':
        raise ValueError('new categorical capture requires a not_run input assessment')
    if type(state_json) is not str or type(questions_json) is not str:
        raise TypeError('state and questions must be captured JSON text')
    if len(state_json.encode()) + len(questions_json.encode()) > MAX_RESPONSE_BYTES:
        raise ValueError('categorical input exceeds size limit')
    if sha(state_json.encode()) != context.expected.evidence_sha256:
        raise ValueError('categorical state digest differs')
    state, questions = load(state_json), load(questions_json)
    if not isinstance(state, dict) or not isinstance(questions, dict):
        raise ValueError('categorical state and questions must be objects')
    if sha(json.dumps(questions, sort_keys=True).encode()) != context.expected.prompt_config_sha256:
        raise ValueError('categorical question configuration differs')
    if set(questions) != set(Labels.model_fields):
        raise ValueError('categorical routing requires all four axes')
    for axis, value in questions.items():
        if (not isinstance(value, dict) or not isinstance(value.get('instructions'), str)
                or not value['instructions'].strip() or not isinstance(value.get('criteria'), dict)
                or set(value['criteria']) != set(get_args(Labels.model_fields[axis].annotation))
                or any(not isinstance(v, str) or not v.strip() for v in value['criteria'].values())):
            raise ValueError('categorical question catalog differs')
        if set(value) - {'type', 'instructions', 'criteria'} or value.get('type', 'choice') != 'choice':
            raise ValueError('categorical routing requires Choice questions')
    profile, target, scope = state.get('architecture_profile'), state.get('target'), state.get('evaluation_scope')
    if not isinstance(profile, dict) or not isinstance(profile.get('goal'), str) or not profile['goal'].strip():
        raise ValueError('architectural goal is missing')
    if (not isinstance(target, dict) or not isinstance(scope, dict)
            or target.get('id') != context.expected.decision_id
            or scope.get('repository') != context.expected.repository
            or scope.get('revision') != context.expected.revision):
        raise ValueError('categorical source identity differs')
    fragments_from(state, context)
    return BoundTask(context, state_json, questions_json)


def verify(bound):
    if not isinstance(bound, BoundTask) or bind(bound.context, state_json=bound.state_json,
            questions_json=bound.questions_json) != bound:
        raise ValueError('categorical task was modified')
