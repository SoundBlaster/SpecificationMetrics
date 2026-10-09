import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from score_repeat_controls import compare, score

RUN = Path(__file__).parent / "runs/2026-10-09-repeat-controls"


class RepeatTests(unittest.TestCase):
    def test_recorded_summary_reproduces_offline(self):
        report = score(RUN)
        self.assertEqual(report, json.loads((RUN / "summary.json").read_text()))
        self.assertTrue(report["completed"])
        self.assertEqual(report["attempted_requests"],32)
        for kind in report["comparisons"].values():
            for axis in kind.values():
                self.assertEqual(axis["scored_comparisons"],16)
                self.assertEqual(axis["label_changes"],0)
        self.assertGreater(report["comparisons"]["same_byte"]["opportunity"]["max_probability_delta"],0)

    def test_labels_and_numeric_stability_are_distinct(self):
        answer = {"choice":"eligible","probabilities":{"eligible":0.8,"excluded":0.2},"confidence":0.6}
        other = copy.deepcopy(answer)
        other.update(probabilities={"eligible":0.7,"excluded":0.3},confidence=0.5)
        difference = compare(answer,other)
        self.assertFalse(difference["label_changed"])
        self.assertAlmostEqual(difference["max_probability_delta"],0.1)
        other.update(choice="excluded")
        self.assertTrue(compare(answer,other)["label_changed"])

    def test_unattempted_round_and_manifest_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / "study"
            shutil.copytree(RUN,run)
            (run / "round-2/responses.jsonl").unlink()
            (run / "round-2/receipt.json").unlink()
            report = score(run)
            self.assertFalse(report["completed"])
            self.assertEqual(report["attempted_requests"],16)
            self.assertEqual(report["comparisons"]["same_byte"]["opportunity"]["scored_comparisons"],0)
            self.assertEqual(report["comparisons"]["same_byte"]["opportunity"]["planned_comparisons"],16)
            p=run / "round-1/manifest.json"
            p.write_text(p.read_text()+" ")
            with self.assertRaises(ValueError):
                score(run)


if __name__ == "__main__":
    unittest.main()
