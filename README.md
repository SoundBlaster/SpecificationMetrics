# SpecificationMetrics

A Rust CLI for measuring Specification adoption in Python, Swift, and Rust.

Python collection/evaluation tools use **Python 3.11+**, with 3.11 selected in
`.python-version` and CI. Jev4Mellea 0.9.0 and the categorical SDK dependencies are
pinned in [the current evaluation lock](evals/jev-classification/requirements-evaluation.lock).
Use the repository `.venv` for local Python commands. Historical benchmark
artifacts retain their actual recorded Python and SDK versions; their separate
0.8.0 environment remains pinned for exact replay. See the
[upgrade and compatibility checks](docs/jev4mellea-0.9-upgrade.md).
The [categorical review bridge](docs/categorical-review-bridge-v1.md) connects
native Jev batches and categorical results to the existing semantic review route.
It scans the current source snapshot and reports the live ratio of distinct
Specification definitions to remaining control-flow opportunities.

The optional `classify` command uses Jev Choice to suggest whether scanner
candidates belong in the Specification opportunity denominator and separately
what kind of logic they express. Suggestions never update reviewed registry
entries or S/U counts. See the [classification contract](docs/candidate-classification-contract.md)
for privacy boundaries, provenance, and review semantics.

The experimental offline `extract-decision-target` command addresses an exact
Python expression separately from its enclosing context. It does not change
discovery, classification or S/U. See the [decision-target contract](docs/decision-target-contract.md).

The proposed [formal analysis roadmap](docs/formal-analysis-roadmap.md) describes
decision contracts, structural evidence, transformation tests and a bounded
predicate-equivalence pilot before extending semantic review or PR gates.

The proposed [classification backend roadmap](docs/classification-backends-roadmap.md)
adds configurable general LLM API and Codex CLI execution alongside System One,
with **Ollama** and **LM Studio** planned as local model-server backends.
Backend comparisons will follow the proposed
[prompt-parity protocol](docs/classification-prompt-parity.md), separating model
configuration effects from differences in semantic instructions.
The experimental [categorical backend contract](docs/categorical-backend-contract-v1.md)
adds offline `prepare-classification` and separately authorized
`run-classification` for a bounded Codex CLI packet, without changing the
existing scanner classification or S/U authority.

## Unified collection

`collect` uses a TOML config to collect **S, U and S/U first**, then optional
LOC/CC/Cog and clone observations from the same captured application sources.
It exports JSON, saves idempotent SQLite history and compares compatible
snapshots without inventing a combined quality score. The scanner works without
external metric tools; missing opt-in tools produce explicit diagnostics.

```bash
cargo run --locked -- collect --config configs/self.toml --output metrics/self.json
cargo run --locked -- collect --config configs/specgraph.toml \
  --output metrics/specgraph.json --store metrics/specgraph.sqlite
cargo run --locked -- collection-history --store metrics/specgraph.sqlite
```

For a PR report with source links, add `--candidate-locations` to both
`collect` runs, then use `compare before.json after.json --github-markdown OWNER/REPO`.
The JSON comparison retains every added, removed and ambiguous location.
When Python complexity details are available, the same Markdown includes
metric-changed and unmatched function hotspots with before/after values.
Unestablished correspondence is explicit; a possible move is never assigned a zero baseline.

See the [collection contract](docs/collection-contract.md) for source exclusions,
external-tool setup, before/after comparisons, statuses and strict exit codes.

## Semantic candidate suggestions

