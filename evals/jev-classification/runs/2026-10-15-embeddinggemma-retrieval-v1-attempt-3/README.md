# EmbeddingGemma 2: local historical retrieval result

**Status:** completed local inference and offline vector/ranking replay.
No hosted inference, ownership acceptance or production metric changes.
See the [protocol and reproduction](../../embeddinggemma-retrieval-pilot-v1.md).

## Scope

15 historical SpecGraph before/after pairs, 30 queries (code + authored English
intent), 45 indexed excerpts including 30 distractors. A correct hit means the
designated historical counterpart. This is not independent semantic gold or an
exhaustive judgement of relevance; some other retrieved documents are useful.
The eight lifecycle pairs are correlated. No query/prompt/ranking tuning was
performed after observing this run.

## Retrieval

| Method | Code first /15 | Code top-5 /15 | Code MRR | Intent first /15 | Intent top-5 /15 | Intent MRR |
|---|---:|---:|---:|---:|---:|---:|
| BM25 | 14 | 14 | .940 | 11 | 15 | .844 |
| Dense 768d | 6 | 14 | .628 | 13 | 15 | .933 |
| Dense 256d | 6 | 14 | .644 | 12 | 15 | .900 |
| BM25 + dense 768d, RRF | 11 | 14 | .841 | 14 | 15 | .967 |
| BM25 + dense 256d, RRF | 12 | 14 | .874 | 14 | 15 | .967 |

All five methods put all 15 counterparts in the first ten for both query modes.
Top-5 intent recall is already saturated by BM25 in this small index. Embeddings
improve the ordering of intent results here; they do not demonstrate higher
top-5 recall or a general replacement for lexical search.

### Family breakdown: first result

| Method | Lifecycle code /8 | Other code /7 | Lifecycle intent /8 | Other intent /7 |
|---|---:|---:|---:|---:|
| BM25 | 8 | 6 | 4 | 7 |
| Dense 768d | 0 | 6 | 6 | 7 |
| Dense 256d | 0 | 6 | 5 | 7 |
| Hybrid 768d | 5 | 6 | 7 | 7 |
| Hybrid 256d | 6 | 6 | 7 | 7 |

The benefit on intent and loss on code are concentrated in lifecycle. The other
seven families do not establish an incremental intent benefit: BM25 already
finds every counterpart first. Reporting only the overall result would hide this.

## What went wrong, with code

### A broad dispatcher outranks the individual decision

Dense search ranks `sg-055` first for all eight lifecycle **code** queries. This
document is a broad lifecycle dispatcher and mentions many requested concepts:

```python
if _review_status(artifacts) in {"open", "merged"}:
    return "git_review_active"
if _promotion_request_state(artifacts) == "requested":
    return "promotion_requested"
if _candidate_approval_decision_state(artifacts) == "materialized":
    return "approval_materialized"
```

The desired individual `_SPEC` ranks 2–5 instead. The broad dispatcher is
related, but is not the designated extracted decision. This is confirmed ranking
behavior; “the model prefers overall topic similarity” is an explanatory
hypothesis, not access to the model's internal reasoning. BM25 preserves exact
identifier discrimination much better on these before/after pairs.

### The indexed declaration omits the actual predicate body

`sg-027-code` asks with a 436-token function checking pre-SIB readiness, findings,
action counts and context counts. Its target `sg-028` is only a declaration:

```python
CLEAN_PRE_SIB_NOOP_PASSTHROUGH = PredicateSpec(
    _is_clean_pre_sib_noop_passthrough,
    name="repaired_handoff.clean_pre_sib_noop_passthrough",
)
```

The helper's implementation is absent from the indexed document. The target
ranks BM25=10, dense768=7, dense256=8, both hybrids=9. Every method misses top-5
on this code query. The short intent query retrieves it first under every method.
Missing implementation context is a concrete corpus boundary; whether including
the helper improves retrieval requires a new controlled run. Do not relabel this
miss as success or modify the frozen corpus in place.

### Related lifecycle states are not interchangeable

