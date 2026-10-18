# Native instruction-parity repeat against unchanged Sol

**Observed:** 2026-10-18 10:35:45.564–10:36:13.490 UTC, 27.926 seconds.
16 logical requests, 16 attempts and potentially billable POSTs; no TLS retries,
ambiguous posts or possible duplicates. All 16 responses passed native identity
and shape checks. These are agreement observations against the existing Sol
comparator, not semantic accuracy or production acceptance rates.

## Before → after

| Measure | Jev 1.13.0 | Luna Decision (`gpt-6-luna`) |
|---|---:|---:|
| All four axes matching Sol | 25/32 → **31/32** | 15/32 → **18/32** |
| Role + ownership matching Sol | 15/16 → **16/16** | 7/16 → **9/16** |
| Role | 7/8 → **8/8** | 1/8 → **3/8** |
| Evidence support | 2/8 → **7/8** | 0/8 → **1/8** |
| Ownership | 8/8 → **8/8** | 6/8 → **6/8** |
| Tool responsibility | 8/8 → **8/8** | 8/8 → **8/8** |
| Coherent native tuples | 3/8 → **7/8** | 7/8 → **6/8** |
| Role/support conflicts | 5 → **1** | 1 → **2** |
| Unknown primary role | 1/8 → **0/8** | 7/8 → **5/8** |
| Baseline, all axes | 11/16 → **15/16** | 7/16 → **8/16** |
| Retrieval, all axes | 14/16 → **16/16** | 8/16 → **10/16** |

Jev gained six agreements and lost none; Luna gained three and lost none.
Luna's greater role resolution also created a new role/support contradiction.
Unknown ownership/tool agreement is not proof of absence or successful positive
fact discovery. Ordinary conversational Luna was not tested.

## What changed

Each native question received the exact existing Sol semantic-guidance paragraph
and its original four-axis category catalog. Code, source views, accepted-fact
placeholders, retrieval, models, endpoints and order stayed unchanged. See the
[frozen audit](../2026-10-18-semantic-instruction-parity-preparation-v1/instruction-audit.json)
and [predeclared design](../../semantic-instruction-parity-v1.md).

**Sol was not rerun.** Its original 24 annotations and eight-view consensus are
reused with their unchanged instructions/rubric, state views and receipt.
Top-line SHA-256: `3f25fe46df4537286501fa39552087020cf7a138dd44e2f1a9603354e6d54e3c`.

Native output remains choice distributions; Sol also supplied explanations and
source quotes. The results show sensitivity to the instruction condition, not
which particular clause caused a change. Single historical/current observations
cannot separate instruction effects from stochastic or temporal drift.

## Cost and traceability

Provider-reported usage:

| Provider | Prior input tokens | New input tokens | Prior output | New output |
|---|---:|---:|---:|---:|
| Jev | 27,949 | 39,693 | 1,374 | 1,359 |
| Luna Decision | 23,563 | 34,571 | 0 | 0 |

Input grew by 11,744 tokens (+42.0%) for Jev and 11,008 (+46.7%) for Luna.
No billing receipt or monetary cost is available. Luna reports zero output tokens
despite returning four valid choice distributions; preserve that provider field.
The similar total duration to the earlier 29.122-second run is descriptive, not
a latency improvement claim. There were no native probability-mass warnings here.

- `manifest.json`: exact rendered requests, matching frozen preparation.
- `preparation-binding.json`: reference/budget authorization binding.
- `attempts.jsonl`, `responses.jsonl`: durable transport events and exact successful
  HTTP JSON bytes, captured as base64 plus SHA-256.
- `receipt.json`, `execution-binding.json`: transport counters and local producer/
  runtime snapshot, not remote attestation.
- `comparison.json`: strict transport replay, raw-label/coherence results and
  every old → new per-axis change.
- [Diagnosis](diagnosis.md): source example, observations and remaining hypotheses.
- `result-receipt.json`: binds every run file and producer closure after analysis.

No model answer becomes accepted facts; production S/U and H1/H2 eligibility
remain unchanged. The general configurable-runner refactor remains deferred.

**Next bounded task:** minimize the transferred semantic guidance with a
predeclared clause/catalog ablation, checking whether the Jev gain survives with
fewer input tokens. Keep the single residual conflict for review rather than
repairing it or adding an automatic expensive-model fallback.