The experimental [incremental retrieval index](evals/jev-classification/incremental-retrieval-index-v1.md)
refreshes local EmbeddingGemma document vectors from committed Python sources.
It reuses unchanged inputs, removes deleted active entries, follows supported
local predicate helpers, and rejects stale revision/profile reads. It is separate
from the Rust classifier and from immutable benchmark snapshots.
The [context preparation entry point](evals/jev-classification/retrieval-context-refresh-v1.md)
refreshes that index before assembling source-bound Jev/Luna draft requests.
The [native fact-response adapter](evals/jev-classification/retrieval-fact-response-adapter-v1.md)
checks saved four-question responses and emits unaccepted proposals or explicit
review/rejection diagnostics.
The [paired retrieval study](evals/jev-classification/paired-retrieval-study-v1.md)
freezes matching evidence views and validates local transport attribution before
semantic comparison. [Independent view annotations](evals/jev-classification/runs/2026-10-18-paired-blind-reference-v1/README.md)
are available as diagnostics. Their actual annotator allocation is unbalanced;
the mandatory design qualification rejects them as an H1/H2 paired reference.
Live results remain pending.
The [scoring contract](evals/jev-classification/paired-retrieval-scoring-v1.md)
fixes denominators, abstention/error handling and qualification prerequisites;
operational H3 results remain separate from semantic H1/H2 claims.

```bash
export JEV_API_KEY='…'
cargo run -- scan ../SpecGraph --include src --output /tmp/specgraph-scan.json
cargo run -- classify \
  --scan /tmp/specgraph-scan.json \
  --profile configs/specificationcore-classification.toml \
  --allow-hosted-classification \
  --output /tmp/specgraph-classifications.json
```

The command revalidates the scan against current sources, omits candidates
inside recognized Specifications, and sends bounded candidate contexts to the
hosted Jev API only after the explicit opt-in flag is supplied. It makes no
automatic retries. The report is informational and keeps the opportunity and
concern-kind classifications on separate axes. Set `--min-confidence` only
after calibrating the Jev-specific threshold against reviewed examples.

## Specification application diagnostics

```sh
cargo run -- application-sites ../SpecGraph \
  --scope-manifest /path/to/source-roles.toml --output /tmp/applications.json
```

The advisory Python-if profile distinguishes confirmed direct `PredicateSpec`
applications, mixed expressions, and unresolved `.is_satisfied_by` calls.
It preserves raw S/U. Source digests, candidate anchors and factory locations
make the results inspectable. See the [contract and supported subset](docs/application-sites-contract.md).

For synchronous `FirstMatch.decide`, including assignments and arguments:

```sh
cargo run -- application-sites ../SpecGraph/tools --profile python-decisions-v1 \
  --scope-manifest /path/to/tools-source-roles.toml --output /tmp/decisions.json
```

This separate opt-in profile records direct result consumption, embedded
processing and unresolved calls. See its [contract](docs/decision-applications-contract.md)
and [frozen SpecGraph pilot](docs/firstmatch-application-pilot.md).

`--profile python-decision-flow-v1` additionally traces an immediately bound
result to a subsequent if-condition within a conservative straight-line function
or loop body, including comparisons with verified same-module enum members.
Reassignment and unsupported effects stop analysis explicitly. See the
[flow contract and pilot](docs/decision-flow-contract.md). It does not change U.

`--profile python-decision-flow-alias-v1` follows supported local name copies
through the next condition, with explicit bounds and barriers. Its evidence is
static and advisory: it does not establish reachability or change U. See the
[local-alias contract](docs/local-alias-flow-contract.md). The earlier flow
profile continues to report alias propagation as unresolved.

## Live metric

For each source snapshot, calculate `S / U`: `S` is the number of distinct
application-defined Specifications, counted once per definition rather than
once per use; `U` is the number of current decision opportunities that remain
outside Specification. Both counts are recomputed from the same source scope.
The ratio can grow beyond 1 and is not a percentage or a score capped at 100.
For example, `0 / 10,000` becomes `1 / 9,999` after one conversion. A large
ratio is a valid observation; questions about Specification reuse, coupling,
and cohesion belong to separate metrics.

If `U` reaches zero, report `S` and `U` plus a `complete` state instead of
serializing infinity as a JSON number. If both counts are zero, report
`not_applicable`. Changes in project scope, new decisions, and deleted code may
move the ratio in either direction; that is part of a live project-health
measurement. Store dated snapshots and their source revision in SQLite to
explain the trajectory, without freezing a historical denominator.

