# Helper context and larger bilingual index: observed results

**Completed local inference.** The [frozen protocol](../../retrieval-helper-pilot-v1.md)
and its SHA-256 are retained. No hosted inference, ownership decisions or S/U changes.

## H1 supported on the known failure

Exactly one historical document changed: `sg-028`, the declaration of
`CLEAN_PRE_SIB_NOOP_PASSTHROUGH`. Its unique local predicate body was appended
from the same pinned Git file. All 30 query vectors and 45 original document
vectors were reused. The query, document IDs, other texts and expected answer
were unchanged. The named predicate checks readiness, findings, action counts
and required context; that content had been absent from the declaration.

| Method | `sg-027-code` rank before | Rank with helper | Code top-5 /15 before → after |
|---|---:|---:|---:|
| BM25 | 10 | 1 | 14 → 15 |
| Dense 768d | 7 | 1 | 14 → 15 |
| Dense 256d | 8 | 1 | 14 → 15 |
| Hybrid 768d | 9 | 1 | 14 → 15 |
| Hybrid 256d | 9 | 1 | 14 → 15 |

No other designated-target rank changed in this comparison. The prior lifecycle
dispatcher failures remain. This supports the missing-body explanation for this
specific failure and does not establish universal helper-expansion benefit.

## Larger source index and H2 failure

SpecGraph `main` is pinned at `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.
The builder considered 125 Python files under `tools/` and 2,431 eligible
declarations; 512 were sampled by stable path/symbol hash and six missing targets
were added, giving **518 indexed documents**. The eight query targets are new to
the prior retrieval packet; the author read their implementations. This is a
purposive development evaluation, not a blind holdout or exhaustive repository
index. Other relevant implementations are not exhaustively labelled.

No selected current document satisfied the narrow local helper-expansion rule.
Consequently the current `declaration` and `with_helpers` arms are identical and
do **not** provide additional evidence about helper expansion.

Each target has one authored English and one Russian intent query. No code-query
exact copies are used for this new set.

| Method, frozen v1 | English first /8 | English top-5 /8 | Russian first /8 | Russian top-5 /8 |
|---|---:|---:|---:|---:|
| BM25 | 5 | 7 | 1 | 1 |
| Dense 768d | 8 | 8 | 7 | 8 |
| Dense 256d | 8 | 8 | 6 | 7 |
| Hybrid 768d | 7 | 7 | 3 | 3 |
| Hybrid 256d | 7 | 7 | 2 | 3 |

**H2 fails:** the frozen hybrid256 criterion required top-5 ≥7/8 in both
languages; Russian reached 3/8. Keep this original result even after fixing the
implementation. Dense768 is promising on these eight selected implementations;
8/8 is not a population accuracy estimate.

### Concrete remaining misses

- Russian authorization deserialization (`new-05-ru`): the designated
  `subject_source_write.py::parse_write_authorization` ranks dense768=4,
  dense256=11. The smaller vector first retrieves
  `supervisor.py::load_operator_request_bridge_policy`. Both concern permissions,
  but the requested parsing boundary differs. The 256d trade-off now costs an
  actual top-5/top-10 hit; the earlier tiny pilot did not expose this.
- English workspace path validation (`new-02-en`): dense ranks the exact
  `safe_workspace_path` first; BM25 ranks it 49th and hybrid768 pushes it to ninth.
  Related path/bootstrap utilities outrank it. A nonempty lexical channel can
  still dilute the semantic result; the repair below does not solve all fusion
  quality issues.

## Confirmed implementation failure and bounded repair

The inherited tokenizer used `[a-z]+|[0-9]+`. Six Russian queries became empty;
two retained only `windows` and `staging`. More importantly, v1 gave every document
an RRF vote from the full BM25 ranking even when its BM25 score was zero. Empty
queries therefore added a stable but arbitrary alphabetical ranking to dense
results. This is a confirmed scoring defect, not evidence that Gemma fails at
Russian understanding.

The [separate v2 replay](../2026-10-15-retrieval-fusion-replay-v2/README.md) uses
the **same saved vectors**, independently varies Unicode tokenization and removal
of nonpositive BM25 contributions, and adds regression tests. It makes no model
calls. Unicode alone leaves Russian top-5 unchanged; removing unsupported lexical
votes raises hybrid768 to 8/8 and hybrid256 to 7/8. These are post-failure repair
results, not a retroactive H2 pass or independent validation.

## Runtime and storage

Same local M4 Pro host and float32/MPS text/code model as the predecessor. Existing
weights were loaded offline; no new model download. The 553 unique document
representations reuse 45 old vectors and require **508 new document encodes**;
all 30 historical queries are reused and 16 new queries encoded. The current
518-document index overlaps some historical text, which explains deduplication.

| Measurement | Observed |
|---|---:|
| Encode 508 new document representations | 26.03 s |
| English query median / p95, 8 samples | 28 / 84 ms |
| Russian query median / p95, 8 samples | 29 / 129 ms |
| Timed execution body | 37.72 s |
| Maximum encoded input length | 1,154 tokens |
| Process peak RSS | 1.68 GiB |
| MPS driver allocation at end | 3.97 GiB |

The execution timer begins after source reconstruction and predecessor replay;
it is not end-to-end CLI latency. These short sequential measurements are not an
SLA. RSS and MPS snapshots overlap on unified memory and must not be summed.
The lower RSS than the predecessor is not evidence of lower total memory usage.

Raw current-index document vectors require 1,591,296 bytes at 768d or 530,432
bytes at 256d, excluding metadata/index overhead. Dimensional truncation saves
storage, not model inference time. Quality loss on `new-05-ru` argues for retaining
768d as the next semantic-search baseline.

## Verification and local cache routing

- Full packet reconstructed from pinned Git source before inference; original
  SpecGraph checkout and its unrelated local file were preserved.
- Seven helper/ranking tests cover exact spans, rebinding/local scopes, partial
  fragments, tampered source, paired arms, malformed vectors and predecessor parity.
- Four additional fusion regression tests cover Unicode and unsupported votes.
- Original four-view replay and corrected four-arm replay reproduce saved results.
- TB5 preflight verified the expected mounted UUID. Python bytecode and temporary
  runtime files were routed to that checkout's external build directory. The
  existing virtual environment and read-only model snapshot stay in their original
  locations; this task did not migrate or delete caches.
- CI replays only stored vectors. Its completion is reported separately from
  these local checks.

Artifacts: `packet.json`, `embeddings.npz`, `scores.json`, `receipt.json`.
All source excerpts retain the existing SpecGraph Apache-2.0 corpus notice.

## Next bounded task

Keep 768d dense as the semantic baseline and lexical search as a separate useful
channel. Test evidence-aware fusion on new queries, particularly ambiguous shared
words such as Windows/windows, and evaluate cross-module predicate resolution in
a separately versioned source packet. Do not select more fusion weights using
these eight known answers and call the result generalization.
