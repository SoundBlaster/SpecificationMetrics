import http.client
import io
import json
import ssl
import unittest

from coreinfra_transport import LedgerError, RetryPolicy, connection, endpoint_path, post


ENDPOINT = "https://hub.coreinfra.ai/typesafe/api/v1/systemone"
WIRE = b'{"model":"jev-1.13.0","state":"test","questions":{}}'


class FakeConnection:
    def __init__(self, *, fail_at=None, error=None, status=200, body=b'{}'):
        self.fail_at, self.error, self.status, self.body = fail_at, error, status, body
        self.requests = []
        self.closed = False
        self.length, self.chunked = None, False

    def fail(self, stage):
        if self.fail_at == stage:
            raise self.error

    def connect(self):
        self.fail("connect")

    def request(self, method, path, body, headers):
        self.requests.append((method, path, body, headers))
        self.fail("request")

    def getresponse(self):
        self.fail("response")
        return self

    def read(self, limit):
        self.fail("read")
        return self.body[:limit]

    def close(self):
        self.closed = True


class TransportTests(unittest.TestCase):
    def framed_connection(self, wire):
        class Socket:
            def makefile(self, *args):
                return io.BytesIO(wire)
        response = http.client.HTTPResponse(Socket())
        response.begin()
        conn = FakeConnection()
        conn.getresponse = lambda: response
        return conn

    def call(self, connections, **kwargs):
        self.events, self.delays, self.created = [], [], []
        def factory(timeout):
            self.assertEqual(timeout, 30)
            conn = connections[len(self.created)]
            self.created.append(conn)
            return conn
        result = post(ENDPOINT, WIRE, "secret-test-only", live=True,
                      emit=self.events.append, connection_factory=factory,
                      sleep=self.delays.append, **kwargs)
        self.assertTrue(all(c.closed for c in self.created))
        self.assertNotIn("secret-test-only", json.dumps(self.events))
        self.assertNotIn("secret-test-only", str(result))
        return result

    def test_connect_eof_then_success_has_no_duplicate_billing_risk(self):
        failed = FakeConnection(fail_at="connect", error=ssl.SSLEOFError())
        ok = FakeConnection()
        result = self.call([failed, ok])
        self.assertEqual(result["status"], "http_response")
        self.assertEqual(result["network_attempts"], 2)
        self.assertEqual(result["potentially_billable_posts"], 1)
        self.assertFalse(result["duplicate_execution_possible"])
        self.assertEqual(self.delays, [1.0])
        self.assertEqual(failed.requests, [])

    def test_post_send_failures_retry_identical_wire_with_ambiguity(self):
        for stage in ["request", "response", "read"]:
            with self.subTest(stage=stage):
                failed = FakeConnection(fail_at=stage, error=ssl.SSLEOFError())
                ok = FakeConnection()
                result = self.call([failed, ok])
                self.assertEqual(failed.requests, ok.requests)
                self.assertEqual(ok.requests[0][2], WIRE)
                self.assertEqual(result["ambiguous_posts"], 1)
                self.assertEqual(result["potentially_billable_posts"], 2)
                self.assertTrue(result["duplicate_execution_possible"])
                self.assertEqual(result["semantic_status"], "unscored")

    def test_exhaustion_is_transport_error_and_attempt_cap_includes_first(self):
        result = self.call([FakeConnection(fail_at="read", error=ssl.SSLEOFError()) for _ in range(3)])
        self.assertEqual(result["status"], "transport_error")
        self.assertEqual(result["network_attempts"], 3)
        self.assertEqual(self.delays, [1.0, 2.0])
        self.assertEqual([e["attempt"] for e in self.events if e["event"] == "attempt_finished"], [1, 2, 3])
        self.assertFalse(result["attempts"][-1]["retry_scheduled"])

    def test_one_attempt_policy_disables_retries(self):
        result = self.call([FakeConnection(fail_at="connect", error=ssl.SSLEOFError())], policy=RetryPolicy(max_attempts=1))
        self.assertEqual(result["network_attempts"], 1)
        self.assertEqual(self.delays, [])

    def test_no_retry_on_certificate_timeout_reset_or_generic_ssl_error(self):
        for error in [ssl.SSLCertVerificationError(), TimeoutError(), ConnectionResetError(),
                      ssl.SSLError(), http.client.RemoteDisconnected()]:
            with self.subTest(error=type(error).__name__):
                result = self.call([FakeConnection(fail_at="connect", error=error)])
                self.assertEqual(result["network_attempts"], 1)
                self.assertEqual(self.delays, [])

    def test_known_transient_alert_retries(self):
        error = ssl.SSLError()
        error.reason = "TLSV1_ALERT_INTERNAL_ERROR"
        result = self.call([FakeConnection(fail_at="connect", error=error), FakeConnection()])
        self.assertEqual(result["network_attempts"], 2)

    def test_http_errors_redirects_and_malformed_bodies_never_retry(self):
        for status in [200, 302, 401, 429, 500, 503]:
            with self.subTest(status=status):
                result = self.call([FakeConnection(status=status, body=b'not json')])
                self.assertEqual(result["http_status"], status)
                self.assertEqual(result["body"], b'not json')
                self.assertEqual(result["network_attempts"], 1)
                self.assertEqual(result["semantic_status"], "unscored")

    def test_response_size_bound_does_not_retry(self):
        result = self.call([FakeConnection(body=b'x' * (1024 * 1024 + 1))])
        self.assertEqual(result["status"], "response_too_large")
        self.assertIsNone(result["body"])
        self.assertEqual(self.delays, [])

    def test_real_http_truncation_retries_even_when_prefix_is_valid_json(self):
        for wire in [b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n{}',
                     b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n',
                     b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n',
                     b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\n{}']:
            with self.subTest(wire=wire):
                failed = self.framed_connection(wire)
                ok = FakeConnection()
                result = self.call([failed, ok])
                self.assertEqual(result["body"], b'{}')
                self.assertEqual(result["network_attempts"], 2)
                self.assertTrue(result["attempts"][0]["incomplete_http_body"])
                self.assertTrue(result["duplicate_execution_possible"])
                self.assertEqual(failed.requests, ok.requests)

    def test_real_complete_framed_responses_are_not_retried(self):
        for wire in [b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}',
                     b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n']:
            with self.subTest(wire=wire):
                result = self.call([self.framed_connection(wire)])
                self.assertEqual(result["body"], b'{}')
                self.assertEqual(result["network_attempts"], 1)

    def test_truncated_body_exhaustion_never_returns_json_prefix(self):
        wire = b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n{}'
        result = self.call([self.framed_connection(wire) for _ in range(3)])
        self.assertEqual(result["status"], "transport_error")
        self.assertIsNone(result["body"])
        self.assertEqual(self.delays, [1.0, 2.0])

    def test_truncated_http_error_does_not_retry(self):
        wire = b'HTTP/1.1 503 Unavailable\r\nContent-Length: 10\r\n\r\n{}'
        result = self.call([self.framed_connection(wire)])
        self.assertEqual(result["network_attempts"], 1)
        self.assertEqual(result["attempts"][0]["http_status"], 503)
        self.assertEqual(self.delays, [])

    def test_verified_tls_is_required_before_post(self):
        real = connection(30)
        self.assertEqual(real.host, "hub.coreinfra.ai")
        self.assertTrue(real._context.check_hostname)
        self.assertEqual(real._context.verify_mode, ssl.CERT_REQUIRED)
        real.close()  # No connect or network call.
        self.call([FakeConnection()])
        self.assertEqual([e["event"] for e in self.events],
                         ["attempt_started", "post_may_start", "attempt_finished"])

    def test_ledger_failure_stops_before_post_or_retry(self):
        for event in ["attempt_started", "post_may_start", "attempt_finished"]:
            with self.subTest(event=event):
                conn = FakeConnection(fail_at="read", error=ssl.SSLEOFError())
                def emit(row):
                    if row["event"] == event:
                        raise OSError("secret-test-only")
                with self.assertRaisesRegex(LedgerError, "Attempt ledger unavailable"):
                    post(ENDPOINT, WIRE, "secret-test-only", live=True, emit=emit,
                         connection_factory=lambda _: conn,
                         sleep=lambda _: self.fail("must not retry"))
                if event != "attempt_finished":
                    self.assertEqual(conn.requests, [])

    def test_bad_origin_and_missing_live_never_create_connection(self):
        for endpoint in ["http://hub.coreinfra.ai/x", "https://evil.test/x",
                         "https://hub.coreinfra.ai@evil.test/x", ENDPOINT + "?key=secret",
                         ENDPOINT + "#fragment", ENDPOINT + "\n"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                endpoint_path(endpoint)
        with self.assertRaises(ValueError):
            post(ENDPOINT, WIRE, "key", emit=lambda _: None,
                 connection_factory=lambda _: self.fail("must not connect"))

    def test_operation_path_is_explicit_and_does_not_assume_jev_payload(self):
        conn = FakeConnection()
        body = b'{"model":"explicit-decision-model","input":"different API"}'
        result = post("https://hub.coreinfra.ai/explicit-operation", body, "test-key",
                      live=True, emit=lambda _: None, connection_factory=lambda _: conn)
        self.assertEqual(conn.requests[0][1:3], ("/explicit-operation", body))
        self.assertEqual(result["semantic_status"], "unscored")

    def test_invalid_policy_rejected(self):
        for kwargs in [{"max_attempts": 4}, {"max_attempts": True},
                       {"backoff_seconds": (0, 0)}, {"timeout_seconds": 0},
                       {"max_response_bytes": 0}, {"max_response_bytes": 1048576.0},
                       {"max_response_bytes": True}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                RetryPolicy(**kwargs)


if __name__ == "__main__":
    unittest.main()
