import json
from pathlib import Path
import unittest

from decision_target_alignment import anchor_position

ROOT = Path(__file__).parent


class TargetAlignmentTests(unittest.TestCase):
    def test_anchors_use_byte_columns_and_reject_ambiguous_needles(self):
        site = {"start_line": 7, "code": "имя = value\n    if ready:\n        pass\n"}
        self.assertEqual(anchor_position(site, "value"), (7, 10))
        self.assertEqual(anchor_position(site, "if ready"), (8, 5))
        for needle in ["missing", " "]:
            with self.assertRaises(ValueError):
                anchor_position(site, needle)

    def test_frozen_targets_are_source_bound_without_old_semantic_labels(self):
        run = ROOT/"runs/2026-10-10-decision-targets"
        report = json.loads((run/"report.json").read_text())
        selectors = json.loads((run/"selectors.json").read_text())
        corpus = {c["description"]: c["metadata"]["source"]["site"] for c in json.loads((ROOT/"corpus/cases.json").read_text())}
        self.assertEqual(report["new_inference_requests"], 0)
        self.assertEqual(report["planned_cases"], len(selectors["cases"]))
        self.assertEqual(report["extracted_targets"], report["planned_cases"])
        self.assertEqual([c["selector"] for c in report["cases"]], selectors["cases"])
        self.assertEqual(len({c["target"]["target_id"] for c in report["cases"]}), len(report["cases"]))
        for case in report["cases"]:
            site = corpus[case["source_candidate_id"]]
            self.assertEqual(case["source"], {k: site[k] for k in case["source"]})
            self.assertFalse(case["prior_labels_transferred"])
            self.assertEqual(case["reference_status"], "requires_new_annotation")
            target = case["target"]
            self.assertEqual(target["ownership_status"], "unknown")
            self.assertEqual(target["metric_effect"], "none")
            self.assertFalse(target["expression"]["truncated"])
            span = target["expression"]["span"]
            lines = site["code"].encode().splitlines(keepends=True)
            a, b = span["start_line"] - site["start_line"], span["end_line"] - site["start_line"]
            self.assertGreaterEqual(a, 0)
            self.assertLess(b, len(lines))
            if a == b:
                selected = lines[a][span["start_column"]-1:span["end_column"]-1]
            else:
                selected = lines[a][span["start_column"]-1:] + b"".join(lines[a+1:b]) + lines[b][:span["end_column"]-1]
            self.assertEqual(selected.decode(), target["expression"]["code"])
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse({"reference", "predictions", "opportunity", "concern_kind"} & set(value))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(report)


if __name__ == "__main__":
    unittest.main()
