# Incremental retrieval index v1

The local retrieval prototype can now refresh its embeddings as committed code
changes. This is a separate mutable index; frozen benchmark packets, vectors and
receipts are never modified. It is an evaluation-layer Python utility, not yet a
Rust CLI command or an automatically installed repository hook.

## Lifecycle and identity

1. Resolve the requested Git ref once to a full commit and read blobs from that
   immutable tree. Uncommitted edits are deliberately outside this v1 scope.
2. Reconstruct source documents and the supported local helper context.
3. Look up vectors by the hash of the **exact model input and encoder profile**.
   The profile includes model/revision, actual local model-file content digest,
   dimensions, document prompt, normalization, dtype, device and runtime versions.
4. Encode missing inputs in batches of four. Publish the new active manifest in
   the same SQLite transaction as its new vectors. Failure rolls everything back.
5. Before consuming results, require the desired source snapshot and profile via
   `read_current`. A different commit, scope, extractor or profile is stale and
   cannot silently supply source candidates.

The active manifest binds file/blob hashes, paths, symbols, spans, helper bodies,
commit/tree, include/exclude scope, extraction identity and document/vector keys.
Checksum/dimension/finiteness/normalization checks reject damaged cached vectors.
A digest establishes content identity, not semantic correctness or authorization.

| Change | Effect |
|---|---|
| No changes | Zero encoder calls; all vectors reused |
| Commit or line numbers only | Provenance refresh; unchanged input vectors reused |
| Function body | Re-encode that representation |
| Supported local predicate helper | Re-encode the helper and every indexed wrapper containing its body |
| Added declaration | Encode its new input |
| Deleted declaration | Remove from active membership; never return as a current hit |
| Rename | New locator/title input; old membership removed |
| Model files, revision, prompt or runtime changes | Separate cache namespace; re-encode |
| Parse failure, truncation, encoder failure | No publication; previous snapshot remains intact |

Deleted vectors remain in the cache for an explicit historical rebuild. Search
consumers read **active membership only**, never the entire cache. One SQLite
transaction serializes writers; readers see one complete snapshot. A long encode
may make a second writer time out rather than publish a partial index. Use a
separate store per concurrently served branch/context. There is no monotonic
commit requirement: an explicit historical revision is a legitimate rebuild,
and the read boundary still requires that exact revision.

## Commands

Use the existing environment from `requirements-embeddinggemma.txt` and the
already downloaded pinned model snapshot. There is no model download, hosted
request, background inference, or implicit installation. `plan` and `check`
hash local model files and read package versions but do not load the model.
`update` loads it lazily only when missing vectors exist.

```bash
cd evals/jev-classification
# Set these to existing local paths; keep generated stores outside tracked files.
SPECGRAPH_REPO=/path/to/SpecGraph
EMBEDDING_SNAPSHOT=/path/to/snapshots/914f7f89142e33e77833254d9c9b90c3cef7303b
RETRIEVAL_STORE=/path/to/generated/specgraph-main.sqlite

../../.venv-embedding/bin/python -m retrieval_index_v1 plan \
  --repo "$SPECGRAPH_REPO" --repository-id 0al-spec/SpecGraph --revision HEAD \
  --include 'tools/*.py' --exclude 'tools/experimental/*' \
  --store "$RETRIEVAL_STORE" --model-path "$EMBEDDING_SNAPSHOT"

# Run update with the same arguments after a merge or before retrieval.
# It computes a fresh manifest each time and encodes only missing inputs.
../../.venv-embedding/bin/python -m retrieval_index_v1 update \
  --repo "$SPECGRAPH_REPO" --repository-id 0al-spec/SpecGraph --revision HEAD \
  --include 'tools/*.py' --exclude 'tools/experimental/*' \
  --store "$RETRIEVAL_STORE" --model-path "$EMBEDDING_SNAPSHOT"

../../.venv-embedding/bin/python -m retrieval_index_v1 check \
  --repo "$SPECGRAPH_REPO" --repository-id 0al-spec/SpecGraph --revision HEAD \
  --include 'tools/*.py' --exclude 'tools/experimental/*' \
  --store "$RETRIEVAL_STORE" --model-path "$EMBEDDING_SNAPSHOT"
```

The destination directory must already exist. `check` returns exit 2 for an
absent, stale or corrupt index. Source/configuration errors fail the command;
they do not make old results current. Device defaults to `mps`; `cpu` and `cuda`
are explicit alternatives. Runtime/device changes intentionally invalidate reuse.
On hosts with build-cache routing requirements, apply those environment settings
to the commands; no host-specific paths are embedded in the project.

For a consumer, construct `snapshot(...)` and the expected encoder profile,
optionally `update(...)`, then call `read_current(...)`. Do not select rows from
the cache directly or treat `plan` as a published index. Source-query changes
need new query vectors; this store contains document vectors only.

## Scope and evidence

The index v1 now uses source-snapshot selector **v2**: top-level functions and
direct typed or untyped `PredicateSpec` assignments spanning 4–100 lines, with one unambiguous
same-module predicate-function hop. All matching declarations are indexed; there
is no 512-document sample. Include/exclude use Python `fnmatchcase`: `*` matches
slashes, so `tools/*.py` also includes Python files in nested directories.

Classes/methods, other languages, YAML intent documents, imported helpers and
general dependency analysis are **not** covered. Length-filtered declarations
are counted. A source syntax/encoding error is fatal; unsupported selected
symlinks are rejected. Missing query hits cannot prove absent ownership. Source
matching and current vectors do not create accepted facts or change S/U.

Paired-study preparation exposed a confirmed extraction defect: `ast.Assign`
matched `RULE = PredicateSpec(...)` but omitted real declarations such as
`RULE: PredicateSpec[Context] = PredicateSpec(...)`. Selector v2 also handles
`ast.AnnAssign`; its contract and collector digest change, so old active
manifests are stale until an explicit update. Unchanged exact document inputs
can still reuse cached vectors. A regression checks typed-wrapper extraction,
helper-body inclusion and helper-change invalidation. This does not add class,
import-alias or imported-helper coverage, nor rewrite historical frozen corpora.

Regression tests use a deterministic test encoder and temporary Git histories,
not model quality labels. They cover no-op reuse, helper invalidation, source
line shifts, deletion/rename/restore, stale revision/scope/profile rejection,
model/runtime identity changes, rollback after a later failed batch, malformed
vectors, checksum corruption, incomplete manifests, reader isolation during an
update, invalid source and repository separation.

Local smoke verification used the actual pinned EmbeddingGemma on
`tools/product_workspace_next_moves_support.py` at SpecGraph commit
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`: the first update encoded 8
documents; the second reused all 8 with zero encoder calls; `check` returned
`current`. This validates the local adapter/cache path on that scope, not
retrieval quality or full-project source coverage. Model downloads and hosted
requests were disabled. The mutable smoke database stays outside the repository.

PR70 review found that a structurally corrupt SQLite file bypassed the original
`ValueError` handler. `check` now also maps SQLite database errors to
`unavailable`/exit 2. A CLI regression with non-SQLite bytes reproduces the
original failure and verifies the documented automation contract.

The [context preparation entry point](retrieval-context-refresh-v1.md) now calls
this update/read boundary automatically before assembling new Jev/Luna draft
requests. Automatic execution in SpecGraph CI still requires selecting a runner
with the local model and persistent store; CI runs offline regression tests only.
