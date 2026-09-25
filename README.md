# SpecificationMetrics

A Rust CLI for tracking how explicitly selected code decisions are represented
by SpecificationCore. It scans Python, Swift, and Rust syntax, then measures
progress against a reviewed, durable inventory of decision opportunities.

## Why the inventory is durable

Refactoring can remove the original `if` or `switch`. Recounting only current
syntax would then shrink the denominator and overstate progress. `sync` records
each discovered site in a TOML registry. Reviewers classify it as `eligible` or
`excluded`; eligible entries remain in the denominator after their original
syntax disappears.

`defer` is discovered in Swift, but ordinary scope-exit cleanup normally belongs
in `excluded` with a reason. A decision inside its body is scanned separately.

## Install and run

```bash
cargo build --release
cargo run -- scan ../SpecGraph --output candidates.json
cargo run -- sync ../SpecGraph --registry registries/specgraph.toml \
  --include tools/idea_to_spec_promotion_gate.py
# Review each `disposition = "unreviewed"` entry in the registry.
cargo run -- measure ../SpecGraph --registry registries/specgraph.toml
cargo run -- measure ../SpecGraph --registry registries/specgraph.toml --require-complete
```

The scanner follows `.gitignore`. Use repeated `--include` arguments to start
with individual files or directories; later `sync --include` calls can expand
that registry's scope. The selected scope is saved in the registry, so
`measure` reuses it. A registry already covering the whole root cannot be
narrowed. Keep one registry per source repository and root.

The scanner reports source parse errors explicitly. `sync` refuses to update a
registry from a partial scan unless `--allow-partial` is given. `measure` sets
`provisional` when candidates still need review, a legacy eligible anchor
disappeared without complete evidence, or a file could not be parsed.

## Registry and score

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
a non-empty `reason`. An eligible entry can earn one point for each evidence
reference:

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
