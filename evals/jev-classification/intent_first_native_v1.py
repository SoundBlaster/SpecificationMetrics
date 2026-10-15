"""Native Choice projection of v4.1; never fabricate a rich annotation."""
from decimal import Decimal

from coreinfra_retry_run import decode
from decision_choice_contract_v2 import ChoiceContractError, ResponseIdentityError, bounded

POLICY = 'specmetrics.intent-first-native-choice/v1'
PROVIDERS = {
    'jev-coreinfra': ('jev-1.13.0', 'https://hub.coreinfra.ai/typesafe/api/v1/systemone'),
    'luna-decision-coreinfra': ('gpt-6-luna', 'https://hub.coreinfra.ai/openai/api/v1/decisions'),
}
COMMON = (
    'The goal is uniform, addressable, composable and observable domain rules for human and AI SDLC. '
    'Judge ONLY state.target in state.evaluation_scope: shared_definition across supplied uses, or '
    'the exact expression for the selected bound_application, not the call or whole caller. '
    'Use ONLY the supplied architecture_profile, target, bounded_context and evaluation_scope. '
    'Inspect supplied intent/proposal/spec documents with their stated authority; record no invented facts. '
    'Missing documents do not force uncertainty if code establishes the contract. '
    'After bounded intent lookup prefer formalization if primary role remains ambiguous. '
    'Reuse an existing same-decision Specification through its evaluation path, including simple NOT/AND/OR; '
    'Boolean facts alone are not Specifications and operators alone require no wrapper. '
    'Formatting/linting belong to tool rule sets; this does not prove configured enforcement. '
    'This is a native Choice projection: select the requested category, not JSON/rationales/citations. '
)
QUESTIONS = {
    'concern_kind': {'type': 'choice', 'instructions': COMMON + 'Classify primary responsibility independently of recommendation.',
        'criteria': {
            'policy': 'Decides domain admissibility, authority, lifecycle or which obligation has precedence.',
            'variant_behavior': 'Selects HOW an already established domain activity is implemented for a variant.',
            'mechanics': 'Representation, parsing, transport or adaptation without a distinct domain decision.',
            'unknown': 'Supplied evidence cannot settle primary role; pair with insufficient evidence support.'}},
    'evidence_confidence': {'type': 'choice', 'instructions': COMMON +
        'Classify evidence support for concern_kind. This ordinal category is NOT your numeric native provider confidence.',
        'criteria': {
            'supported': 'Direct code/contract witness establishes primary role.',
            'limited': 'Relevant evidence supports a tentative role but remains incomplete or conflicting.',
            'insufficient': 'Primary role cannot be settled; concern_kind must remain unknown.'}},
    'recommendation': {'type': 'choice', 'instructions': COMMON +
        'Choose architectural action. Retain role uncertainty instead of converting it to affirmative mechanics.',
        'criteria': {
            'formalize': 'Inline domain decision, or meaningful role ambiguity after intent lookup. One use/pure contract is enough.',
            'reuse_specification': 'Same decision already belongs to a Specification evaluation or simple recognized composition; no wrapper required.',
            'use_tool_rules': 'Formatter/linter responsibility; use existing tool rule management without claiming configured exact enforcement.',
            'keep_procedural': 'ONLY affirmatively established ordinary mechanics with supported evidence and no distinct domain decision.'}},
}


def wire_body(provider, state):
    if provider not in PROVIDERS:
        raise ValueError('unknown provider')
    model, _ = PROVIDERS[provider]
    if provider == 'jev-coreinfra':
        return {'model': model, 'state': state, 'questions': QUESTIONS}
    return {'model': model, 'input': state, 'questions': [
        {'name': axis, 'type': 'choice', 'instructions': q['instructions'],
         'choices': [{'value': label, 'description': text} for label, text in sorted(q['criteria'].items())]}
        for axis, q in sorted(QUESTIONS.items())]}


