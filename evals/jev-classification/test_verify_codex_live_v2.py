import json
from pathlib import Path
import shutil
import tempfile
import unittest

import verify_codex_live_v1 as v1
import verify_codex_live_v2 as v2
from verify_codex_one_packet_v1 import load, sha


class LiveReplayV2Tests(unittest.TestCase):
    def test_frozen_capture_passes_both_consumers(self):
        self.assertEqual(v1.verify()["matching_axes"], 3)
        self.assertEqual(v2.verify()["matching_axes"], 3)

    def mutated_capture(self, label, check):
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "capture"
            shutil.copytree(v1.BUNDLE, bundle)
            answer = load(bundle / "answer.json")
            answer["answers"]["concern_kind"] = label
            (bundle / "answer.json").write_text(json.dumps(answer))
            report = load(bundle / "report.json")
            report["answers"] = answer["answers"]
            (bundle / "report.json").write_text(json.dumps(report))
            events = [json.loads(row) for row in (bundle / "events.jsonl").read_text().splitlines()]
            events[2]["item"]["text"] = json.dumps(answer)
            (bundle / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
            comparison = load(bundle / "comparison.json")
            axis = next(row for row in comparison["axes"] if row["axis"] == "concern_kind")
            axis.update(codex_label=label, agrees_with_sol=label == axis["sol_label"])
            (bundle / "comparison.json").write_text(json.dumps(comparison))
            receipt = load(bundle / "receipt.json")
            receipt["files_sha256"] = {name: sha(bundle / name) for name in receipt["files_sha256"]}
            (bundle / "receipt.json").write_text(json.dumps(receipt))
            # Demonstrate the actual v1 blind spot with coherently rebound data.
            self.assertEqual(v1.verify(bundle)["matching_axes"], 3)
            with self.assertRaisesRegex(ValueError, check):
                v2.verify(bundle)

    def test_coherently_rebound_out_of_enum_answer_is_rejected(self):
        self.mutated_capture("invalid", "schema enum label")

    def test_valid_changed_axis_cannot_keep_stale_summary(self):
        self.mutated_capture("mechanics", "derived agreement summary")


if __name__ == "__main__":
    unittest.main()
