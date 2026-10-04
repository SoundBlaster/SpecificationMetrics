# Registered rule reuse · Python v1

`check-rule-reuse` answers a bounded question: did this Git change introduce a
procedural copy of a project-registered Specification rule? It does not claim to
recognize all semantically equivalent code or convert every conditional into a
Specification. Primary S/U counters are unchanged.

## Catalog and evidence

A TOML catalog (`schema_version = 1`) registers each rule's stable `id`,
`bounded_context`, relative `paths`, `canonical_path`, `canonical_symbol` and
`canonical_digest`. `fingerprint-rule` reads the named declaration from a Git
commit and returns its BLAKE3 digest and source. Python v1 requires a direct
`PredicateSpec` import from `specification_core`, an assigned `PredicateSpec`
call and one inline lambda with one plain context parameter. That parameter is
derived from the AST. Only the canonical declaration is excluded from matching;
other code in its file remains eligible.

A rule can register historical `templates`: `id`, `expression`,
`renameable_identifiers`, and a GitHub `source_url`. Review must establish that
these expressions implement the registered rule over the intended facts. A URL
alone does not prove equivalence. Prefer full commit permalinks. Paths establish
an explicit analysis boundary; v1 does not infer bounded contexts. Register
production paths only, keeping fixtures and examples outside those scopes.

The SpecGraph pilot catalog is `configs/specgraph-rule-catalog.toml`. It covers
`tools/` for `subject_publication.workspace_allocation` and registers the original
six-condition guard from PR #762. Enlarging its scope is a review decision.

## Matching and delta

The analyzer reads committed base/head snapshots without checking out or
executing project code. It visits predicates in `if`, `elif`, `while`, `assert`,
`require` first arguments and lambda bodies. It does not cover arbitrary boolean
assignments, comprehensions, match guards, generated code, Rust or Swift yet.
A `complete` result means this declared construct/path scope was parsed, not
that every decision in the project was examined.

Exact matches preserve operator order, fields, constants and calls. Formatting,
redundant parentheses and ordinary unescaped single/double quote differences are
ignored. Only explicitly registered identifier binders may be renamed, with a
consistent bijection. Reordered checks are not exact: short-circuit behavior can
matter. A compound predicate wrapping a registered condition is review-only.

Feature overlap produces `near_match` suggestions, never a blocking count.
Direct or aliased explicit imports followed by a direct `.is_satisfied_by(...)`
call (optionally negated) are counted as static reuse. Context assembly is not a
copy. Nested spec calls do not exempt a compound predicate. Whole-file assignment
and parameter shadowing prevent reuse recognition. Module aliases, re-exports,
dynamic imports and runtime identity resolution are unsupported in this adapter;
`reused_specifications` is a static observation, not runtime proof.

For each changed file, old matches are consumed by rule/kind/template identity,
so line shifts and registered binder renaming are not new copies. Git-detected
file renames preserve this baseline; copies into the scope are new. A move Git
does not identify as a rename can appear as a removal/addition and requires
review. Counts describe changed files, not a repository-wide inventory.

## Gate and storage

```sh
specification-metrics fingerprint-rule /path/to/repo \
  --path tools/policy_spec.py --symbol POLICY --at HEAD
specification-metrics check-rule-reuse /path/to/repo \
  --catalog reviewed-rules.toml --base BASE_SHA --head HEAD_SHA \
  --output report.json --store metrics.sqlite --strict
specification-metrics rule-reuse-history --store metrics.sqlite
```

Without `--strict`, a report is informational. With it, newly introduced exact
`new_reimplementations > 0` or an `incomplete` parse result returns a nonzero
exit code **after** writing the report and optional snapshot. Missing/malformed
catalogs, stale canonical digests, unreadable Git sources and invalid revisions
are errors; callers must not reinterpret absence of a report as zero.

SQLite stores idempotent snapshots in `rule_reuse_snapshots`, separate from the
primary metrics history, with timestamp, report, Git revisions, catalog digest
and analyzer version. No baseline total is subtracted to excuse new copies in
another changed file. Near-match suggestions are available in the JSON report.

CI should supply a catalog from its trusted base revision, and pin the analyzer
commit. A changed head catalog cannot quietly disable its own gate. Catalog
migration needs explicit reviewed rollout because changed canonical digests fail
closed under the old catalog. First-time activation without a base catalog must
be visibly labeled bootstrap/report-only, not described as an enforcing gate.

## Optional Jev

New near matches export `semantic_review_requests` with the exact candidate,
registered declaration and bounded context. The provider can be invoked with
`--classify-near-matches --allow-hosted-classification`, `--endpoint`, `--model`
and `--api-key-env` (default `JEV_API_KEY`). Source is sent only with explicit
hosted opt-in; the default scan uses no API key and makes no network requests.

The TypeSafe Choice contract is `same_rule / different_rule / needs_review`.
Provider-reported probabilities and confidence are not calibrated quality
measurements. The request is capped at 24 KiB, response at 1 MiB, redirects and
retries are disabled, and a bounded timeout is required. Errors/malformed output
become `needs_review`. Reports retain requested/returned model when available,
prompt version/digest and input digest; model revision and rationale are
unavailable, so responses are not reusable semantic cache entries. No provider
response changes the blocking exact-match count or authorizes a rewrite.

## Pilot evidence

Against SpecGraph commits `9b285a2e018331460c1a6bee46a697b24a26d3fb` →
`5ddd1c0b62241681c2ced4073a3402a68c10e385`, the registered scope reports
`before_reimplementations = 1`, `after_reimplementations = 0`,
`new_reimplementations = 0`, `reused_specifications = 1`, `files_checked = 4`,
`status = complete`. This validates the original guard's disappearance and the
static call recognition. Unit/CLI tests separately introduce exact/renamed copies,
changed literals/orders, aliases, parse failures, stale catalogs, renames and
mocked provider responses. No live Jev quality claim follows from mock tests.
