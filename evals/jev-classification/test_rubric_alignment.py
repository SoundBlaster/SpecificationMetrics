import json
import shutil
import tempfile
import unittest
from pathlib import Path
from rubric_alignment import load
from score_rubric_alignment import score
from question_grouping import canonical, digest

RUN = Path(__file__).parent / "runs/2026-10-10-rubric-alignment"


class AlignmentTests(unittest.TestCase):
    def test_frozen_plan_has_matched_reference_and_context(self):
        manifest,plan=load(RUN)
        self.assertEqual(len(plan),32)
        self.assertEqual(manifest["repeats"],2)

    def test_changed_context_or_duplicate_request_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder)
            for name in ["manifest.json","plan.json","rubric.json","reference-packet.json","reference-mapping.json"]:
                shutil.copyfile(RUN/name,run/name)
            original=json.loads((run/"plan.json").read_text())
            for mode in ["context","duplicate"]:
                plan=json.loads(json.dumps(original))
                if mode=="context":
                    body=json.loads(plan[0]["wire_json"])
                    body["state"]["extra"]="Unplanned context"
                    raw=canonical(body)
                    plan[0].update(wire_json=raw.decode(),wire_sha256=digest(raw))
                else:
                    plan[1]=plan[0]
                (run/"plan.json").write_text(json.dumps(plan))
                with self.assertRaises(ValueError):load(run)
            (run/"plan.json").write_text(json.dumps(original))
            packet=json.loads((run/"reference-packet.json").read_text())
            packet["questions"]["opportunity"]["instructions"]="A different reference task"
            (run/"reference-packet.json").write_text(json.dumps(packet))
            with self.assertRaises(ValueError):load(run)

    def test_recorded_report_reproduces_without_inference(self):
        report=score(RUN)
        self.assertEqual(report,json.loads((RUN/"summary.json").read_text()))
        self.assertTrue(report["completed"])
        self.assertFalse(report["alignment_hypothesis_supported"])
        for repeat in ["1","2"]:
            self.assertEqual(report["summaries"][repeat]["baseline"]["opportunity"]["agreement_count"],4)
            self.assertEqual(report["summaries"][repeat]["aligned"]["opportunity"]["agreement_count"],5)
            self.assertEqual(set(report["controls"][repeat]["aligned"]["owned_false_positive_ids"]),{"sg-018","sg-020"})

    def test_false_completion_and_wrong_wire_receipts_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder)
            for name in ["manifest.json","plan.json","rubric.json","reference-packet.json","reference-mapping.json","annotations.json","responses.jsonl","receipt.json"]:
                shutil.copyfile(RUN/name,run/name)
            rows=[json.loads(s) for s in (run/"responses.jsonl").read_text().splitlines()]
            original=json.loads(json.dumps(rows))
            rows[0]["wire_sha256"]="wrong"
            (run/"responses.jsonl").write_text("\n".join(json.dumps(r) for r in rows)+"\n")
            with self.assertRaises(ValueError):score(run)
            (run/"responses.jsonl").write_text(json.dumps(original[0])+"\n")
            receipt=json.loads((run/"receipt.json").read_text())
            receipt["attempted_requests"]=1
            (run/"receipt.json").write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):score(run)
            receipt.update(completed=False,stop_reason="test interruption")
            (run/"receipt.json").write_text(json.dumps(receipt))
            report=score(run)
            self.assertIsNone(report["alignment_hypothesis_supported"])
            for repeat in ["1","2"]:
                for arm in ["baseline","aligned"]:
                    self.assertEqual(report["summaries"][repeat][arm]["opportunity"]["agreement_denominator"],8)
            self.assertEqual(report["summaries"]["2"]["aligned"]["opportunity"]["not_run_cases"],8)


if __name__ == "__main__":unittest.main()
