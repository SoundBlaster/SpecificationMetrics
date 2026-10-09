import unittest
import json
import shutil
import tempfile
from pathlib import Path
from score_rustjev import index_rows, score


class ScoreTests(unittest.TestCase):
    def row(self, label="eligible", decision="Accepted(\"eligible\")"):
        return {"candidate_id": "x", "axis": "opportunity", "accepted_label": label, "decision": decision}

    def test_recorded_report_reproduces_offline(self):
        run = Path(__file__).parent / "runs/2026-10-08-rustjev-coreinfra"
        self.assertEqual(score(run), json.loads((run / "summary.json").read_text()))

    def test_partial_run_compares_only_scored_historical_axes(self):
        source = Path(__file__).parent / "runs/2026-10-08-rustjev-coreinfra"
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            for name in ["manifest.json", "requests.json", "responses.jsonl", "receipt.json"]:
                shutil.copyfile(source / name, run / name)
            rows = [json.loads(line) for line in (run / "responses.jsonl").read_text().splitlines()]
            historical = json.loads((source.parent / "2026-10-05-intent-profile-ablation/run-1/run.json").read_text())
            previous = next(r["response"]["output"][rows[0]["axis"]]["choice"] for r in historical["rows"]
                            if r["candidate_id"] == rows[0]["candidate_id"] and r["repeat"] == 0
                            and r["arm"] == "code_plus_architecture_profile")
            rows[0].update(accepted_label=previous, decision="Accepted(" + json.dumps(previous) + ")")
            receipt = json.loads((run / "receipt.json").read_text())
            for selected in [[], [dict(rows[0], accepted_label=None, decision="Failed(TimedOut)")], [rows[0]]]:
                (run / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in selected))
                receipt.update(saved_responses=len(selected), completed=False)
                (run / "receipt.json").write_text(json.dumps(receipt))
                report = score(run)
                self.assertEqual(report["historical_label_changes"], [])
                for axis in ["opportunity", "concern_kind"]:
                    self.assertEqual(report["summaries"][axis]["agreement_denominator"], 8)
            # An actual scored disagreement still counts, even if the other axis is missing.
            different = "excluded" if previous != "excluded" else "eligible"
            changed = dict(rows[0], accepted_label=different, decision="Accepted(" + json.dumps(different) + ")")
            (run / "responses.jsonl").write_text(json.dumps(changed) + "\n")
            self.assertEqual(len(score(run)["historical_label_changes"]), 1)

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
