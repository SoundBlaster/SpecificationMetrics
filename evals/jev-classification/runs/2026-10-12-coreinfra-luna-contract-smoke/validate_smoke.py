"""Offline validation of this frozen mixed smoke; not a generic provider decoder."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).parent

def unit(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Expected finite unit probability")
    return value

def validate(response):
    if response.get("model") != "gpt-6-luna":
        raise ValueError("Unexpected returned model")
    answers = response["answers"]
    if not isinstance(answers, list) or len(answers) != 3:
        raise ValueError("Expected all three answers")
    by_name = {a["name"]: a for a in answers}
    if set(by_name) != {"blocked", "state", "severity"}:
        raise ValueError("Missing, duplicate or unexpected answer")
    pred = by_name["blocked"]
    if pred["type"] != "predicate":
        raise ValueError("Expected predicate")
    unit(pred["probability"])
    for name, kind, expected in [("state", "choice", ["blocked", "ready"]),
                                 ("severity", "score", [0, 1])]:
        answer = by_name[name]
        if answer["type"] != kind:
            raise ValueError("Unexpected answer type")
        unit(answer["confidence"])
        probs = answer["probabilities"]
        values = [p["value"] for p in probs]
        if len(probs) != 2 or any(type(v) is not type(e) for v, e in zip(values, expected)) or set(values) != set(expected):
            raise ValueError("Invalid option coverage")
        if not math.isclose(sum(unit(p["probability"]) for p in probs), 1.0, abs_tol=1e-6, rel_tol=0):
            raise ValueError("Distribution not normalized")
        if kind == "choice":
            if answer["choice"] not in expected:
                raise ValueError("Unexpected choice")
        else:
            labels = {0: "none", 1: "blocked"}
            if any(p.get("label") != labels[p["value"]] for p in probs):
                raise ValueError("Unexpected level label")
            score = unit(answer["score"])
            if not math.isclose(score, sum(p["value"] * p["probability"] for p in probs), abs_tol=1e-6, rel_tol=0):
                raise ValueError("Score differs from weighted level mean")
    return {"native_contract": "passed_for_frozen_mixed_smoke", "types": ["predicate", "choice", "score"],
            "semantic_status": "trivial_smoke_not_classifier_accuracy", "general_decoder": False}

if __name__ == "__main__":
    rows = (ROOT / "responses.jsonl").read_bytes()
    row = json.loads(rows)
    if row["http_status"] != 200 or row["status"] != "json_received":
        raise ValueError("Expected successful transport")
    result = validate(row["response"])
    result["responses_sha256"] = hashlib.sha256(rows).hexdigest()
    result["validator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["logical_requests"] = 1
    print(json.dumps(result, indent=2))
