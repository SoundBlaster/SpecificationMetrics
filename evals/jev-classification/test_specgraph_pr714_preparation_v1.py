import copy
import importlib.metadata
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import prepare_specgraph_pr714_v1 as prep


class PreparationTests(unittest.TestCase):
    def test_frozen_four_tasks_verify_without_source_checkout_or_credentials(self):
        with patch.dict("os.environ", {}, clear=True), patch("socket.socket.connect", side_effect=AssertionError("offline")):
            self.assertEqual(prep.verify()["hosted_requests"], 0)
        plan = prep.load(prep.RUN / "plan.json")
        self.assertEqual(len(plan["cases"]), 4)
        self.assertFalse(plan["authorization"]["inference_authorized"])
        self.assertFalse(plan["automatic_fact_acceptance"])
        self.assertEqual(plan["metric_effect"], "none")

    def test_exact_spans_rubric_and_contexts_remain_bound_without_author_labels(self):
        prior = prep.load(prep.RUBRIC)
        inputs = prep.load(prep.RUN / "source-inputs.json")

        def no_labels(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & {"answers", "labels", "gold", "expected_labels"})
                for child in value.values():
                    no_labels(child)
            elif isinstance(value, list):
                for child in value:
                    no_labels(child)

        for case, symbol, start, end in prep.CASES:
            packet = prep.load(prep.RUN / f"{case}.packet.json")
            self.assertEqual(packet["task"]["questions"], prior["task"]["questions"])
            self.assertEqual(packet["semantic_instructions"], prior["semantic_instructions"])
            self.assertEqual(packet["task"]["state"]["target"]["source"], inputs["fragments"][case])
            self.assertEqual(prep.load(prep.RUN / f"{case}.context.json"), prep.context_for(packet))
            self.assertLessEqual((prep.RUN / f"{case}.packet.json").stat().st_size, 65536)
            parent = inputs["fragments"][symbol.split("/")[0]]
            lines = parent["code"].splitlines(keepends=True)
            self.assertEqual("".join(lines[start-parent["start_line"]:end-parent["start_line"]+1]),
                             inputs["fragments"][case]["code"])
            no_labels(packet)
            self.assertEqual(prep.context_for(packet)["assessment"]["status"], "not_run")

    def test_rebound_packet_is_rejected_after_receipt_hash_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            shutil.copytree(prep.RUN, bundle)
            path = bundle / "D01.packet.json"
            packet = prep.load(path)
            packet["task"]["state"]["target"]["source"]["code"] += "# altered\n"
            path.write_text(prep.encoded(packet) + "\n")
            receipt = prep.load(bundle / "preparation-receipt.json")
            receipt["files_sha256"][path.name] = prep.sha(path.read_bytes())
            (bundle / "preparation-receipt.json").write_text(prep.encoded(receipt) + "\n")
            with self.assertRaisesRegex(ValueError, "prepared artifact differs"):
                prep.verify(bundle)

    def test_source_and_authority_mutation_cannot_be_hidden_by_rebinding(self):
        for filename in ("source-inputs.json", "plan.json", "D02.context.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as td:
                bundle = Path(td) / "bundle"
                shutil.copytree(prep.RUN, bundle)
                path = bundle / filename
                value = prep.load(path)
                value["inference_authorized"] = True
                path.write_text(prep.encoded(value) + "\n")
                with self.assertRaises(ValueError):
                    prep.verify(bundle)

    def test_freeze_refuses_existing_preparation(self):
        with self.assertRaisesRegex(ValueError, "refuse to overwrite"):
            prep.freeze()


class BridgePreparationTests(unittest.TestCase):
    """Adapter compatibility only; all labels below are synthetic test inputs."""

    @classmethod
    def setUpClass(cls):
        version = importlib.metadata.version("mellea-jev-adapter")
        if tuple(int(v) for v in version.split(".")[:2]) < (0, 9):
            raise unittest.SkipTest("current SDK bridge is exercised in evaluation-sdk-current")

    def test_all_new_packets_bind_and_follow_existing_synthetic_routes(self):
        from categorical_review_bridge_v1 import bind, categorical_plan
        from mellea_jev import CategoricalResult
        from semantic_review_routing_v1.context import RoutingContext
        from structured_semantic_review_v1.preparation import request_sha256

        for case, *_ in prep.CASES:
            packet = prep.load(prep.RUN / f"{case}.packet.json")
            for provider, model in (("jev-coreinfra", "jev-1.13.0"),
                                    ("luna-responses-coreinfra", "gpt-6-luna")):
                with self.subTest(case=case, provider=provider), patch.dict("os.environ", {}, clear=True), patch(
                        "socket.socket.connect", side_effect=AssertionError("offline")):
                    context = RoutingContext.model_validate_json(prep.encoded(prep.context_for(packet, provider, model)))
                    bound = bind(context, state_json=prep.encoded(packet["task"]["state"]),
                                 questions_json=prep.encoded(packet["task"]["questions"]))
                    self.assertEqual(dict(bound.sdk_task().questions).keys(), packet["task"]["questions"].keys())
                    for role, support, route in (("policy", "supported", "retain_proposal"),
                                                  ("mechanics", "supported", "retain_proposal"),
                                                  ("unknown", "insufficient", "ordinary_review")):
                        result = CategoricalResult(answers=dict(concern_kind=role, evidence_confidence=support,
                            ownership="unknown", tool_responsibility="unknown"),
                            requested_model=model, returned_model=model)
                        plan = categorical_plan(bound, result, response_sha256=prep.sha(b"synthetic-test-only"))
                        self.assertEqual(plan.report()["original_route"]["route"], route)
                        self.assertFalse(plan.report()["automatic_fact_acceptance"])
                        if route == "ordinary_review":
                            request = plan.review_request()
                            review_input = json.loads(request["input"])
                            self.assertNotIn("labels", review_input)
                            self.assertNotIn("original_assessment", review_input)
                            historical = prep.load(prep.ROOT / "runs/2026-10-18-structured-luna-review-live-v1/manifest.json")
                            self.assertNotEqual(request_sha256(plan.review), historical["request_sha256"])
                            self.assertEqual(plan.inspect_review()["review_status"], "not_run")
                        else:
                            self.assertIsNone(plan.review_request())
                    incomplete = categorical_plan(bound, None, response_sha256=None, status="not_run")
                    self.assertEqual(incomplete.report()["original_route"]["route"], "stop_incomplete")
                    self.assertIsNone(incomplete.review_request())

    def test_stale_state_and_mixed_decision_binding_are_rejected(self):
        from categorical_review_bridge_v1 import bind
        from semantic_review_routing_v1.context import RoutingContext

        packet = prep.load(prep.RUN / "D01.packet.json")
        # Use the real serialization boundary: strict Pydantic Python mode
        # rejects JSON arrays for tuple fields; JSON mode accepts that wire form.
        context = RoutingContext.model_validate_json((prep.RUN / "D01.context.json").read_text())
        state = prep.encoded(packet["task"]["state"])
        questions = prep.encoded(packet["task"]["questions"])
        with self.assertRaisesRegex(ValueError, "state digest differs"):
            bind(context, state_json=state + " ", questions_json=questions)
        changed = copy.deepcopy(prep.context_for(packet))
        changed["expected"]["decision_id"] = "another-decision"
        with self.assertRaisesRegex(ValueError, "source identity differs"):
            bind(RoutingContext.model_validate_json(prep.encoded(changed)), state_json=state, questions_json=questions)


if __name__ == "__main__":
    unittest.main()
