import copy
import json
from pathlib import Path
import tempfile
import unittest

from decision_choice_contract import parse_response
from matched_expression_plan import REFERENCE, build, inspect_results, validate
from question_grouping import canonical, digest


QUESTIONS = json.loads((REFERENCE / "reference-packet.json").read_text())["questions"]


def fixture(provider):
    answers = {}
    for axis, q in QUESTIONS.items():
        labels = sorted(q["criteria"])
        probs = {label: float(i == 0) for i, label in enumerate(labels)}
        answers[axis] = {"type": "choice", "choice": labels[0], "probabilities": probs, "confidence": 0.8}
    if provider == "luna-decision-coreinfra":
        answers = [{**a, "name": axis, "probabilities": [{"value": k, "probability": v} for k, v in a["probabilities"].items()]}
                   for axis, a in answers.items()]
    return {"model": "gpt-6-luna" if isinstance(answers, list) else "jev-1.13.0", "answers": answers}


def parse(body, provider):
    return parse_response(json.dumps(body), provider=provider,
                          model="gpt-6-luna" if provider == "luna-decision-coreinfra" else "jev-1.13.0",
                          questions=QUESTIONS)


class NativeContracts(unittest.TestCase):
    def test_native_fixtures_decode_to_same_labels_and_distributions(self):
        jev = parse(fixture("jev-coreinfra"), "jev-coreinfra")
        luna = parse(fixture("luna-decision-coreinfra"), "luna-decision-coreinfra")
        self.assertEqual(jev["answers"], luna["answers"])

    def test_jev_malformed_responses_fail_closed(self):
        for mutation in ["model", "missing", "extra", "type", "choice", "coverage", "bool", "negative", "sum", "max", "confidence", "huge"]:
            with self.subTest(mutation=mutation):
                b = fixture("jev-coreinfra"); a = b["answers"]["opportunity"]
                if mutation == "model": b["model"] = "other"
                elif mutation == "missing": del b["answers"]["concern_kind"]
                elif mutation == "extra": b["answers"]["extra"] = copy.deepcopy(a)
                elif mutation == "type": a["type"] = "refusal"
                elif mutation == "choice": a["choice"] = "invented"
                elif mutation == "coverage": a["probabilities"].pop("needs_review")
                elif mutation == "bool": a["probabilities"]["eligible"] = True
                elif mutation == "negative": a["probabilities"]["eligible"] = -0.1
                elif mutation == "sum": a["probabilities"]["eligible"] = 0.5
                elif mutation == "max": a["choice"] = "excluded"
                elif mutation == "confidence": a["confidence"] = None
                else: a["confidence"] = 10 ** 400
                with self.assertRaises(ValueError): parse(b, "jev-coreinfra")

    def test_luna_duplicate_identities_and_invalid_options_are_rejected(self):
        for mutation in ["name", "option", "numeric_option", "missing", "wrong_type", "coverage", "probability"]:
            with self.subTest(mutation=mutation):
                b = fixture("luna-decision-coreinfra"); a = b["answers"][0]
                if mutation == "name": b["answers"][1]["name"] = a["name"]
                elif mutation == "option": a["probabilities"][1]["value"] = a["probabilities"][0]["value"]
                elif mutation == "numeric_option": a["probabilities"][0]["value"] = 0
                elif mutation == "missing": b["answers"].pop()
                elif mutation == "wrong_type": a["type"] = "predicate"
                elif mutation == "coverage": a["probabilities"].pop()
                else: a["probabilities"][0]["probability"] = "1.0"
                with self.assertRaises(ValueError): parse(b, "luna-decision-coreinfra")

    def test_nonfinite_and_duplicate_json_keys_rejected(self):
        for raw in ['{"model":"a","model":"b"}', '{"model":NaN}', '{"model":1e999}']:
            with self.assertRaises(ValueError):
                parse_response(raw, provider="jev-coreinfra", model="jev-1.13.0", questions=QUESTIONS)

    def test_probability_ties_are_valid_without_repair(self):
        b = fixture("jev-coreinfra"); a = b["answers"]["opportunity"]
        a["probabilities"] = {"eligible": 0.5, "excluded": 0.5, "needs_review": 0}
        self.assertEqual(parse(b, "jev-coreinfra")["answers"]["opportunity"]["choice"], "eligible")


