"""Opt-in transport for NEW CoreInfra evaluation protocols; never scores answers."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import ssl
import time
from urllib.parse import urlsplit


PROTOCOL = "specmetrics.coreinfra-tls-retry/v1"
HOST = "hub.coreinfra.ai"


class LedgerError(RuntimeError):
    """A failed attempt ledger must never trigger or continue inference."""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: tuple = (1.0, 2.0)
    timeout_seconds: float = 30.0
    max_response_bytes: int = 1024 * 1024

    def __post_init__(self):
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 3:
            raise ValueError("Expected one to three total attempts")
        if tuple(self.backoff_seconds) != (1.0, 2.0):
            raise ValueError("Protocol v1 fixes backoff to one and two seconds")
        object.__setattr__(self, "backoff_seconds", tuple(self.backoff_seconds))
        if self.timeout_seconds != 30.0 or self.max_response_bytes != 1024 * 1024:
            raise ValueError("Protocol v1 fixes socket timeout and response bound")

    def receipt(self):
        return {"protocol": PROTOCOL, **asdict(self)}


def endpoint_path(endpoint):
    """Exact CoreInfra HTTPS origin only; no redirects, credentials or query."""
    url = urlsplit(endpoint)
    if (url.scheme != "https" or url.netloc != HOST or not url.path.startswith("/")
            or url.query or url.fragment or any(ord(c) <= 32 or ord(c) >= 127 for c in endpoint)):
        raise ValueError("Expected an explicit CoreInfra HTTPS operation URL")
    return url.path


def transient_tls(error):
    # A bad certificate/configuration is not a transient provider outage.
    if isinstance(error, ssl.SSLCertVerificationError):
        return False
    return isinstance(error, (ssl.SSLEOFError, ssl.SSLZeroReturnError)) or (
        isinstance(error, ssl.SSLError)
        and getattr(error, "reason", None) in {
            "TLSV1_ALERT_INTERNAL_ERROR", "SSLV3_ALERT_INTERNAL_ERROR", "UNEXPECTED_EOF_WHILE_READING",
        }
    )


def connection(timeout):
    return http.client.HTTPSConnection(HOST, timeout=timeout, context=ssl.create_default_context())


def post(endpoint, wire, key, *, live=False, policy=RetryPolicy(), emit,
         connection_factory=connection, sleep=time.sleep, monotonic=time.monotonic):
    """Send identical bytes at most three times, with a caller-owned durable ledger.

    ``emit`` must append and flush each event. If logging fails, stop immediately.
    The caller must reserve ``policy.max_attempts`` from its total attempt budget
    BEFORE calling, freeze endpoint/model/wire/policy/implementation digests, and
    refuse reuse of an existing run. No response decoder runs inside the retry loop.
    """
    path = endpoint_path(endpoint)
    if not live:
        raise ValueError("Hosted inference requires explicit live opt-in")
    if not isinstance(wire, bytes) or not wire or len(wire) > 64 * 1024:
        raise ValueError("Expected one to 65536 exact request bytes")
    if not isinstance(key, str) or not key or any(ord(c) <= 32 or ord(c) >= 127 for c in key):
        raise ValueError("Invalid credential")
    identity = {"protocol": PROTOCOL, "wire_sha256": hashlib.sha256(wire).hexdigest()}
    def record(event):
        try:
            emit({"recorded_at": datetime.now(timezone.utc).isoformat(), **event})
        except Exception:
            # Do not leak logger messages or treat disk errors as network errors.
            raise LedgerError("Attempt ledger unavailable; stop this run") from None

    attempts, ambiguous_posts = [], 0
    for number in range(1, policy.max_attempts + 1):
        stage, sent, retry, conn = "connect", False, False, None
        t = monotonic()
        record({**identity, "event": "attempt_started", "attempt": number})
        try:
            conn = connection_factory(policy.timeout_seconds)
            conn.connect()  # Verified TLS; no credential or HTTP before success.
            stage = "request"
            # Persist BEFORE request(): even a failed write may have sent bytes.
            record({**identity, "event": "post_may_start", "attempt": number})
            sent = True
            conn.request("POST", path, body=wire, headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json",
                "Accept-Encoding": "identity", "User-Agent": "specmetrics-coreinfra-retry/1",
            })
            stage = "response"
            response = conn.getresponse()
            stage = "read"
            raw = response.read(policy.max_response_bytes + 1)
            status = "http_response" if len(raw) <= policy.max_response_bytes else "response_too_large"
            result = {"status": status, "http_status": response.status, "body": raw if status == "http_response" else None}
            attempt = {"attempt": number, "stage": stage, "status": status,
                       "http_status": response.status, "post_may_have_been_sent": True,
                       "retry_scheduled": False}
        except (ssl.SSLError, OSError, http.client.HTTPException) as error:
            if sent:
                ambiguous_posts += 1
            retry = transient_tls(error) and number < policy.max_attempts
            attempt = {"attempt": number, "stage": stage, "status": "transport_error",
                       "error_type": type(error).__name__, "transient_tls": transient_tls(error),
                       "post_may_have_been_sent": sent, "retry_scheduled": retry}
            result = {"status": "transport_error", "http_status": None, "body": None}
        finally:
            if conn is not None:
                conn.close()
        attempt["elapsed_seconds"] = round(monotonic() - t, 6)
        attempt["backoff_seconds"] = policy.backoff_seconds[number - 1] if retry else 0
        attempts.append(attempt)
        record({**identity, "event": "attempt_finished", **attempt})
        if not retry:
            break
        sleep(policy.backoff_seconds[number - 1])
    return {**identity, **result, "policy": policy.receipt(), "attempts": attempts,
            "network_attempts": len(attempts),
            "potentially_billable_posts": sum(a["post_may_have_been_sent"] for a in attempts),
            "ambiguous_posts": ambiguous_posts,
            "duplicate_execution_possible": ambiguous_posts > 0 and sum(a["post_may_have_been_sent"] for a in attempts) > 1,
            "semantic_status": "unscored"}