def tuple_violations(labels):
    errors = []
    role, support, action = (labels[k] for k in ('concern_kind', 'evidence_confidence', 'recommendation'))
    if (role == 'unknown') != (support == 'insufficient'):
        errors.append('unknown_requires_insufficient_and_vice_versa')
    if action == 'keep_procedural' and (role, support) != ('mechanics', 'supported'):
        errors.append('procedural_requires_supported_mechanics')
    if action == 'formalize' and (role, support) == ('mechanics', 'supported'):
        errors.append('established_mechanics_do_not_justify_formalization')
    return errors


def parse_response(raw, *, provider, model):
    if provider not in PROVIDERS or model != PROVIDERS[provider][0]:
        raise ResponseIdentityError('unexpected_requested_provider_or_model')
    try:
        body = decode(raw)
    except (ValueError, UnicodeError):
        raise ChoiceContractError('invalid_response_json') from None
    if not isinstance(body, dict) or body.get('model') != model:
        raise ResponseIdentityError('unexpected_returned_model')
    answers = body.get('answers')
    luna = provider == 'luna-decision-coreinfra'
    if luna:
        if not isinstance(answers, list) or len(answers) != len(QUESTIONS):
            raise ResponseIdentityError('unexpected_answer_identities')
        named = {}
        for answer in answers:
            if not isinstance(answer, dict) or not isinstance(answer.get('name'), str) or answer['name'] in named:
                raise ResponseIdentityError('duplicate_or_missing_answer_identity')
            named[answer['name']] = answer
        answers = named
    if not isinstance(answers, dict) or set(answers) != set(QUESTIONS):
        raise ResponseIdentityError('unexpected_answer_identities')
    parsed, warnings = {}, []
    for axis, question in QUESTIONS.items():
        answer = answers[axis]
        if not isinstance(answer, dict) or answer.get('type') != 'choice':
            raise ChoiceContractError('expected_choice_answer')
        probabilities = answer.get('probabilities')
        if luna:
            if not isinstance(probabilities, list):
                raise ChoiceContractError('expected_probability_array')
            mapped = {}
            for item in probabilities:
                if not isinstance(item, dict) or not isinstance(item.get('value'), str) or item['value'] in mapped:
                    raise ChoiceContractError('duplicate_or_missing_option_identity')
                mapped[item['value']] = item.get('probability')
            probabilities = mapped
        if not isinstance(probabilities, dict) or set(probabilities) != set(question['criteria']):
            raise ChoiceContractError('unexpected_option_coverage')
        probabilities = {k: bounded(v, 'invalid_probability') for k, v in probabilities.items()}
        choice = answer.get('choice')
        if not isinstance(choice, str) or choice not in probabilities:
            raise ChoiceContractError('unexpected_selected_option')
        confidence = bounded(answer.get('confidence'), 'invalid_confidence')
        if probabilities[choice] != max(probabilities.values()):
            raise ChoiceContractError('selected_option_not_maximum')
        total = sum((Decimal(str(v)) for v in probabilities.values()), Decimal(0))
        if abs(total - 1) > Decimal('0.000001'):
            if luna or abs(total - 1) > Decimal('0.01'):
                raise ChoiceContractError('probability_mass_outside_allowance')
            warnings.append({'code': 'probability_mass_deviation', 'axis': axis, 'raw_total': str(total),
                             'absolute_allowance': '0.01', 'policy': POLICY})
        parsed[axis] = {'choice': choice, 'probabilities': probabilities, 'provider_confidence': confidence}
    labels = {axis: answer['choice'] for axis, answer in parsed.items()}
    violations = tuple_violations(labels)
    return {'requested_model': model, 'returned_model': body['model'], 'answers': parsed, 'labels': labels,
            'warnings': warnings, 'validation_policy': POLICY, 'tuple_violations': violations,
            'tuple_consistent': not violations, 'full_v4_1_annotation': False,
            'semantic_correctness_verified': False, 'provider_scoring_enabled': False,
            'confidence_semantics': 'ordinal_choice_separate_from_uncalibrated_native_provider_confidence',
            'metric_effect': 'none'}
