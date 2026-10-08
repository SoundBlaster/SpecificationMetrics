import unittest
import json
from pathlib import Path
from score_rustjev import index_rows, score


class ScoreTests(unittest.TestCase):
    def row(self, label="eligible", decision="Accepted(\"eligible\")"):
        return {"candidate_id": "x", "axis": "opportunity", "accepted_label": label, "decision": decision}

    def test_recorded_report_reproduces_offline(self):
        run = Path(__file__).parent / "runs/2026-10-08-rustjev-coreinfra"
        self.assertEqual(score(run), json.loads((run / "summary.json").read_text()))

    def test_failed_results_do_not_become_semantic_abstentions(self):
        rows = index_rows([self.row(None, "Failed(TimedOut)")], {("x", "opportunity")})
        self.assertIsNone(rows[("x", "opportunity")]["accepted_label"])
        rows = index_rows([self.row("needs_review", "Accepted(\"needs_review\")")], {("x", "opportunity")})
        self.assertEqual(rows[("x", "opportunity")]["accepted_label"], "needs_review")

    def test_duplicate_unplanned_and_inconsistent_receipts_are_rejected(self):
        planned = {("x", "opportunity")}
        for rows, plan in [([self.row(), self.row()], planned), ([self.row()], set()),
                           ([self.row("eligible", "Failed(TimedOut)")], planned),
                           ([self.row(None)], planned), ([self.row("unexpected")], planned)]:
            with self.assertRaises(ValueError):
                index_rows(rows, plan)


if __name__ == "__main__":
    unittest.main()
