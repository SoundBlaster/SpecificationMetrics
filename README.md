# SpecificationMetrics

A Rust CLI for measuring Specification adoption in Python, Swift, and Rust.
It scans the current source snapshot and reports the live ratio of distinct
Specification definitions to remaining control-flow opportunities.

See the [roadmap](ROADMAP.md) for proposed System One assisted candidate
classification with Jev, Laya, and GLiNER2.5-Decide.

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

Counting rule v2 recognizes direct Specification/DecisionSpec conformances or
implementations and source sites that construct `PredicateSpec` or `FirstMatch`
variants. It counts a factory site once, regardless of runtime calls. Decisions
inside recognized definitions or factories do not contribute to `U`. Reviewed
`excluded` entries in an optional registry remove only *currently matching*
candidates. Other current candidates contribute to `U`.

The [counting contract](docs/counting-contract.md) defines the source ownership
boundary and the disjoint reasons for removing a candidate from `U`. For a
whole-repository scan, use a versioned source-role manifest. Only `application`
files contribute to the ratio; unassigned or conflicting files make the report
provisional. Without a manifest or explicit `--include` paths, a directory-root
measurement remains provisional discovery.

This is a syntax-based measure. Aliased or indirect conformances, some factory
forms, and a decision that merely calls a Specification from an ordinary `if`
may need review. Inspect `scan` output, its `specifications` list, and the raw
counts before interpreting changes. A parse issue marks a report provisional.

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