class FrozenPlan(unittest.TestCase):
    def test_result_inspection_preserves_failures_missing_rows_and_stale_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); manifest = build()
            (run / "manifest.json").write_bytes(canonical(manifest))
            rows = []
            for i, request in enumerate(manifest["requests"][:3]):
                response = fixture(request["provider"])
                if i == 1: response["model"] = "wrong"
                rows.append({"request_id": request["request_id"], "wire_sha256": request["wire_sha256"],
                             "status": "http_error" if i == 2 else "json_received", "response": response})
            path = run / "responses.jsonl"
            path.write_bytes(b"\n".join(canonical(row) for row in rows))
            report = inspect_results(run)
            self.assertEqual((report["planned_requests"], report["received_rows"], report["native_valid"], report["native_invalid"]), (32, 3, 1, 1))
            self.assertEqual(len(report["missing_result_request_ids"]), 29)
            self.assertEqual(len(report["attempt_status_unknown_request_ids"]), 29)
            self.assertEqual(report["unattempted_request_ids"], [])
            self.assertEqual(report["rows"][2]["native_status"], "not_evaluated")
            self.assertIsNone(report["rows"][1]["prediction"])
            rows[0]["wire_sha256"] = "stale"
            path.write_bytes(b"\n".join(canonical(row) for row in rows))
            with self.assertRaises(ValueError): inspect_results(run)

    def test_interruption_after_post_does_not_become_unattempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); manifest = build(); manifest_raw = canonical(manifest)
            (run / "manifest.json").write_bytes(manifest_raw)
            (run / "responses.jsonl").write_bytes(b"")
            request = manifest["requests"][0]
            event = {"request_id": request["request_id"], "wire_sha256": request["wire_sha256"], "event": "attempt_started"}
            (run / "attempts.jsonl").write_bytes(canonical(event) + b"\n" + canonical({**event, "event": "post_may_start"}))
            report = inspect_results(run)
            self.assertEqual(report["attempted_without_result_request_ids"], [request["request_id"]])
            self.assertEqual(report["unattempted_request_ids"], [])
            self.assertEqual(len(report["attempt_status_unknown_request_ids"]), 31)
            receipt = {"manifest_sha256": digest(manifest_raw), "attempt_ledger_complete": False}
            (run / "receipt.json").write_bytes(canonical(receipt))
            self.assertEqual(inspect_results(run)["unattempted_request_ids"], [])
            receipt.update(attempt_ledger_complete=True, network_attempts=1, attempted_requests=1)
            (run / "receipt.json").write_bytes(canonical(receipt))
            report = inspect_results(run)
            self.assertEqual(len(report["unattempted_request_ids"]), 31)
            self.assertEqual(report["attempt_status_unknown_request_ids"], [])
            receipt["network_attempts"] = 2
            (run / "receipt.json").write_bytes(canonical(receipt))
            with self.assertRaises(ValueError): inspect_results(run)
            receipt["manifest_sha256"] = "stale"
            (run / "receipt.json").write_bytes(canonical(receipt))
            with self.assertRaises(ValueError): inspect_results(run)

    def test_same_state_and_rubric_both_providers_and_repeats(self):
        manifest = build(); requests = manifest["requests"]
        self.assertEqual(len(requests), 32)
        self.assertEqual(len({r["request_id"] for r in requests}), 32)
        for case in json.loads((REFERENCE / "reference-packet.json").read_text())["cases"]:
            rows = [r for r in requests if r["case_id"] == case["case_id"]]
            self.assertEqual(len(rows), 4)
            states = []
            for row in rows:
                body = json.loads(row["wire_json"])
                self.assertEqual(digest(row["wire_json"].encode()), row["wire_sha256"])
                state = body.get("state", body.get("input")); states.append(state)
                self.assertEqual(digest(state.encode()), case["state_sha256"])
                if row["provider"] == "jev-coreinfra":
                    self.assertEqual(body["questions"], QUESTIONS)
                    self.assertEqual(set(body), {"model", "state", "questions"})
                else:
                    reconstructed = {q["name"]: {"type": q["type"], "instructions": q["instructions"],
                                     "criteria": {c["value"]: c["description"] for c in q["choices"]}} for q in body["questions"]}
                    self.assertEqual(reconstructed, QUESTIONS)
                    self.assertEqual(set(body), {"model", "input", "questions"})
            self.assertEqual(len(set(states)), 1)
        for i in range(0, 32, 2):
            self.assertNotEqual(requests[i]["provider"], requests[i + 1]["provider"])
            self.assertEqual(requests[i]["case_id"], requests[i + 1]["case_id"])
            self.assertEqual(requests[i]["provider"], requests[i + 17 if i < 16 else i - 15]["provider"])

    def test_validation_is_offline_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); m = build(); path = run / "manifest.json"
            path.write_bytes(canonical(m)); result = validate(run)
            self.assertFalse(result["inference"])
            self.assertEqual(result["max_network_attempts"], 96)
            self.assertFalse((run / "attempts.jsonl").exists())
            for field in ["wire_json", "wire_sha256", "provider", "state_sha256"]:
                broken = copy.deepcopy(m); broken["requests"][0][field] = "tampered"
                path.write_bytes(canonical(broken))
                with self.assertRaises(ValueError): validate(run)
            for field in ["analysis_producer_digests", "reference_sha256", "max_network_attempts"]:
                broken = copy.deepcopy(m); broken[field] = None
                path.write_bytes(canonical(broken))
                with self.assertRaises(ValueError): validate(run)


if __name__ == "__main__":
    unittest.main()
