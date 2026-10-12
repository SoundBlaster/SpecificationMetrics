"""Strict native Choice decoding for the matched expression experiment only."""
import math

from coreinfra_retry_run import decode


def unit(value):
    if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
        raise ValueError("Expected a finite unit probability")
    return value


def parse_response(raw, *, provider, model, questions):
    """Reject refusals/malformed results; never repair or infer a missing label."""
    if provider not in {"jev-coreinfra", "luna-decision-coreinfra"}:
        raise ValueError("Unknown provider")
    if not isinstance(questions, dict) or set(questions) != {"opportunity", "concern_kind"}:
        raise ValueError("Expected the two classification questions")
    body = decode(raw)
    if not isinstance(body, dict) or body.get("model") != model:
        raise ValueError("Unexpected returned model")
    answers = body.get("answers")
    if provider == "luna-decision-coreinfra":
        if not isinstance(answers, list) or len(answers) != len(questions):
            raise ValueError("Expected exactly two native answers")
        named = {}
        for answer in answers:
            if not isinstance(answer, dict) or not isinstance(answer.get("name"), str) or answer["name"] in named:
                raise ValueError("Missing or duplicate answer identity")
            named[answer["name"]] = answer
        answers = named
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ValueError("Unexpected answer identities")
    normalized = {}
    for axis, question in questions.items():
        answer = answers[axis]
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise ValueError("Expected Choice, not refusal or another answer type")
        probabilities = answer.get("probabilities")
        if provider == "luna-decision-coreinfra":
            if not isinstance(probabilities, list):
                raise ValueError("Expected native probability array")
            mapped = {}
            for item in probabilities:
                if not isinstance(item, dict) or not isinstance(item.get("value"), str) or item["value"] in mapped:
                    raise ValueError("Missing or duplicate option identity")
                mapped[item["value"]] = item.get("probability")
            probabilities = mapped
        if not isinstance(probabilities, dict) or set(probabilities) != set(question["criteria"]):
            raise ValueError("Expected exact rubric option coverage")
        probabilities = {label: unit(value) for label, value in probabilities.items()}
        choice = answer.get("choice")
        if not isinstance(choice, str) or choice not in probabilities:
            raise ValueError("Unexpected selected option")
        confidence = unit(answer.get("confidence"))
        if not math.isclose(math.fsum(probabilities.values()), 1.0, abs_tol=1e-6, rel_tol=0):
            raise ValueError("Distribution is not normalized")
        if probabilities[choice] != max(probabilities.values()):
            raise ValueError("Selected option is not a maximum")
        normalized[axis] = {"type": "choice", "choice": choice,
                            "probabilities": probabilities, "confidence": confidence}
    return {"model": body["model"], "answers": normalized,
            "confidence_semantics": "native_provider_value_not_cross_provider_calibrated"}
