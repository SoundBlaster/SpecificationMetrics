import base64
import importlib.metadata
import json
from pathlib import Path
import ssl
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pr714_transport_v1 import send
from test_coreinfra_transport import FakeConnection


class TransportTests(unittest.TestCase):
    def transport(self, connections, wire=b"{}"):
        events, sleeps, created = [], [], []
        def factory(timeout):
            self.assertEqual(timeout, 30)
            conn = connections[len(created)]
            created.append(conn)
            return conn
        result = send("https://hub.coreinfra.ai/typesafe/api/v1/systemone", wire, "synthetic-secret",
            emit=events.append, connection_factory=factory, sleep=sleeps.append)
        self.assertTrue(all(c.closed for c in created))
        return result, events, sleeps

    def test_pre_post_tls_retry_is_bounded_and_posts_once(self):
        result, events, sleeps = self.transport([FakeConnection(fail_at="connect", error=ssl.SSLEOFError()),
            FakeConnection(fail_at="connect", error=ssl.SSLEOFError()), FakeConnection()])
        self.assertEqual(result["network_attempts"], 3)
        self.assertEqual(result["potentially_billable_posts"], 1)
        self.assertEqual(sleeps, [1, 2])
        self.assertEqual(sum(e["event"] == "post_may_start" for e in events), 1)

    def test_possible_post_failure_never_retries(self):
        for stage in ("request", "response", "read"):
            with self.subTest(stage=stage):
                result, _, delays = self.transport([FakeConnection(fail_at=stage, error=ssl.SSLEOFError())])
                self.assertEqual((result["network_attempts"], result["potentially_billable_posts"], result["ambiguous_posts"]), (1, 1, 1))
                self.assertEqual(delays, [])
                self.assertFalse(result["duplicate_execution_possible"])

    def test_certificate_and_http_errors_do_not_retry(self):
        for connection in (FakeConnection(fail_at="connect", error=ssl.SSLCertVerificationError()),
                           FakeConnection(status=401, body=b"do not publish error body")):
            result, _, sleeps = self.transport([connection])
            self.assertEqual(result["network_attempts"], 1)
            self.assertIsNone(result["body"])
            self.assertEqual(sleeps, [])

    def test_profile_accepts_96k_and_rejects_larger_and_oversized_response(self):
        self.transport([FakeConnection()], b"x" * (96 * 1024))
        with self.assertRaises(ValueError):
            self.transport([], b"x" * (96 * 1024 + 1))
        result, _, _ = self.transport([FakeConnection(body=b"x" * (1048576 + 1))])
        self.assertEqual(result["status"], "response_too_large")
        self.assertIsNone(result["body"])


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        version = importlib.metadata.version("mellea-jev-adapter")
        if tuple(int(v) for v in version.split(".")[:2]) < (0, 9):
            raise unittest.SkipTest("live pilot uses current SDK, never inference in CI")
        import specgraph_pr714_live_v1
        cls.p = specgraph_pr714_live_v1

    def synthetic_dispatch(self, directory, timeout):
        p = self.p
        request = p.read(directory / "request.json")
        wire = json.loads(request["wire_json"])
        if request["kind"] == "jev":
            labels = dict(concern_kind="unknown", evidence_confidence="insufficient",
                          ownership="unknown", tool_responsibility="unknown")
            body = dict(model="jev-1.13.0", answers={axis: dict(type="choice", choice=labels[axis], confidence=1.0,
                probabilities={value: float(value == labels[axis]) for value in question["criteria"]})
                for axis, question in wire["questions"].items()}, usage=dict(input_tokens=10, output_tokens=5))
            raw = p.encoded(body).encode()
        else:
            # A failed rich review must stay visible, never turn into a clean result.
            raw = b'{"status":"incomplete","model":"gpt-6-luna","output":[]}'
        events = [dict(event="attempt_started", attempt=1), dict(event="post_may_start", attempt=1),
            dict(event="attempt_finished", attempt=1, retry_scheduled=False, post_may_have_been_sent=True)]
        with (directory / "attempts.jsonl").open("x") as out:
            for event in events:
                out.write(p.encoded(dict(event, request_sha256=request["wire_sha256"])) + "\n")
        p.write(directory / "response.json", dict(request_sha256=request["wire_sha256"],
            raw_body_base64=base64.b64encode(raw).decode(), raw_body_sha256=p.sha(raw)))
        p.write(directory / "transport.json", dict(network_attempts=1, potentially_billable_posts=1,
            http_status=200, ambiguous_posts=0, status="http_response"))
        p.write(directory / "execution.json", dict(child_exit_code=0, hard_timeout=False, wall_seconds=0.01, hard_limit_seconds=timeout))

    def test_preparation_and_full_synthetic_route_cannot_respend(self):
        p = self.p
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", COREINFRA_API_KEY="synthetic-not-real"), patch(
                "socket.socket.connect", side_effect=AssertionError("offline")):
            prep, run = Path(td)/"prep", Path(td)/"run"
            p.freeze(prep)
            self.assertFalse(p.run(prep, run)["inference"])
            self.assertFalse(run.exists())
            result = p.run(prep, run, live=True, dispatcher=self.synthetic_dispatch)
            self.assertEqual(result["logical_requests"], 8)
            report = p.analyze(prep, run)
            self.assertEqual(report["selected_reviews"], 4)
            self.assertTrue(all(c["status"] == "analysis_incomplete" for c in report["cases"]))
            self.assertFalse(report["automatic_fact_acceptance"])
            p.save_report(prep, run)
            self.assertTrue(p.verify_result(prep, run)["verified"])
            with self.assertRaisesRegex(ValueError, "already spent"):
                p.run(prep, Path(td)/"another", live=True, dispatcher=self.synthetic_dispatch)

    def test_changed_request_or_producer_binding_is_rejected_before_live(self):
        p = self.p
        with tempfile.TemporaryDirectory() as td:
            prep = Path(td)/"prep"
            p.freeze(prep)
            path = prep/"manifest.json"
            manifest = p.read(path)
            manifest["requests"][0]["wire_json"] += " "
            path.write_text(p.encoded(manifest))
            with self.assertRaisesRegex(ValueError, "frozen request"):
                p.run(prep, Path(td)/"run")

    def test_hard_timeout_kills_process_group_without_publishing_stderr(self):
        p = self.p
        class Process:
            pid, returncode = 123456, -9
            calls = 0
            def communicate(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired("synthetic", 1)
                return b"private", b"private"
        with tempfile.TemporaryDirectory() as td, patch.object(p.subprocess, "Popen", return_value=Process()), patch.object(p.os, "killpg") as kill:
            directory = Path(td)
            p.dispatch(directory, 1)
            kill.assert_called_once_with(123456, p.signal.SIGKILL)
            self.assertTrue(p.read(directory/"execution.json")["hard_timeout"])
            self.assertNotIn("private", (directory/"execution.json").read_text())


if __name__ == "__main__":
    unittest.main()
