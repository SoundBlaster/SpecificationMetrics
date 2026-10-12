import ast
import copy
import json
from pathlib import Path
import unittest

from prepare_decision_reference import ROOT, build, declaration_range, fragment
from question_grouping import canonical, digest


RUN = ROOT / "runs/2026-10-12-expression-reference"


class ReferencePreparationTests(unittest.TestCase):
    def test_packet_and_mapping_are_bound_without_prior_semantic_labels(self):
        packet = json.loads((RUN / "reference-packet.json").read_text())
        mapping = json.loads((RUN / "source-mapping.json").read_text())
        self.assertEqual(mapping["packet_sha256"], digest(canonical(packet)))
        self.assertEqual(mapping["target_report_sha256"], digest((ROOT / "runs/2026-10-10-decision-targets/report.json").read_bytes()))
        self.assertEqual(mapping["selector_sha256"], digest(canonical(json.loads((RUN / "context-selectors.json").read_text()))))
        self.assertEqual(mapping["rubric_sha256"], digest(canonical(json.loads((RUN / "rubric.json").read_text()))))
        self.assertEqual(mapping["new_inference_requests"], 0)
        self.assertFalse(mapping["prior_labels_transferred"])
        self.assertEqual(mapping["reference_status"], "awaiting_independent_annotation")
        self.assertEqual(len(packet["cases"]), 8)
        for case, proof in zip(packet["cases"], mapping["cases"]):
            self.assertEqual(case["case_id"], proof["case_id"])
            self.assertEqual(case["state_sha256"], digest(canonical(case["state"])))
            self.assertEqual(case["state_sha256"], proof["state_sha256"])
            self.assertEqual(set(case), {"case_id", "state", "state_sha256"})
            self.assertEqual(set(case["state"]), {"architecture_profile", "target", "bounded_context"})
            self.assertLessEqual(len(canonical(case["state"])), 16 * 1024)
            self.assertFalse(case["state"]["bounded_context"]["truncated"])
            self.assertLessEqual(sum(len(f["code"].encode()) for f in proof["fragments"]), 8 * 1024)
            span = proof["expression_span"]
            self.assertTrue(any(f["start_byte"] <= span["start_byte"] < span["end_byte"] <= f["end_byte"] for f in proof["fragments"]))
            for f, p in zip(case["state"]["bounded_context"]["fragments"], proof["fragments"]):
                self.assertEqual(f["code"], p["code"])
                self.assertEqual(digest(p["code"].encode()), p["sha256"])
                self.assertEqual(len(p["code"].encode()), p["end_byte"] - p["start_byte"])
        for name, expected in mapping["implementation_digests"].items():
            self.assertEqual(digest((ROOT / name).read_bytes()), expected)

    def test_missing_or_duplicate_declarations_and_invalid_spans_fail(self):
        with self.assertRaises(ValueError):
            declaration_range(ast.parse("def x(): pass\ndef x(): pass"), "x")
        with self.assertRaises(ValueError):
            declaration_range(ast.parse("x=1"), "missing")
        with self.assertRaises(ValueError):
            fragment(b"x=1\n", 1, 2, "test")
        raw = "# привет\n@dataclass\nclass C:\n    x: str\n".encode()
        start, end = declaration_range(ast.parse(raw.decode()), "C")
        f = fragment(raw, start, end, "test")
        self.assertEqual(raw[f["start_byte"]:f["end_byte"]].decode(), f["code"])
        self.assertTrue(f["code"].startswith("@dataclass"))

    def test_changed_source_or_incomplete_selector_inventory_fails_closed(self):
        selectors = json.loads((RUN / "context-selectors.json").read_text())
        rubric = json.loads((RUN / "rubric.json").read_text())
        with self.assertRaisesRegex(ValueError, "Pinned source digest mismatch"):
            build(selectors, rubric, lambda *args: b"changed\n")
        broken = copy.deepcopy(selectors)
        broken["cases"].pop("sg-017")
        with self.assertRaises(ValueError):
            build(broken, rubric, lambda *args: self.fail("must fail before source read"))

    def test_proposals_are_not_reference_and_template_is_unlabelled(self):
        packet = json.loads((RUN / "reference-packet.json").read_text())
        template = json.loads((RUN / "annotation-template.json").read_text())
        proposals = json.loads((RUN / "annotation-proposals.json").read_text())
        self.assertEqual(template["packet_sha256"], digest(canonical(packet)))
        self.assertEqual(proposals["packet_sha256"], template["packet_sha256"])
        self.assertEqual(proposals["authority"], "context_author_non_blind_proposals_not_gold")
        self.assertEqual({a["case_id"] for a in template["annotations"]}, {c["case_id"] for c in packet["cases"]})
        states = {c["case_id"]: c["state_sha256"] for c in packet["cases"]}
        for annotation in template["annotations"]:
            self.assertEqual(annotation["state_sha256"], states[annotation["case_id"]])
            self.assertIsNone(annotation["opportunity"])
            self.assertIsNone(annotation["concern_kind"])
            self.assertEqual(annotation["status"], "pending")
        self.assertEqual({a["case_id"] for a in proposals["annotations"]}, set(states))
        for annotation in proposals["annotations"]:
            self.assertEqual(annotation["state_sha256"], states[annotation["case_id"]])
            self.assertEqual(annotation["status"], "proposed")

    def test_comparison_is_blocked_until_new_reference_and_native_luna_schema(self):
        packet = json.loads((RUN / "reference-packet.json").read_text())
        plan = json.loads((RUN / "comparison-plan.json").read_text())
        self.assertEqual(plan["packet_sha256"], digest(canonical(packet)))
        self.assertEqual(plan["status"], "prepared_not_executable")
        self.assertEqual(plan["reference_status"], "awaiting_independent_annotation")
        self.assertIsNone(plan["providers"][1]["endpoint"])
        self.assertIsNone(plan["providers"][1]["requested_model"])
        self.assertEqual(plan["planned_logical_requests"], len(packet["cases"]) * len(plan["providers"]) * plan["repeats"])
        self.assertEqual(plan["max_network_attempts"], plan["planned_logical_requests"] * plan["max_attempts_per_request"])
        self.assertEqual(plan["new_inference_requests"], 0)


if __name__ == "__main__":
    unittest.main()