Counting rule v10 recognizes direct Specification/DecisionSpec conformances or
implementations and source sites that construct `PredicateSpec` or `FirstMatch`
variants. Python also counts a subscripted call such as `PredicateSpec[ContextFacts](...)`
when the constructor resolves to `specification_core.PredicateSpec` in the
selected scope. It counts a factory site once, regardless of runtime calls. Decisions
inside recognized definitions or factories do not contribute to `U`. Reviewed
`excluded` entries in an optional registry remove only *currently matching*
candidates. Other current candidates contribute to `U`.

Python module-level subclasses are also discovered transitively through
statically resolved bases, including generic bases, aliases and import-based
re-exports. Their class bodies are excluded from `U`, and inheritance is a
runtime use of the base. Rebound or ambiguous bases do not establish coverage.
See the [v9 inheritance audit](docs/python-inheritance-counting-audit.md) for the
SpecGraph reproduction and the distinction between analyzer corrections and
application refactoring gains.

Rule v10 classifies named Python and Rust Specification declarations as `live`,
`dead`, or `unknown`. Resolved runtime uses stay in `S`; a private declaration
without a resolved use leaves `S` only when a source-role manifest explicitly
sets `[liveness] closed_world = true`. Public declarations, unresolved or
ambiguous imports, dynamic lookup, incomplete scans, and Swift liveness remain `unknown` and
therefore stay in `S`. Rust liveness resolves a bounded set of crate/module
paths and runtime constructions, including direct named imports and aliases.
Ambiguous imports, unresolved dynamic trait-object lookup, and macro references
outside known static registries remain `unknown`. Python classes can also opt in
through the typed `__specmetrics_specification__` class variable documented in
the [declaration marker contract](docs/declaration-marker-contract.md). Marker
issues and unknown liveness make the report provisional. The report includes
per-status counts and evidence. Anonymous factory sites remain in `S` as before.

Swift types can opt in by conforming to the exact unqualified
`SpecificationMetricV1` protocol, directly or in a same-file extension. Rust
types can opt in through a local `SpecificationMetricV1` trait and a
`struct`/`enum` implementation. Conventional crate/module paths are resolved;
unmapped ownership stays provisional. Swift liveness remains `unknown`; Rust
uses the conservative resolver described above.

The [counting contract](docs/counting-contract.md) defines the source ownership
boundary and the disjoint reasons for removing a candidate from `U`. For a
whole-repository scan, use a versioned source-role manifest. Only `application`
files contribute to the ratio; unassigned or conflicting files make the report
provisional. Without a manifest or explicit `--include` paths, a directory-root
measurement remains provisional discovery.

This is a syntax-based measure. Aliased or indirect conformances, some factory
forms, and a decision that merely calls a Specification from an ordinary `if`
may need review. Python liveness is intentionally conservative and currently
supports named class declarations, aliased and unaliased module imports,
import-based re-export chains, direct and parameterized generic constructor
calls, class-level factory calls, known evaluator/combinator calls, runtime
`isinstance`/`issubclass` and class-pattern uses, static type
registry values, and explicit registration calls. Module-level `__getattr__`,
computed `__all__`, and cyclic re-export paths stay `unknown` when they could
affect a declaration. Inspect the `specification_liveness` evidence and raw
counts before interpreting changes.
A parse, marker, scope, or unknown liveness issue marks a report provisional.

## Current reviewed inventory

`sync` records each discovered site in a TOML registry. Reviewers classify it
as `eligible` or `excluded`. `measure` can use reviewed exclusions from the
registry, but its denominator comes from the current source only. Historical
entries whose fingerprints are absent no longer contribute to `U`.

