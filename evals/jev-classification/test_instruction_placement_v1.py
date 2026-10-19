from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import instruction_placement_v1 as study
from coreinfra_transport import post
from test_coreinfra_transport import FakeConnection


def synthetic_sender(endpoint, wire, key, *, live, policy, emit):
    payload = study.prior.decode(wire)
    messages = payload["input"]
    state = study.prior.decode(messages[1]["content"])["state"]
    answers = dict(concern_kind="policy", evidence_confidence="supported",
                   ownership="unknown", tool_responsibility="unknown")
    if state["target"]["source"]["symbol"] == "WORKSPACE_ALLOCATION_SPEC" and messages[0]["role"] == "developer":
        answers["ownership"] = "existing_specification"
    body = study.prior.encoded(dict(status="completed", model=study.prior.MODEL,
        output=[dict(type="message", role="assistant", status="completed", content=[dict(
            type="output_text", text=study.prior.encoded(dict(answers=answers)))])])).encode()
    return post(endpoint, wire, key, live=live, policy=policy, emit=emit,
                connection_factory=lambda _: FakeConnection(body=body), sleep=lambda _: None)


class FinalPlacementTests(unittest.TestCase):
    def test_exactly_one_role_changes_and_stop_rule_is_frozen(self):
        manifest = study.expected()
        self.assertEqual((len(manifest["requests"]), manifest["max_network_attempts"], manifest["new_sol_calls"]), (12, 36, 0))
        for case in study.prior.CASES:
            for repeat in (1, 2):
                pair = {r["arm"]: study.prior.decode(r["wire_json"]) for r in manifest["requests"]
                        if r["case_id"] == case and r["repeat"] == repeat}
                high, low = pair["developer_rules"], pair["user_rules"]
                self.assertEqual(high["input"][0]["role"], "developer")
                self.assertEqual(low["input"][0]["role"], "user")
                low["input"][0]["role"] = "developer"
                self.assertEqual(high, low)
                self.assertEqual(study.prior.decode(high["input"][1]["content"]), {"state": manifest["tasks"][case]["state"]})
        self.assertIn("no further research", manifest["stopping_rule"])

    def test_offline_preparation_and_rebound_effort_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "run"
            study.freeze(run)
            self.assertFalse(study.execute(run, sender=lambda *a, **kw: self.fail("live call"))["inference"])
            path = run / "manifest.json"
            manifest = study.prior.decode(path.read_bytes())
            manifest["requests"][0]["wire_json"] = manifest["requests"][0]["wire_json"].replace('"medium"', '"high"')
            path.write_text(study.prior.encoded(manifest))
            receipt_path = run / "preparation-receipt.json"
            receipt = study.prior.decode(receipt_path.read_bytes())
            receipt["manifest_sha256"] = study.prior.sha(path.read_bytes())
            receipt_path.write_text(study.prior.encoded(receipt))
            with self.assertRaisesRegex(ValueError, "placement preparation changed"):
                study.verify(run)

    def test_synthetic_priority_effect_capture_and_no_repeat(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "run"
            study.freeze(run)
            with patch.dict("os.environ", COREINFRA_API_KEY="offline-test-not-a-secret"):
                receipt = study.execute(run, live=True, sender=synthetic_sender)
                with self.assertRaisesRegex(ValueError, "Refusing to repeat"):
                    study.execute(run, live=True, sender=synthetic_sender)
            self.assertEqual(receipt["network_attempts"], 12)
            result = study.analyze(run)
            self.assertTrue(result["narrow_priority_prediction_supported"])
            self.assertEqual(result["research_status"], "closed_per_user_request")
            self.assertFalse(result["further_inference_authorized"])
            self.assertIsNone(result["semantic_accuracy"])
            path = run / "responses.jsonl"
            path.write_text(path.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "capture binding"):
                study.analyze(run)

    def test_final_recorded_result_replays_without_network(self):
        if not (study.RUN / "comparison.json").exists():
            self.skipTest("final live check not captured yet")
        self.assertEqual(study.analyze(study.RUN), study.prior.decode((study.RUN / "comparison.json").read_bytes()))


if __name__ == "__main__":
    unittest.main()
