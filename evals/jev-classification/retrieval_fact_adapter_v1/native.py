"""Decode the four-question projection without normalizing provider numbers."""
from decimal import Decimal

from coreinfra_retry_run import decode
from decision_choice_contract_v2 import ChoiceContractError, ResponseIdentityError, bounded
from prepare_retrieval_context_v1 import PROVIDERS, QUESTIONS

POLICY = 'specmetrics.retrieval-native-choice/v1'
MAX_RESPONSE_BYTES = 1024 * 1024


def parse_response(raw, *, provider, model):
    if provider not in PROVIDERS or model != PROVIDERS[provider][0]:
        raise ResponseIdentityError('unexpected_requested_provider_or_model')
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ChoiceContractError('response_too_large')
    try:
        body = decode(raw)
    except (ValueError, UnicodeError, RecursionError):
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
        total = sum((Decimal(str(p)) for p in probabilities.values()), Decimal(0))
        if abs(total - 1) > Decimal('0.000001'):
            allow = (provider == 'jev-coreinfra' and model == 'jev-1.13.0'
                     and len(probabilities) in (3, 4) and abs(total - 1) <= Decimal('0.01'))
            if not allow:
                raise ChoiceContractError('probability_mass_outside_allowance')
            warnings.append(dict(code='probability_mass_deviation', axis=axis, raw_total=str(total),
                                 absolute_allowance='0.01', policy=POLICY))
        parsed[axis] = dict(choice=choice, probabilities=probabilities, provider_confidence=confidence)
    return dict(returned_model=body['model'], answers=parsed,
                labels={axis: answer['choice'] for axis, answer in parsed.items()}, warnings=warnings,
                validation_policy=POLICY,
                confidence_semantics='ordinal_support_separate_from_uncalibrated_native_provider_confidence')
