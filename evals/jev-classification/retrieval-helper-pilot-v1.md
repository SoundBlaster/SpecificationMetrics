# Helper-context and bilingual retrieval pilot v1

## Frozen questions, before inference

1. **H1, controlled representation diagnostic:** in the historical 45-document
   index, adding source-bound local predicate bodies brings `sg-027-code` into
   dense768 top-5 and improves its rank relative to the unchanged declaration
   index. Also report every method, changed target, and aggregate regression.
   One repaired known failure is not generalization evidence.
2. **H2, next-pilot engineering criterion:** in a larger current-source sample,
   hybrid256 retrieves at least 7/8 designated implementations in top-5 for
   English **and** Russian intent queries. Compare BM25/dense/hybrid and both
   dimensions. This small, chosen threshold is for deciding the next experiment,
   not production readiness or statistical proof of language parity.

## Two separate comparisons

Historical: reuse exactly the predecessor's 30 query vectors and 45 unchanged
document vectors. Encode only changed document representations. Both arms have
identical document identities, query text and target locators. BM25 also sees the
expanded text, so its corpus statistics can change. A test requires the generic
ranker to reproduce the predecessor's full ranks and top ten.

Current: pin SpecGraph `main` at
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`. Enumerate top-level Python functions
and simple named assignments containing `PredicateSpec` under `tools/`, limited
to 4–100 lines. Select the first 512 by SHA-256 of path/symbol; add any missing
targets from eight source-read examples. The cap and forced inclusion bound cost
and guarantee that the retrieval question has an indexed answer. This is not a
repository coverage estimate: long functions, classes/methods, nested definitions,
other paths and unsampled declarations are outside the index.

The eight target locators must not appear among the previous pilot's query or
document locators. Each has one authored English query and one Russian query
written from the source before observing retrieval. They are new to this retrieval
benchmark, not independent holdout annotations or unseen by the author. Relevant
alternatives and duplicates have not been exhaustively adjudicated. Exact-source
hit rate can penalize a useful equivalent result; report representative misses.

## Helper boundary

Parse the complete pinned Python module, not a potentially incomplete excerpt.
Only calls inside module-level assignments and within the excerpt's line span
are eligible. Recognize the syntax `PredicateSpec(local_function)` and append the
unique same-module function's exact source lines. Reject rebindings/imports and
conditional alternative definitions. Do not descend into lambda scopes, resolve
cross-module references, follow helper chains, execute code or infer semantic
equivalence. The PredicateSpec spelling is a syntactic selector, not proof that
it resolves to a particular library's constructor.

Every document carries revision/path/symbol/line ranges, full-file hash and
excerpt hash; added helpers carry their own ranges and hashes. Reconstruct the
entire packet from Git before live execution. The working checkout is not edited.

## Model, cost and authority

Use the same pinned `google/embeddinggemma-2` revision, text/code-only float32 MPS
configuration, CodeRetrieval query prefix, explicit document title/text format,
768/256 normalization and RRF constant 60 as the predecessor. Deduplicate document
representations; reuse unchanged historical vectors and all historical queries.
One warm-up and one pass over missing representations and 16 new queries. Reject
oversized inputs rather than truncating. No retries based on retrieval quality.

Use the existing local model snapshot in offline mode; no model download, paid
API or hosted inference. Local Python bytecode goes to the verified TB5 checkout
directory; existing environments and model weights remain in place and are not
migrated. Tracked evidence files remain in the source repository.

All results are `ranked_candidates`. No semantic approval, absence claim,
automatic Specification reuse or S/U change. The large index remains explicitly
non-exhaustive. Source excerpts retain SpecGraph's Apache-2.0 provenance and the
existing `corpus/LICENSE.SpecGraph` notice.

## Verification and reporting

Save exact inputs, vectors, ranks/top-ten results, execution/producer/protocol
hashes and runtime receipt. CI recomputes rankings without model dependencies,
Git source access or network inference; it verifies stored evidence integrity,
not source availability. `--check-source --repo /path/to/SpecGraph` independently
reconstructs the packet from pinned Git objects locally.

Report H1/H2 literally, per-language counts, dimension differences, index encoding
time, query latency and RSS/MPS snapshots. The run is a small sequential sample,
not an SLA. MPS allocations overlap with RSS on unified memory; do not sum them.
Keep an outcome report separate so this protocol stays frozen during/after inference.

## Preparation findings

- Initial preparation parsed an indented `require(...)` excerpt as a standalone
  program and raised `IndentationError`. The source itself was valid. Fix: resolve
  calls from the full-module AST constrained by the exact source span. The test
  `test_indented_partial_excerpt_uses_complete_module_ast` reproduces this boundary.
- `_check_transition` and then `parse_write_request` were rejected because they
  already occurred in the old corpus. Both were replaced before inference with
  `parse_write_authorization`; the target-overlap guard remains active. This is
  corpus preparation, not reranking or relabelling an observed result.
