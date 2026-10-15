# Refresh retrieval before Jev/Luna context preparation

`prepare_retrieval_context_v1.py` connects the incremental index to a new,
fact-only native request preparation path. The command automatically refreshes
document embeddings, reads the exact current snapshot, encodes the query with
EmbeddingGemma's `CodeRetrieval` prompt, ranks candidates, and freezes identical
context for Jev and Luna in their respective native Choice envelopes.

```text
Git ref -> pinned source scope -> incremental update -> freshness-checked read
                                                       |
query -> local query embedding -> cosine top-k ---------+
                                                       v
                                bounded target + retrieved source candidates
                                                       |
                         global architecture profile + unresolved fact questions
                                                       v
                                  Jev draft / Luna draft + completion receipt
```

## Behavior and authority

- The declared target must be uniquely present in the selected indexed scope.
  Its self-hit is excluded. No-op updates preserve the model state and wire
  bytes: update/cache-hit counters are kept outside model context.
- Context includes exact source spans/hashes/revision and supported helper
  bodies. Code appears once per source view, rather than duplicating the
  embedding renderer text. A helper change is reflected before request assembly.
- Defaults: cosine top-5, 8 KiB retrieved-context budget, 16 KiB total state,
  64 KiB wire. Whole candidates that exceed the budget are omitted and listed
  in diagnostics; code is never silently truncated. Ties sort by document ID.
- Index content identity includes source, encoder profile and verified vectors.
  The actual manifest hash is recorded separately for audit. Different update
  counters cannot masquerade as new model evidence.
- Corruption, failed update, stale read, missing target or a ref that moves
  during preparation aborts the operation. Old results are never a fallback.
- Facts for this new target start unknown. Code source provenance does not
  assert semantic ownership. Intent lookup remains `not_done`; this source-only
  index does not claim that proposal/spec documents were searched.
- Native questions cover role, ordinal evidence support, ownership and tool
  responsibility. They preserve the global SpecificationCore architecture goal.
  There is no model-selected recommendation and no `absent_in_scope` choice:
  ranked retrieval cannot establish absence. Source snippets are evidence data,
  never instructions; cosine scores are not semantic confidence.
- Existing accepted registry facts, formal policy outputs and S/U do not change.
  This is a new evaluation preparation path, not a change to Rust `classify` or
  the historical three-axis native experiments.

## Run locally

Use the repository's embedding environment and existing model snapshot. Apply
host-specific build/cache routing when required; generated stores and bundles
belong outside tracked source files.

```bash
cd evals/jev-classification
../../.venv-embedding/bin/python -m pip install -r requirements-retrieval-context.txt

../../.venv-embedding/bin/python prepare_retrieval_context_v1.py \
  --repo /path/to/SpecGraph --repository-id 0al-spec/SpecGraph --revision HEAD \
  --include 'tools/*.py' --exclude 'tools/experimental/*' \
  --store /path/to/generated/specgraph-main.sqlite \
  --model-path /path/to/snapshots/914f7f89142e33e77833254d9c9b90c3cef7303b \
  --target 'tools/product_workspace_next_moves_support.py::safe_workspace_path' \
  --query 'Find the rule that rejects unsafe workspace paths' \
  --top-k 5 --output /path/to/generated/new-context-preparation
```

The output directory must be new and its parent must exist. `packet.json` contains
the bound state, fact plan, retrieval diagnostics and index refresh report.
`jev-coreinfra.json` and `luna-decision-coreinfra.json` are request-body drafts.
`preparation-receipt.json` is written last; `verify_bundle` checks completeness,
hashes, state binding and equality with both provider projections. A partial
directory without this receipt is not a completed preparation. No credentials
are read, no model is downloaded, and no hosted request is sent by this command.

The four-question fact projection is **not** the rich proposal response schema:
native Choice cannot supply its source locators/rationale. It has no response
adapter yet and is marked `response_adapter_ready=false`. It is not a transport
run manifest and cannot be handed directly to the old three-axis decoder. Before
live evaluation, implement the fact-projection response adapter, freeze the
bounded experiment/reference and obtain its live authorization. Do not fabricate
citations or automatically promote native labels into accepted facts.

## Validation

Nine offline integration tests exercise automatic refresh, supported helper
changes, deletion, stable no-op wire bytes, whole-hit budgeting, stale/error
rejection, a moving ref, malformed query vectors, equal Jev/Luna state and
bundle integrity. Existing index tests continue to cover atomic publication,
rollback and reader isolation. CI runs integration tests without a model.

A local smoke on SpecGraph commit
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`, restricted to
`tools/product_workspace_next_moves_support.py`, reused all **8** document
vectors, encoded **0** new document inputs and encoded one local query. It
returned **5** source candidates with no budget omissions, verified a completed
two-provider draft bundle and made **0** hosted requests. This proves pipeline
wiring on that scope, not useful semantic matches or provider quality.