`measure --store` saves each distinct report to a SQLite database, including
the source digest, Git revision when available, scope-manifest digest, rule
version, raw counts,
ratio, and parse status. `history` reads these snapshots newest first. Repeating
an identical measurement returns the same snapshot ID instead of appending a
duplicate. The separate `measure-evidence` command retains the earlier
evidence-based `coverage_percent` report; it is not `S / U`.

`defer` is discovered in Swift, but ordinary scope-exit cleanup normally belongs
in `excluded` with a reason. A decision inside its body is scanned separately.

## Install and run

```bash
cargo build --release
cargo run -- scan ../SpecGraph --output candidates.json
cargo run -- sync ../SpecGraph --registry registries/specgraph.toml \
  --include tools/idea_to_spec_promotion_gate.py
# Review each `disposition = "unreviewed"` entry in the registry.
cargo run -- measure ../SpecGraph --registry registries/specgraph.toml \
  --store metrics/specgraph.sqlite --require-complete
cargo run -- history --store metrics/specgraph.sqlite
# Historical evidence report, if needed:
cargo run -- measure-evidence ../SpecGraph --registry registries/specgraph.toml
```

The scanner follows `.gitignore`. Use repeated `--include` arguments to start
with individual files or directories; later `sync --include` calls can expand
that registry's scope. The selected scope is saved in the registry, so
`measure` reuses it. A registry already covering the whole root cannot be
narrowed. Keep one registry per source repository, root, and reviewed production
scope. To establish a narrower scope after a whole-root registry, start a new
registry and history store rather than comparing the two ratios as one trend.

For a whole-project measurement, create a TOML manifest with roles for every
supported source file discovered under the root. More specific paths override
broader paths, so `.` can select the default application scope:

```toml
schema_version = 1

[liveness]
closed_world = true # Only if all runtime consumers are assigned in this manifest.

[[source_sets]]
role = "application"
paths = ["."]

[[source_sets]]
role = "framework"
paths = ["vendor/SpecificationCore"]

[[source_sets]]
role = "test"
paths = ["tests", "fixtures", "examples"]

[[source_sets]]
role = "generated"
paths = ["generated", "build"]

[[source_sets]]
role = "excluded"
paths = ["app/legacy.py", "old/subsystem"]
reason = "Reviewed outside the current adoption scope"
```

An exact file path excludes that file; a directory path excludes all supported
source files below it. These are repository-relative paths, not globs. More
specific paths can select a file back into `application` if needed. The
`excluded` role requires a non-empty reason and removes the file's findings
from both `S` and `U`. A registry site's `disposition = "excluded"` is different:
it removes only one reviewed decision candidate from `U`.

```bash
cargo run -- scan ../SpecGraph --scope-manifest scopes/specgraph.toml
cargo run -- sync ../SpecGraph --scope-manifest scopes/specgraph.toml \
  --registry registries/specgraph.toml
cargo run -- measure ../SpecGraph --scope-manifest scopes/specgraph.toml \
  --registry registries/specgraph.toml --store metrics/specgraph.sqlite \
  --require-complete
```

The manifest is a checked-in measurement contract; it need not live inside the
scanned root. Each supported file must resolve to one role. The report records
the semantic manifest digest, file counts by role group, and any scope issues.
`--include` and `--scope-manifest` are mutually exclusive. A registry is bound
to its manifest digest; changing roles requires a new registry. SQLite history
stores the digest and preserves older snapshots without it.

### Example: this Rust project

[`scopes/specificationmetrics.toml`](scopes/specificationmetrics.toml) assigns
the project's `src` tree to `application` and its liveness fixtures to `test`:

```bash
cargo run -- scan . --scope-manifest scopes/specificationmetrics.toml
```

Rust unit tests written inline in `src` files remain part of the `application`
role because source roles apply to whole files. Put tests in a separate
directory such as `tests/` and add it as a `test` source set when you want to
exclude those files from the ratio.

