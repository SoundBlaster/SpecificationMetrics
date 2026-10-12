"""Native Choice validation with an explicit Jev mass-warning allowance."""
from decimal import Decimal

from coreinfra_retry_run import decode
from decision_choice_contract import parse_response as strict_parse, unit

POLICY = 'jev-choice-mass-warning/v1'
STRICT_TOLERANCE = Decimal('0.000001')
MASS_ALLOWANCE = Decimal('0.01')


class ChoiceContractError(ValueError):
    """A fixed diagnostic code, never a provider-controlled error message."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ResponseIdentityError(ChoiceContractError):
    """The returned model or question identity cannot be attributed safely."""


def bounded(value, code):
    try:
        return unit(value)
    except ValueError:
        raise ChoiceContractError(code) from None


def parse_response(raw, *, provider, model, questions):
    """Keep raw numbers/labels/confidence; mass warnings never repair an answer."""
    if provider not in {'jev-coreinfra', 'luna-decision-coreinfra'}:
        raise ResponseIdentityError('unknown_provider')
    if not isinstance(questions, dict) or set(questions) != {'opportunity', 'concern_kind'}:
        raise ResponseIdentityError('unexpected_questions')
    try:
        body = decode(raw)
    except (ValueError, UnicodeError):
        raise ChoiceContractError('invalid_response_json') from None
    if not isinstance(body, dict) or body.get('model') != model:
        raise ResponseIdentityError('unexpected_returned_model')
    answers = body.get('answers')
    if provider == 'luna-decision-coreinfra':
        if not isinstance(answers, list) or len(answers) != len(questions):
            raise ResponseIdentityError('unexpected_answer_identities')
        named = {}
        for answer in answers:
            if not isinstance(answer, dict) or not isinstance(answer.get('name'), str) or answer['name'] in named:
                raise ResponseIdentityError('duplicate_or_missing_answer_identity')
            named[answer['name']] = answer
        answers = named
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ResponseIdentityError('unexpected_answer_identities')
    if provider == 'luna-decision-coreinfra':
        try:
            result = strict_parse(raw, provider=provider, model=model, questions=questions)
        except (ValueError, TypeError, KeyError):
            raise ChoiceContractError('strict_native_contract_invalid') from None
        return {**result, 'warnings': [], 'validation_policy': POLICY}
    parsed, warnings = {}, []
    for axis, question in questions.items():
        answer = answers[axis]
        if not isinstance(answer, dict) or answer.get('type') != 'choice':
            raise ChoiceContractError('expected_choice_answer')
        probabilities = answer.get('probabilities')
        if not isinstance(probabilities, dict) or set(probabilities) != set(question['criteria']):
            raise ChoiceContractError('unexpected_option_coverage')
        probabilities = {label: bounded(value, 'invalid_probability') for label, value in probabilities.items()}
        choice = answer.get('choice')
        if not isinstance(choice, str) or choice not in probabilities:
            raise ChoiceContractError('unexpected_selected_option')
        confidence = bounded(answer.get('confidence'), 'invalid_confidence')
        if probabilities[choice] != max(probabilities.values()):
            raise ChoiceContractError('selected_option_not_maximum')
        total = sum((Decimal(str(p)) for p in probabilities.values()), Decimal(0))
        residual = total - 1
        if abs(residual) > STRICT_TOLERANCE:
            applicable = (provider == 'jev-coreinfra' and model == 'jev-1.13.0'
                          and len(probabilities) in (3, 4))
            if not applicable or abs(residual) > MASS_ALLOWANCE:
                raise ChoiceContractError('probability_mass_outside_allowance')
            warnings.append({'code': 'probability_mass_deviation', 'axis': axis,
                             'policy': POLICY, 'raw_total': str(total),
                             'residual': str(residual), 'absolute_allowance': str(MASS_ALLOWANCE)})
        parsed[axis] = {'type': 'choice', 'choice': choice,
                        'probabilities': probabilities, 'confidence': confidence}
    return {'model': body['model'], 'answers': parsed, 'warnings': warnings,
            'validation_policy': POLICY,
            'confidence_semantics': 'native_provider_value_not_cross_provider_calibrated'}


def evaluate_response(body, *, provider, model, questions):
    """Return replayable validation metadata and whether identity requires a stop."""
    metadata = {'policy': POLICY, 'status': 'valid', 'warnings': [], 'rejection_code': None}
    try:
        prediction = parse_response(body, provider=provider, model=model, questions=questions)
        metadata['warnings'] = prediction['warnings']
        return prediction, metadata, False
    except ChoiceContractError as error:
        metadata.update(status='invalid', rejection_code=error.code)
        return None, metadata, isinstance(error, ResponseIdentityError)