The hybrid intent miss is `sg-009-intent`: promotion-request state. The first
result is promotion-execution (`sg-012`), and the exact request rule (`sg-010`)
is second. Both discuss requests, errors and lifecycle progress. A semantic
adjudicator still needs the requested decision boundary before recommending
reuse. Similarity must not bypass the acceptance contract.

## Dimensions, time and memory

Machine observed: Apple M4 Pro, 24 GiB unified memory, macOS 27, Python 3.10.19;
Torch MPS, float32, 271,002,624 active model parameters. Vision/audio configs were
asserted disabled. Maximum input length was 1000 tokens; no truncation.

| Measurement | Observed |
|---|---:|
| Model load from cached snapshot | 1.93 s |
| Encode 45 documents, batch size 4 | 4.58 s |
| Code query median / p95, 15 samples | 161 / 261 ms |
| Intent query median / p95, 15 samples | 29 / 50 ms |
| Mean across all 30 query encodes | 88 ms |
| Score all queries with all five methods | 18 ms |
| Full successful process, including source check/imports/warm-up | 25.95 s |
| Process peak RSS | 1.90 GiB |
| MPS active allocation at end | 1.01 GiB |
| MPS driver allocation at end | 2.33 GiB |

Query timing includes query encoding and conversion to NumPy. It is a single
small sequential run with one warm-up, not steady-state throughput or an SLA;
shorter intent text and shape warm-up affect the comparison. The initial snapshot
download took about 146 seconds in the first failed attempt (terminal timing).
The successful attempt used the cache (receipt: 0.0035 seconds), so it must not
be presented as a cold download benchmark. RSS and MPS allocations overlap on
unified memory: **do not sum them**, and do not call end snapshots GPU peaks.

At float32, 45 raw document vectors occupy 135 KiB in 768d or 45 KiB in 256d,
excluding metadata/index overhead. The 256d hybrid retains the same intent
top-1/top-5 result here; dense alone loses one intent top-1 (`sg-013`, rank 1→2).
The 256d hybrid gains one code top-1. These are small correlated observations,
not evidence that dimensionality reduction universally improves ranking.
Truncation reduces vector storage threefold; it does **not** reduce encoder cost.

## Evidence and verification

- `packet.json`: exact model revision, inputs, pair references and source hashes.
- `embeddings.npz`: saved float32 vectors for deterministic offline scoring.
- `scores.json`: every query's complete 45-document ordering for all methods.
- `receipt.json`: producer/vector/packet hashes, runtime measurements and model config.
- `packages.json`: observed environment versions; `source-verification.txt`: pinned
  Git corpus verification. Input source code is Apache-2.0, see the corpus license.
- Six offline tests passed with warnings as errors: preparation isolation,
  complete ranking/mode aggregation, MRL renormalization, malformed vectors,
  stable ties and tampered replay rejection. Saved-vector replay passed.
- `pip check` passed. GitHub CI adds a ranking-only replay job; local checks do
  not assert that hosted CI has already passed.

Attempts [1](../2026-10-15-embeddinggemma-retrieval-v1/failure.json) and
[2](../2026-10-15-embeddinggemma-retrieval-v1-attempt-2/failure.json) failed during
processor construction, before embeddings. They are retained with the same
input packet and producer; Pillow/Torchvision dependencies were then added.
The successful run is attempt 3, not a selected rerun based on retrieval quality.

## Decision and next experiment

EmbeddingGemma 2 is locally operational and promising for intent-to-code ordering.
Keep BM25 as a first-class channel. Do not replace raw-code search with dense-only
retrieval or enable automatic Specification reuse based on this evidence.

Next: a new, source-bound corpus variant expanding only alias-like Specification
declarations to their local predicate bodies, and a larger current SpecGraph index
with previously unused queries. Compare the old and expanded representations,
retaining lexical/dense/hybrid results and the same acceptance boundary. Include
Russian intent queries separately. Choose a production configuration only after
that broader check; 256d is a reasonable next experimental candidate, not a
proven universal optimum.
