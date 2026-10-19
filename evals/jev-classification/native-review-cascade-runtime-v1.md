# Native uncertainty cascade runtime · v1

Consumer: `specgraph_pr714_live_v2.py`.
Study: `specmetrics.specgraph-pr714-native-cascade/v2`.
Routing adapter: `specmetrics.native-review-cascade/v1`.

This is a new runtime version consuming the exact PR714 source packets and
request templates. Native uncertainty is **enforced** by this runner, rather
than merely reported in a shadow comparison. The historical v1 runner, native
uncertainty shadow evaluator, rich-review v1 preparation/inspector, results and
spent leases are frozen and unchanged.

## Execution contract

1. Verify source preparation, producer hashes, current local SDK/runtime and all
   eight exact request templates before dispatch: four native Jev batches and at
   most four conditional ordinary Luna reviews. No labels enter review requests.
2. Route each completed native capture with the qualified Jev profile and the
   unchanged strict-majority Specifications. Invalid captures stop that decision;
   existing semantic-review reasons and action-required axes retain priority.
3. Prepare a rich review only on the **enforced** route. Derive its complete
   original context from the actual native capture; do not add artificial evidence
   gaps or alter labels just to pass the old preparation gate.
4. Compare a selected review request exactly against its frozen template before
   dispatch. Use the same independent guidance, evidence, four questions, schema,
   Luna model, reasoning effort `low` and 1024 output-token bound.
5. Inspect returned citations, task/request identities, evidence gaps and material
   disagreements using the existing resolution Specifications. Report explicit
   `needs_review` or `analysis_incomplete` where resolution fails. A resolved
   proposal remains unaccepted; S/U and publication authority never change.

All public plan consumers rebuild derived selection and review context from the
same immutable bound task/raw capture. There is no separately supplied review
object or categorical snapshot to mix with a different original assessment.
Native confidence/distributions are diagnostic evidence for routing only and
are excluded from the independent model request.

## Bounds and authorization

Maximum: eight logical calls, 24 pre-POST connection attempts, eight possible
POSTs. Each request permits up to three recognized transient TLS connect attempts
with 1/2 second backoffs; never retry after a possible POST. Verified TLS, fixed
CoreInfra endpoints, no redirects, 96 KiB request bound, 1 MiB response bound,
30-second socket timeout, 100-second child deadline, 900-second dispatch deadline.
No recursive review, semantic retry, Sol call, context expansion or model fallback.

The preparation-level exclusive lease prevents spending the same preparation
through another output directory. Each run owns its attempt ledgers, requests,
successful raw captures, transport/process receipts and reports. The worker
validates the v2 manifest and lease; child timeout terminates its process group.
Private local paths and child stdout/stderr are not published.

**Implementing or freezing this runtime does not authorize inference.** A future
live run requires a separately approved bounded budget and fresh preparation/run
paths. No request is made without `run --live`; default `run` only validates.
The original paid PR714 reservation must not be reused. This task performs no
new hosted calls and does not prepare a second paid run automatically.

## CLI

From `evals/jev-classification` in the repository environment:

```sh
../../.venv/bin/python -B specgraph_pr714_live_v2.py freeze --preparation <new-preparation>
../../.venv/bin/python -B specgraph_pr714_live_v2.py run --preparation <new-preparation> --run <new-run>
```

After a separately authorized live execution, `report` and `verify` use the same
explicit paths. The CLI's pending defaults are unspent placeholders, not evidence
that any live authorization exists. Replay retains the historical exact-local-
runtime qualification; portable cross-host real-result verification is not claimed.

Offline tests substitute transport results and block sockets. A synthetic
seven-dispatch scenario uses the four preserved native response bodies as parser
fixtures and **synthetic** rich reviews: three conditional reviews, one retained
proposal, plus resolved, materially conflicting and failed review outcomes.
This exercises orchestration and resolution, not new provider/semantic quality.
