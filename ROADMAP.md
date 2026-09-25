# Roadmap

This document records completed foundations and proposed work. The CLI scans
Python, Swift, and Rust and computes a live `S / U` ratio. The earlier evidence
report remains available separately. No model inference is part of the current
release.

## Live Specification ratio

The primary project-health metric is `S / U`, recalculated for each source
snapshot. `S` counts distinct recognized Specification definitions and factory
sites once per source location, even when reused at many runtime call sites.
`U` counts current decision opportunities outside Specification. A high ratio
is a valid result; this project does not attempt to balance it with reuse,
coupling, or cohesion metrics.

**Implemented in counting rule v2:** direct conformances/implementations and
selected factory sites in the three languages; current-source denominator;
raw counts and explicit `complete`/`not_applicable` states; optional reviewed
exclusions; and idempotent SQLite snapshots with timestamp, source digest, Git
revision when available, source-role manifest digest, scope, and rule version.
Whole-project scans classify files as application, framework, test, generated,
or explicitly excluded with a reason; only application sources contribute to
the live ratio. The separate
`measure-evidence` command retains the earlier `coverage_percent` report.

**Next accuracy work:** recognize aliased and indirect conformances, more
factory forms, and Specification-backed decisions whose `if` remains outside
a Specification body. Build a labeled cross-language fixture set and compare
each counting rule version against it before changing the metric. Preserve
historical snapshots under their original rule version; do not silently
recalculate old observations with new rules.

Continue the [counting contract](docs/counting-contract.md) with resolved
Specification uses and exact candidate partition counts. An unrestricted root
scan without a manifest remains provisional discovery.

## Specification liveness

Add a diagnostic count of recognized Specification definitions that have no
resolved uses in the measured source set. Exclude confirmed dead definitions
from the live `S / U` ratio, including their internal decision sites, while
keeping the dead-definition count visible in the report. An unresolved or
ambiguous use must remain `unknown` and must not make a definition dead.

**Open contract:** define what counts as a use for each language and source
scope. The analysis needs to account for cross-file references and exported
Specifications that are consumed by code outside the measured root. Dynamic
dispatch, reflection, dependency injection, and public library APIs can make a
textually unused definition live; decide which of these require an explicit
manifest annotation or force an `unknown` result before excluding anything
from the ratio. Keep liveness diagnostics separate from the System One
opportunity classifier below.

## System One assisted candidate classification

**Goal:** reduce the manual effort of reviewing Python, Swift, and Rust
decision candidates while keeping each live denominator auditable. Use a
small, constrained classifier to suggest whether a candidate is a meaningful
SpecificationCore refactoring opportunity, a mechanical construct to exclude,
or uncertain. A suggestion does not change a reviewed classification or score.

### Phase 1 — Labels and evaluation set

- Define a versioned rubric for `eligible`, `excluded`, and `needs_review`.
  Examples of likely exclusions include ordinary input validation and Swift
  scope-exit `defer`; the rubric must describe exceptions and ambiguous cases.
- Create a reviewed, stratified dataset across Python, Swift, and Rust, with
  source language, construct, bounded surrounding code, reviewer label, and
  reason. Keep the dataset license-compatible and free of secrets.
- Establish a simple deterministic baseline and measure per-language confusion
  matrices, eligible precision/recall, false exclusions, abstention rate, and
  review time. Report sample counts and rubric version with every result.

### Phase 2 — Suggestion contract

- Add an optional `suggest` workflow that reads the existing scan output and
  emits a separate, reviewable suggestion artifact. Keep `scan`, `sync`, and
  `measure` deterministic and usable without a model.
- Each suggestion records the candidate fingerprint, proposed label, short
  reason, raw provider scores when available, model/checkpoint revision,
  rubric version, input digest, and inference configuration. Provider scores
  are not treated as interchangeable calibrated probabilities.
- Give the classifier a bounded context that includes the enclosing function
  and relevant nearby code, rather than only the single `if` line. Redact or
  omit sensitive source before any hosted request; hosted inference requires
  explicit opt-in.
- Keep `needs_review` for unsupported syntax, inadequate context, parse errors,
  provider failures, or low-confidence/close decisions. Never turn these into
  silent exclusions.

### Phase 3 — Compare providers

Try the same versioned labels and evaluation set with these candidate backends:

| Backend | Proposed route | Constraint to check |
| --- | --- | --- |
| [Jev](https://docs.typesafe.ai/introduction/quickstart) | Hosted System One `choice` | Source leaves the machine; record request policy, latency, and cost. |
| [Laya](https://github.com/mizorewww/laya-mlx) | Local `choice` through Laya-MLX | MLX runtime targets Apple Silicon; benchmark the selected checkpoint and its license. |
| [GLiNER2.5-Decide](https://huggingface.co/fastino/GLiNER2.5-Decide) | Local GLiNER2 classification | Verify its class scores, context limits, language coverage, and checkpoint license. |

Use an explicit provider adapter, potentially a JSON-lines subprocess for
Python model runtimes called by the Rust CLI. Provider integration should not
become a required dependency of the scanner. Compare quality first; latency,
memory, and cost are secondary selection criteria. Do not claim that a model is
better from a few illustrative examples.

### Phase 4 — Review and adoption

- Show suggestions alongside candidate source and rubric, with an explicit
  accept/correct/abstain review action. Record reviewer decisions separately
  from model output; only accepted decisions update the classification of a
  current candidate. Keep historical classifications for trend explanation.
- Track agreement with reviewers and the rate of corrected false exclusions.
  Re-evaluate on held-out examples after changing the prompt, labels, model,
  checkpoint, or context extraction.
- Reconcile changed fingerprints before carrying a prior suggestion or human
  decision forward. A new source snapshot must not inherit a stale exclusion
  solely because line numbers or syntax look similar.

**Exit criterion:** a provider may be offered as an opt-in review aid when its
held-out quality and abstention behavior are reported for each supported
language, false exclusions are acceptable under a documented review policy,
and the registry remains fully usable without inference. Human-reviewed labels
remain authoritative when resolving ambiguous current candidates; the live
ratio is always recomputed for the source snapshot.
