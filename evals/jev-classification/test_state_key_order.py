import copy
import json
import unittest
import shutil
import tempfile
from pathlib import Path
from state_key_order import load, validate
from question_grouping import digest
from score_state_key_order import score

RUN = Path(__file__).parent / "runs/2026-10-09-state-key-order"


class KeyOrderTests(unittest.TestCase):
    def test_exact_wire_and_semantic_invariants(self):
        _, plan = load(RUN)
        validate(plan)
        broken = copy.deepcopy(plan)
        body = json.loads(broken[0]["wire_json"])
        body["state"]["extra"] = "semantic change"
        wire = json.dumps(body,ensure_ascii=False,separators=(",", ":"))
        broken[0].update(wire_json=wire, wire_sha256=digest(wire.encode()))
        with self.assertRaises(ValueError):
            validate(broken)

    def test_unintended_reserialization_or_duplicates_are_rejected(self):
        _, plan = load(RUN)
        for modify in [lambda p: p.pop(), lambda p: p.__setitem__(1,p[0])]:
            broken = copy.deepcopy(plan);modify(broken)
            with self.assertRaises(ValueError):
                validate(broken)
        broken = copy.deepcopy(plan)
        broken[0]["wire_json"] += " "
        with self.assertRaises(ValueError):
            validate(broken)

    def test_recorded_report_reproduces_offline(self):
        report = score(RUN)
        self.assertEqual(report, json.loads((RUN / "summary.json").read_text()))
        self.assertFalse(report["label_invariance"])
        self.assertEqual(report["paired"]["opportunity"]["changed_labels"], ["sg-018"])
        self.assertEqual(report["summaries"]["insertion"]["opportunity"]["agreement_count"], 3)
        self.assertEqual(report["summaries"]["canonical"]["opportunity"]["agreement_count"], 4)

    def test_receipt_binding_and_partial_denominators(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            for name in ["manifest.json", "plan.json", "responses.jsonl", "receipt.json"]:
                shutil.copyfile(RUN / name, run / name)
            original = (run / "responses.jsonl").read_text().splitlines()
            rows = [json.loads(line) for line in original]
            receipt = json.loads((run / "receipt.json").read_text())
            for mutation in [lambda r: r.reverse(), lambda r: r[0].update(wire_sha256="wrong")]:
                broken = copy.deepcopy(rows)
                mutation(broken)
                (run / "responses.jsonl").write_text("\n".join(json.dumps(r) for r in broken) + "\n")
                with self.assertRaises(ValueError):
                    score(run)
            (run / "responses.jsonl").write_text(original[0] + "\n")
            receipt["attempted_requests"] = 1
            (run / "receipt.json").write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                score(run)  # A truncated run cannot claim completion.
            receipt.update(completed=False, stop_reason="test interruption")
            (run / "receipt.json").write_text(json.dumps(receipt))
            report = score(run)
            self.assertIsNone(report["label_invariance"])
            for arm in ["insertion", "canonical"]:
                self.assertEqual(report["summaries"][arm]["opportunity"]["agreement_denominator"], 8)
            self.assertEqual(report["summaries"]["canonical"]["opportunity"]["not_run_cases"], 8)
            failed = rows[0]
            failed.update(response=None, error="HTTP 503")
            (run / "responses.jsonl").write_text(json.dumps(failed) + "\n")
            self.assertEqual(score(run)["summaries"]["insertion"]["opportunity"]["unscored_cases"], 8)
            # Legacy senders could retain otherwise valid answers before usage accounting failed.
            for usage in [["invalid"], "tokens", {"input_tokens": "invalid"}]:
                failed.update(response=dict(rows[0]["response"] or json.loads(original[0])["response"], usage=usage), error="AttributeError")
                (run / "responses.jsonl").write_text(json.dumps(failed) + "\n")
                report = score(run)
                self.assertEqual(report["summaries"]["insertion"]["opportunity"]["unscored_cases"], 8)
                self.assertEqual(report["usage"]["insertion"], {"input_tokens": 0, "output_tokens": 0})
                self.assertEqual(report["paired"]["opportunity"]["paired_scored_cases"], 0)


if __name__ == "__main__":
    unittest.main()
