from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import codex_envelope_ablation_v1 as v1
import codex_envelope_analysis_v2 as v2
from test_codex_envelope_ablation_v1 import synthetic_sender


class InterruptedAnalysisTests(unittest.TestCase):
    def interrupted(self, run, error, completed_prefix):
        v1.freeze(run)
        calls = 0

        def sender(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls <= completed_prefix:
                return synthetic_sender(*args, **kwargs)
            # Synthetic durable transport events; no network operation.
            kwargs["emit"]({"event": "attempt_started"})
            kwargs["emit"]({"event": "post_may_start"})
            raise error()

        with patch.dict("os.environ", COREINFRA_API_KEY="synthetic-not-a-secret"):
            with self.assertRaises(error):
                v1.execute(run, live=True, sender=sender)
        with self.assertRaisesRegex(ValueError, "response prefix count"):
            v1.analyze(run)
        result = v2.analyze(run)
        self.assertEqual(result["status"], "incomplete_not_evaluable")
        self.assertEqual(result["hypothesis_status"], "not_evaluable")
        self.assertIsNone(result["narrow_hypothesis_supported"])
        self.assertFalse(result["automatic_fact_acceptance"])
        manifest = v1.decode((run / "manifest.json").read_bytes())
        self.assertEqual(result["in_flight_request_without_response"],
                         manifest["requests"][completed_prefix]["request_id"])
        self.assertEqual(len(result["observations"]), completed_prefix)

    def test_sender_exception_and_keyboard_interrupt_remain_diagnosable(self):
        for error in (RuntimeError, KeyboardInterrupt):
            for prefix in (0, 1):
                with self.subTest(error=error, prefix=prefix), tempfile.TemporaryDirectory() as td:
                    self.interrupted(Path(td) / "run", error, prefix)

    def test_extra_missing_rows_and_false_complete_are_rejected(self):
        for mutation in ({"attempted_requests": 2}, {"completed": True},
                         {"attempt_ledger_complete": True}, {"stop_reason": None}):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as td:
                run = Path(td) / "run"
                self.interrupted(run, RuntimeError, 0)
                receipt = v1.decode((run / "receipt.json").read_bytes())
                receipt.update(mutation)
                (run / "receipt.json").write_text(v1.encoded(receipt))
                result = v1.decode((run / "result-receipt.json").read_bytes())
                result["files_sha256"]["receipt.json"] = v1.sha((run / "receipt.json").read_bytes())
                (run / "result-receipt.json").write_text(v1.encoded(result))
                with self.assertRaisesRegex(ValueError, "response prefix count"):
                    v2.analyze(run)

    def test_completed_observation_keeps_identical_scoring(self):
        result = v2.analyze(v1.RUN)
        self.assertIsNone(result.pop("in_flight_request_without_response"))
        self.assertEqual(result.pop("consumer"), "specmetrics.codex-envelope-analysis/v2")
        self.assertEqual(result, v1.decode((v1.RUN / "comparison.json").read_bytes()))


if __name__ == "__main__":
    unittest.main()
