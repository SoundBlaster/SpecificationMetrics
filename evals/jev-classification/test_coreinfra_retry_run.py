from functools import partial
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from coreinfra_retry_run import execute, load, producer_digests, sha
from coreinfra_transport import PROTOCOL, post
from test_coreinfra_transport import ENDPOINT, WIRE, FakeConnection


class RunnerTests(unittest.TestCase):
    def make_run(self, root, count=2):
        run = Path(root)
        manifest = {"protocol": PROTOCOL, "semantic_status": "unscored",
                    "retry_policy": {"max_attempts": 3},
                    "producer_digests": producer_digests(),
                    "max_network_attempts": count * 3,
                    "requests": [{"request_id": "case-" + str(n), "endpoint": ENDPOINT,
                                  "wire_json": WIRE.decode(), "wire_sha256": sha(WIRE)} for n in range(count)]}
        (run / "manifest.json").write_text(json.dumps(manifest))
        return run, manifest

    def test_offline_validates_without_key_or_network_or_artifacts(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {}, clear=True):
            run, _ = self.make_run(root)
            result = execute(run, sender=lambda *a, **k: self.fail("must not send"))
            self.assertEqual(result["max_network_attempts"], 6)
            self.assertFalse(result["inference"])
            self.assertEqual(sorted(p.name for p in run.iterdir()), ["manifest.json"])

    def test_cli_defaults_to_offline_and_rejects_historical_manifest(self):
        runner = Path(__file__).with_name("coreinfra_retry_run.py")
        with tempfile.TemporaryDirectory() as root:
            run, _ = self.make_run(root)
            output = subprocess.check_output([sys.executable, str(runner), "--run", str(run)], timeout=30)
            self.assertFalse(json.loads(output)["inference"])
            self.assertFalse((run / "attempts.jsonl").exists())
            (run / "manifest.json").write_text('{"planned_requests":32,"inference_retries":0}')
            with self.assertRaises(ValueError):
                load(run)

    def test_run_records_exact_attempt_budget_and_refuses_reuse(self):
        conns = iter([FakeConnection(fail_at="read", error=ssl.SSLEOFError()), FakeConnection(), FakeConnection()])
        sender = partial(post, connection_factory=lambda _: next(conns), sleep=lambda _: None)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"COREINFRA_API_KEY": "test-key"}):
            run, _ = self.make_run(root)
            receipt = execute(run, live=True, sender=sender)
            self.assertTrue(receipt["completed"])
            self.assertEqual(receipt["network_attempts"], 3)
            self.assertEqual(receipt["potentially_billable_posts"], 3)
            self.assertEqual(receipt["ambiguous_posts"], 1)
            self.assertTrue(receipt["duplicate_execution_possible"])
            rows = [json.loads(line) for line in (run / "responses.jsonl").read_text().splitlines()]
            self.assertEqual([r["status"] for r in rows], ["json_received"] * 2)
            self.assertTrue(all(r["semantic_status"] == "unscored" for r in rows))
            before = {p.name: p.read_bytes() for p in run.iterdir()}
            with self.assertRaisesRegex(ValueError, "Refusing to repeat"):
                execute(run, live=True, sender=lambda *a, **k: self.fail("must not send"))
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir()})

    def test_exhaustion_preserves_planned_denominator_and_stops_before_next_case(self):
        conns = iter([FakeConnection(fail_at="connect", error=ssl.SSLEOFError()) for _ in range(3)])
        sender = partial(post, connection_factory=lambda _: next(conns), sleep=lambda _: None)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"COREINFRA_API_KEY": "test-key"}):
            run, _ = self.make_run(root)
            receipt = execute(run, live=True, sender=sender)
            self.assertFalse(receipt["completed"])
            self.assertEqual(receipt["planned_requests"], 2)
            self.assertEqual(receipt["attempted_requests"], 1)
            self.assertEqual(receipt["network_attempts"], 3)
            self.assertEqual(receipt["potentially_billable_posts"], 0)
            self.assertEqual(receipt["stop_reason"], "transport_error")

    def test_http_and_invalid_json_stop_without_retry_or_error_body_retention(self):
        for status, body, stop in [(503, b'secret-test-only', "http_error"),
                                   (200, b'{"a":1,"a":2}', "response_decode_error"),
                                   (200, b'{"a":1e999}', "response_decode_error"),
                                   (200, b'[]', "response_decode_error")]:
            with self.subTest(stop=stop), tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"COREINFRA_API_KEY": "test-key"}):
                run, _ = self.make_run(root)
                sender = partial(post, connection_factory=lambda _: FakeConnection(status=status, body=body))
                receipt = execute(run, live=True, sender=sender)
                self.assertEqual(receipt["network_attempts"], 1)
                self.assertEqual(receipt["stop_reason"], stop)
                self.assertNotIn("secret-test-only", (run / "responses.jsonl").read_text())

    def test_invalid_frozen_input_fails_before_network(self):
        for change in [lambda m: m.update(max_network_attempts=7),
                       lambda m: m["requests"][0].update(wire_sha256="wrong"),
                       lambda m: m["requests"][1].update(request_id="case-0"),
                       lambda m: m["producer_digests"].update({"coreinfra_transport.py": "wrong"}),
                       lambda m: m["requests"][0].update(endpoint="https://evil.test/x")]:
            with tempfile.TemporaryDirectory() as root:
                run, manifest = self.make_run(root)
                change(manifest)
                (run / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    load(run)
                self.assertFalse((run / "attempts.jsonl").exists())

    def test_float_response_limit_is_rejected_before_live_artifacts_or_send(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"COREINFRA_API_KEY": "test-key"}):
            run, manifest = self.make_run(root)
            manifest["retry_policy"]["max_response_bytes"] = 1048576.0
            (run / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                execute(run, live=True, sender=lambda *a, **k: self.fail("must not send"))
            self.assertEqual(sorted(p.name for p in run.iterdir()), ["manifest.json"])

    def test_unexpected_failure_keeps_incomplete_receipt_and_blocks_rerun(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"COREINFRA_API_KEY": "test-key"}):
            run, _ = self.make_run(root)
            def fail(*a, **k):
                raise RuntimeError("secret-test-only")
            with self.assertRaises(RuntimeError):
                execute(run, live=True, sender=fail)
            receipt = json.loads((run / "receipt.json").read_text())
            self.assertFalse(receipt["completed"])
            self.assertFalse(receipt["attempt_ledger_complete"])
            self.assertIsNone(receipt["ambiguous_posts"])
            self.assertNotIn("secret-test-only", (run / "receipt.json").read_text())
            with self.assertRaisesRegex(ValueError, "Refusing to repeat"):
                execute(run, live=True, sender=fail)


if __name__ == "__main__":
    unittest.main()
