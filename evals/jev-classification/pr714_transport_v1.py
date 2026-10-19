"""PR714 transport: bounded TLS-connect retries; never resend a possible POST."""

import http.client
import ssl
import time

from coreinfra_transport import connection, endpoint_path, read_bounded, transient_tls

MAX_REQUEST_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


def send(endpoint, wire, key, *, emit, connection_factory=connection, sleep=time.sleep, monotonic=time.monotonic):
    path = endpoint_path(endpoint)
    if (not isinstance(wire, bytes) or not 1 <= len(wire) <= MAX_REQUEST_BYTES
            or not isinstance(key, str) or not key or any(ord(c) <= 32 or ord(c) >= 127 for c in key)):
        raise ValueError("invalid bounded request or credential")
    attempts, posts, ambiguous = [], 0, 0
    raw, status, http_status = None, "not_run", None
    for number in range(1, 4):
        started, conn, sent, retry = monotonic(), None, False, False
        emit(dict(event="attempt_started", attempt=number))
        try:
            conn = connection_factory(30.0)
            conn.connect()
            emit(dict(event="post_may_start", attempt=number))
            sent, posts = True, posts + 1
            conn.request("POST", path, body=wire, headers={"Authorization": "Bearer " + key,
                "Content-Type": "application/json", "Accept-Encoding": "identity",
                "User-Agent": "specmetrics-pr714-live/1"})
            response = conn.getresponse()
            http_status = response.status
            body = read_bounded(response, MAX_RESPONSE_BYTES)
            status = "http_response" if len(body) <= MAX_RESPONSE_BYTES else "response_too_large"
            raw = body if status == "http_response" and http_status == 200 else None
            attempt = dict(attempt=number, status=status, http_status=http_status)
        except (ssl.SSLError, OSError, http.client.HTTPException) as error:
            ambiguous += int(sent)
            retry = not sent and transient_tls(error) and number < 3
            status, raw = "transport_failed", None
            attempt = dict(attempt=number, status=status, error_type=type(error).__name__,
                           http_status=http_status, transient_tls=transient_tls(error))
        finally:
            if conn is not None:
                conn.close()
        delay = float(number) if retry else 0.0
        attempt.update(post_may_have_been_sent=sent, retry_scheduled=retry,
                       elapsed_seconds=round(monotonic() - started, 6), backoff_seconds=delay)
        attempts.append(attempt)
        emit(dict(event="attempt_finished", **attempt))
        if not retry:
            break
        sleep(delay)
    return dict(status=status, http_status=http_status, body=raw, attempts=attempts,
        network_attempts=len(attempts), potentially_billable_posts=posts, ambiguous_posts=ambiguous,
        duplicate_execution_possible=False,
        elapsed_attempt_backoff_seconds=sum(a["elapsed_seconds"] + a["backoff_seconds"] for a in attempts))
