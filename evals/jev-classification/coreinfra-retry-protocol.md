# CoreInfra transport protocol v1

Status: implemented, tested with injected connections; no new hosted experiment
or semantic comparison has been run under this protocol.

The user reports Jev and Luna Decision availability through CoreInfra, including
intermittent TLS/SSL failures. Availability of Luna's operation URL and native
request/response schema still needs a separate verification. The transport does
not translate Jev requests into Luna requests or assume that their APIs match.

## Policy

`specmetrics.coreinfra-tls-retry/v1` is for **new runs only**:

- At most three connection attempts per logical request, including the first.
  A fresh verified HTTPS connection is used each time.
- Backoff is one second, then two seconds. A one-attempt policy is also allowed.
- Repeat only TLS EOF/closed-session errors, explicitly recognized transient
  internal TLS alerts, and premature HTTP body termination (`IncompleteRead`
  or unsatisfied Content-Length/chunked framing). A valid JSON prefix cannot
  establish body completeness. Known non-200 HTTP responses are never retried,
  even if their body terminates prematurely. Other SSL errors, certificate validation failures, timeout,
  reset/disconnect, HTTP errors (including 429/5xx), redirects and decoder errors
  stop the run. Certificate verification is never disabled.
- Retry sends the identical request bytes to the identical explicit operation
  URL on `https://hub.coreinfra.ai`. No redirects or environment proxy routing.
- Socket timeout is 30 seconds; request bound is 64 KiB and response bound is
  1 MiB. The socket timeout is **not** a total wall-clock deadline: DNS and a peer
  that keeps sending data can take longer. This protocol bounds attempt count,
  not total runtime or dollar cost.
  The response byte limit must be a JSON integer, not an equal-valued float;
  malformed policies are rejected before any connection or POST.
- Before TLS connects, no Authorization header or inference is sent. Once
  `request()` might have begun, a failure is ambiguous: the provider may have
  executed and billed it. Retrying can duplicate execution; no exactly-once or
  idempotency guarantee is claimed.

## Runner and evidence

`coreinfra_retry_run.py` validates a run's `manifest.json`. Its requests contain
distinct IDs, full native wire JSON, SHA-256 of the exact UTF-8 bytes, an explicit
model inside that JSON, and a full operation URL. It supports one to 32 logical
requests. The frozen total connection-attempt budget must equal the number of
requests times `max_attempts` (at most 96). Every attempt that reaches POST may
be billable, including failed or duplicated requests; tokens/cost from those
attempts can remain unknown. These limits do not guarantee the key's dollar cap.

The manifest freezes SHA-256 digests of the transport, runner and strict JSON
decoder implementation. The runner checks those digests before execution and
between logical requests. `--live` authorizes the full worst-case attempt budget;
without it, validation does not read the key, create output files or use network.
`COREINFRA_API_KEY` is taken from the process environment, never the manifest.

Outputs are created exclusively; any existing output prevents rerunning:

| File | Meaning |
| --- | --- |
| `attempts.jsonl` | UTC timestamps, ordered events, request ID and wire digest; start, possible POST start, completion/error and backoff seconds. Each event is flushed and fsynced before proceeding. No headers, keys or error messages. |
| `responses.jsonl` | One row per attempted logical request, transport receipt and successful JSON object. Error bodies are omitted. Native successful responses may contain source/context: treat the run as an evaluation artifact. |
| `receipt.json` | Manifest/producer digests, frozen policy, original planned denominator, attempted logical requests, actual network attempts, potentially billable POSTs, ambiguity and stop reason. |

`completed` means every planned request returned HTTP 200 and a strict JSON
object. It **does not mean native response validation or semantic correctness**.
All results have `semantic_status: unscored`. Each provider still needs its own
typed validator before the semantic scorer. No registry/S/U changes are made.
Transport exhaustion is `transport_error`, never classifier `needs_review`.
HTTP and decode errors are separate statuses and are not retried.

If an unexpected exception/interrupt occurs, the receipt is incomplete and
ambiguity fields are unknown. A hard process kill may leave only the ledger;
absence of a receipt does not mean no request ran. Never resume or overwrite that
directory. Count it as an interrupted run before creating a separately identified
new run. Planned cases that were not reached remain in the denominator.

## Creating a new manifest

From this directory, using the experiment's already frozen native request bytes:

```python
import json
from dataclasses import asdict
from pathlib import Path
from coreinfra_retry_run import producer_digests, sha
from coreinfra_transport import PROTOCOL, RetryPolicy

# Supply verified native requests for each provider, not a shared assumed schema.
# requests = [{"request_id": "case-01-jev", "endpoint": explicit_operation_url,
#              "wire_json": native_wire.decode("utf-8"),
#              "wire_sha256": sha(native_wire)}, ...]
policy = RetryPolicy()
new_run = Path("runs/NEW-RUN-ID")
new_run.mkdir()  # A new directory; never an existing run.
manifest = {
    "protocol": PROTOCOL,
    "semantic_status": "unscored",
    "retry_policy": asdict(policy),
    "producer_digests": producer_digests(),
    "max_network_attempts": len(requests) * policy.max_attempts,
    "requests": requests,
}
with (new_run / "manifest.json").open("x") as out:
    json.dump(manifest, out, indent=2)
```

```sh
python3 coreinfra_retry_run.py --run path/to/new-run
# Only after freezing the new experiment and its complete attempt budget:
python3 coreinfra_retry_run.py --run path/to/new-run --live
```

Old runners, producer hashes, raw responses and receipts remain unchanged. Their
zero-inference-retry declarations remain true; the new runner refuses their old
manifest schema. Do not reinterpret historical scores under this policy.

## Next semantic experiment

1. Add bounded, source-digested helper/data context to the explicit decision
   targets: in particular `_pre_sib_original_blocked` for sg017, the origins of
   `refs`/`existing_ac` for sg019, and relevant allocation inputs for sg033.
2. Freeze identical target/context/profile/rubric inputs for both providers,
   allowing only documented native schema encodings to differ. Obtain fresh
   target-specific reference annotations; old whole-function labels do not apply.
3. Verify Luna's actual CoreInfra operation URL, explicit model and typed schema.
   Keep response acceptance distinct from semantic agreement.
4. Preregister case count, repetitions, comparison criteria, attempt budget and
   interrupted-run accounting. Use a new run ID and this transport version.
5. Report semantic agreement/recall/false positives alongside completion rate,
   attempts, transport failures and duplicate-execution ambiguity. Failed and
   unattempted cases must not disappear from the planned denominator.