The scanner reports source parse and scope issues explicitly. `sync` always
rejects unresolved scope issues and refuses parse errors unless
`--allow-partial` is given. Live
`measure` sets `provisional` for parse issues, scope issues, or an unreviewed
whole-root scope; `--require-complete` fails in those cases. The older
`measure-evidence` report also considers unreviewed candidates and missing
legacy anchors provisional.

## Registry and evidence report

The first `sync` creates entries like this:

```toml
schema_version = 1
includes = ["tools/policy.py"]

[[sites]]
id = "python:tools/policy.py:if:...:1"
fingerprint = "python:tools/policy.py:if:...:1"
language = "python"
path = "tools/policy.py"
kind = "if"
disposition = "unreviewed"
```

Give each reviewed entry a stable human-readable `id`. An excluded entry needs
a non-empty `reason`. In the separate evidence report, an eligible entry can
earn one point for each evidence reference:

```toml
[[sites]]
id = "promotion-pre-sib-state"
fingerprint = "python:tools/idea_to_spec_promotion_gate.py:if:...:1"
language = "python"
path = "tools/idea_to_spec_promotion_gate.py"
kind = "if"
disposition = "eligible"

[sites.evidence]
typed_context = "tools/idea_to_spec_promotion_gate.py#_PreSibDecisionContext"
named_rules = "tools/idea_to_spec_promotion_gate.py#_PRE_SIB_STATE_DECISION"
outcomes_tested = "tests/test_idea_to_spec_promotion_gate.py#test_pre_sib_state_decision_and_trace"
trace_tested = "tests/test_idea_to_spec_promotion_gate.py#expected_trace"
```

An evidence reference is a path relative to the scanned repository, optionally
followed by `#` and a literal marker. The CLI checks that the file and marker
exist. Reviewers remain responsible for confirming that they prove the claimed
criterion and that business outputs are preserved.

```text
coverage_percent = earned_points / (4 × eligible_sites) × 100
```

The report also exposes the counts of scanned candidates, excluded and
unreviewed entries, newly found sites, missing legacy anchors, and parse
issues. `coverage_percent` is `null` when no eligible decision is registered.
Review the absolute counts alongside the percentage; reclassifying an eligible
decision as excluded changes the denominator.

## Syntax currently discovered

| Language | Candidate constructs |
| --- | --- |
| Python | `if`/`elif` chains, conditional expressions, comprehension filters, `match` |
| Swift | `if`/`else if` chains, `guard`, `switch`, `defer` |
| Rust | `if`/`else if` chains, `match` |

A chain is one candidate; independent nested decisions are separate. The
fingerprint combines language, path, construct kind, normalized statement text,
and an occurrence number. It survives lines inserted before the statement.
Editing the statement may change its fingerprint and require reconciliation in
the registry. The persistent `id` remains the identity of the reviewed
decision.

Parsers: [Tree-sitter Python](https://github.com/tree-sitter/tree-sitter-python),
[Tree-sitter Swift](https://github.com/alex-pinkus/tree-sitter-swift), and
[Tree-sitter Rust](https://github.com/tree-sitter/tree-sitter-rust).

## Validation

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

## License

MIT. See [LICENSE](LICENSE).

## Registered rule reuse

Detect newly introduced procedural copies of reviewed Python Specification rules with
`check-rule-reuse`; retain separate SQLite history with `rule-reuse-history`.
See the [matching, gate and optional Jev contract](docs/rule-reuse-contract.md).
The first catalog is [SpecGraph workspace allocation](configs/specgraph-rule-catalog.toml).

### Explicit review-only rule patterns

A registered rule can list `review_templates` for known incomplete or otherwise
non-equivalent checks. These produce `near_match` warnings with
`match_basis: review_template`, including source provenance, while `--strict`
continues to block only new exact copies and incomplete analysis. Exact-match
precedence cannot be weakened by a review pattern. This is catalog-driven
structural detection, not automatic semantic equivalence; see
[the rule reuse contract](docs/rule-reuse-contract.md).
