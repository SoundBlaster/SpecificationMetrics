from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import codex_envelope_ablation_v1 as study
from coreinfra_transport import post
from test_coreinfra_transport import FakeConnection


def synthetic_sender(endpoint, wire, key, *, live, policy, emit):
    """Deliberately synthetic treatment effect, never provider evidence."""
    payload = study.decode(wire)
    state = study.decode(payload["input"])["state"]
    is_spec = state["target"]["source"]["symbol"] == "WORKSPACE_ALLOCATION_SPEC"
    answers = dict(concern_kind="policy", evidence_confidence="supported",
                   ownership="unknown", tool_responsibility="unknown")
    if is_spec and not payload["instructions"].startswith((study.FIXTURE / "instructions.md").read_text()):
        answers["ownership"] = "existing_specification"
    body = study.encoded(dict(status="completed", model=study.MODEL,
        output=[dict(type="message", role="assistant", status="completed",
            content=[dict(type="output_text", text=study.encoded(dict(answers=answers)))])])).encode()
    return post(endpoint, wire, key, live=live, policy=policy, emit=emit,
                connection_factory=lambda _: FakeConnection(body=body), sleep=lambda _: None)


class EnvelopeAblationTests(unittest.TestCase):
    def test_only_treatment_differs_and_order_is_balanced(self):
        with patch.dict("os.environ", {}, clear=True):
            manifest = study.expected()
        self.assertEqual((manifest["planned_requests"], manifest["max_network_attempts"], manifest["new_sol_calls"]), (12, 36, 0))
        template = (study.FIXTURE / "instructions.md").read_text()
        for case in study.CASES:
            rows = [r for r in manifest["requests"] if r["case_id"] == case]
            self.assertEqual([r["arm"] for r in rows[:2]], list(reversed([r["arm"] for r in rows[2:]])))
            minimal = study.decode(next(r for r in rows if r["arm"] == "minimal")["wire_json"])
            treated = study.decode(next(r for r in rows if r["arm"] == "codex_default")["wire_json"])
            self.assertEqual(treated.pop("instructions"), template + "\n\n" + minimal.pop("instructions"))
            self.assertEqual(treated, minimal)
            self.assertEqual(treated["reasoning"], {"effort": "medium"})
            self.assertFalse(treated["store"])
            self.assertNotIn("previous_response_id", treated)

    def test_no_live_side_effect_and_rebound_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "run"
            study.freeze(run)
            self.assertFalse(study.execute(run, sender=lambda *a, **kw: self.fail("network"))["inference"])
            manifest = study.decode((run / "manifest.json").read_bytes())
            manifest["requests"][0]["wire_json"] = manifest["requests"][0]["wire_json"].replace('"medium"', '"high"')
            (run / "manifest.json").write_text(study.encoded(manifest))
            receipt = study.decode((run / "preparation-receipt.json").read_bytes())
            receipt["manifest_sha256"] = study.sha((run / "manifest.json").read_bytes())
            (run / "preparation-receipt.json").write_text(study.encoded(receipt))
            with self.assertRaisesRegex(ValueError, "frozen experiment differs"):
                study.verify(run)

    def test_synthetic_effect_replays_and_captured_answer_tampering_fails(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "run"
            study.freeze(run)
            with patch.dict("os.environ", COREINFRA_API_KEY="synthetic-not-a-secret"):
                receipt = study.execute(run, live=True, sender=synthetic_sender)
                with self.assertRaisesRegex(ValueError, "Refusing to repeat"):
                    study.execute(run, live=True, sender=synthetic_sender)
            self.assertTrue(receipt["completed"])
            self.assertEqual(receipt["network_attempts"], 12)
            result = study.analyze(run)
            self.assertTrue(result["narrow_hypothesis_supported"])
            self.assertFalse(result["automatic_fact_acceptance"])
            self.assertIsNone(result["semantic_accuracy"])
            path = run / "responses.jsonl"
            rows = [study.decode(line) for line in path.read_bytes().splitlines()]
            rows[0]["response"]["model"] = "another-model"
            path.write_text("".join(study.encoded(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "capture receipt binding"):
                study.analyze(run)

    def test_refusal_and_wrong_model_are_failures_not_unknown(self):
        task = study.expected()["tasks"]["R01"]
        for body in [dict(status="incomplete", model=study.MODEL, output=[]),
                     dict(status="completed", model=study.MODEL, output=[dict(type="message", role="assistant",
                         status="completed", content=[dict(type="refusal", refusal="synthetic")])])]:
            with self.assertRaises(Exception):
                study.sdk_exchange(task, body)
        response = dict(status="completed", model="wrong", output=[dict(type="message", role="assistant",
            status="completed", content=[dict(type="output_text", text=study.encoded(dict(answers={
                name: "insufficient" if name == "evidence_confidence" else "unknown" for name in task["questions"]})))])])
        with self.assertRaisesRegex(ValueError, "response model differs"):
            study.sdk_exchange(task, response)

    def test_recorded_comparison_replays_when_present(self):
        if not (study.RUN / "comparison.json").exists():
            self.skipTest("live observation is not captured")
        self.assertEqual(study.analyze(study.RUN), study.decode((study.RUN / "comparison.json").read_bytes()))


if __name__ == "__main__":
    unittest.main()
