# Reproducible metric collection

The Rust CLI's primary observation is always **S, U, and S/U**. `collect` reuses
the existing counting rule and liveness classifier without changing their
meaning. Classic metrics supplement this observation; they never replace it
with a composite quality score. Tests of behavioral parity remain separate.

## Contract and commands

```toml
schema_version = 1
project = "0al-spec/SpecGraph"
root = "../../SpecGraph"
includes = ["tools", "src"]

[supplementary]
python_complexity = false
duplication = false
```

Save this as `configs/specgraph.toml` in SpecificationMetrics, or use the
[included example](../configs/specgraph.toml). Paths are relative to the config,
not the shell working directory. `project` is a stable logical identity, so two
isolated checkouts can share a comparison contract. Unknown TOML fields fail
instead of silently ignoring a misspelled option.

```bash
cargo build --release --locked
target/release/specification-metrics collect --config configs/specgraph.toml \
  --output metrics/specgraph-before.json --store metrics/specgraph.sqlite
# After a refactoring, run again with the same contract:
target/release/specification-metrics collect --config configs/specgraph.toml \
  --output metrics/specgraph-after.json --store metrics/specgraph.sqlite
target/release/specification-metrics compare \
  metrics/specgraph-before.json metrics/specgraph-after.json \
  --output metrics/specgraph-diff.json
target/release/specification-metrics collection-history \
  --store metrics/specgraph.sqlite --limit 20
```

For separate checkouts, copy the config and change only `root` and execution
paths. Choose whole directories rather than a frozen list of files when new
Specification modules should automatically enter the measurement.

Optional `scope_manifest` selects the existing versioned file-role TOML contract
instead of `includes`. `registry` applies existing reviewed candidate exclusions
and can supply includes. Conflicting scopes are rejected. File and directory
exclusions remain those of the source-role manifest; only application source
files contribute to **both** primary and supplementary measurements. Review
the manifest before claiming a whole-repository measurement.

## Primary observation

`primary` contains the complete existing live report, including:

- `specification_definitions` (**S**): live plus unknown definitions/factory sites;
- `remaining_opportunities` (**U**): current candidates outside recognized
  Specification bodies/factories and current reviewed exclusions;
- `scanned_candidates`, `covered_candidates`, `reviewed_exclusions`: the
  denominator's auditable partition;
- live/dead/unknown specification counts and liveness evidence;
- ratio, `complete`/`not_applicable`/`ratio` state, source revision/digest,
  source roles, counting-rule version, parse and marker diagnostics.

Confirmed dead specifications leave S. Unknown specifications stay in S and
make the observation provisional. U is syntax discovery, not an assertion that
every candidate deserves conversion. A ratio above one is valid. U=0 uses an
explicit state and null ratio; no infinity or division by zero is serialized.

## Opt-in external metrics

Install the optional tools in the repository's Python 3.11+ environment;
no metric package becomes a dependency of the Rust scanner:

```bash
# If needed, create the common environment first: python3.11 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements-metrics.txt
```

Enable the desired additions in the config:

```toml
[supplementary]
python_complexity = true
duplication = true
python = "../.venv/bin/python"
```

The interpreter path is config-relative (a bare executable name uses PATH).
Python 3.11+ is the supported baseline. Duplication requires Node.js/npm; the adapter invokes
`npx --yes jscpd@5.0.11`, which may download that pinned package when explicitly
enabled. CI tests it on Node 22. jscpd has a 120-second timeout.

| Observation | External tool | Scope |
| --- | --- | --- |
| LOC/SLOC | Radon 6.0.1 | Selected Python sources |
| Function CC sum/max and per-location results | Radon 6.0.1 | Selected Python sources |
| Function Cog sum/max and per-location results | complexipy 8.0.1 | Selected Python sources |
| Clone pairs, duplicate lines/tokens and locations | jscpd 5.0.11, 30 tokens/3 lines | Selected Python, Swift, Rust sources |

The scanner captures source bytes once. External tools receive a disposable
copy of exactly those captured application files, preserving relative paths.
They do not import application code, rescan excluded directories, or include
benchmark fixtures. Temporary paths and tool timestamps are removed from saved
results. Radon method results are deduplicated by source location because its
API exposes them both directly and under classes. Same-named methods remain
distinct. Raw tool versions and settings accompany the observations.

Function-level CC/Cog are the tools' native observations; **lambda completeness
is not claimed**. Class aggregates are not added to method CC. Swift/Rust CC
and Cog, architecture/layer-policy metrics, churn, coverage, and System One
inference are not implemented by this adapter. Empty Python scope has zero
Python files; this must not be read as zero Swift/Rust complexity.

## Status, history and comparison

`status` is `complete` only when the primary report is authoritative under its
existing rules and all requested supplements completed. It is `provisional`
when primary diagnostics require review, or `partial` when primary is complete
but a requested supplement failed. Inspect every supplement status even when
the overall status is provisional. Disabled tools are `not_requested`, not zero.
Missing executables, wrong Python package versions, timeouts and invalid output
retain a diagnostic, never a fabricated metric.

Default collection returns exit 0 for a valid diagnostic report. Add
`--require-complete` to return nonzero for partial/provisional results. The
diagnostic JSON is still emitted, but strict failure is **not stored**. Invalid
config/root/scope or storage errors also return nonzero. This is a completeness
gate, not a code-quality threshold gate.

`--store` records the full collection in the SQLite `collections` table with
UTC time and content key. Repeating an identical report under the same root
returns the same ID. It can coexist with the existing `snapshots` table:
`history` reads old primary-only reports, `collection-history` reads combined
reports. Existing commands and saved primary reports retain their contracts.
Without `--require-complete`, diagnostic collections can be saved for audit.

`compare` rejects different project identities or contract digests. The digest
includes schema, collector version, adapter source digest, normalized includes,
manifest digest, registry content, counting-rule version and requested tools.
Root/interpreter paths are execution details. Supplemental deltas additionally
require complete results and matching tool versions; otherwise `delta` is null
and status is `not_comparable`. Primary deltas remain visible on provisional
reports, with the comparison explicitly labeled provisional. Ratio delta is
null when either state has no numerical ratio. No automatic better/worse verdict
is emitted.

Stored source digests identify bytes; a Git HEAD is provenance, not a claim
that the working tree was clean. Atomic project-wide filesystem snapshots and
signed/tamper-proof artifacts are not provided. Collection JSON files are
explicit exports; rerunning with the same output path replaces that file.

## Validation

```bash
cargo fmt --check
cargo test --locked
cargo clippy --all-targets --locked -- -D warnings
.venv-metrics/bin/python scripts/test_classic_metrics.py
```

CLI regression tests cover a conversion from U to S, idempotent history,
incompatible contracts, config typos, provisional discovery, and missing tools
under strict mode. External-tool tests cover same-named methods and repeatable
clone reports with portable source paths. No model or network inference is
needed for the primary metric.

### Bounded SpecGraph smoke measurement

The collection was also run twice against SpecGraph revision
`08823f47e820efd2878ff4b782336afdadd66644`, selecting only
`tools/ontology_imports.py`, `tools/ontology_owner_decision_import_v2.py`, and
`tools/ontology_decision_state_spec.py`. Captured source digest:
`46d013bea0c1470c70eb591d4caee7262ba52e23f875b6ca6c984622752ef521`.

| Observation | Result |
| --- | --- |
| S / U | 3 / 639 = 0.004694835680751174 |
| Live / dead / unknown Specifications | 3 / 0 / 0 |
| Collection status | complete for this selected scope |
| Python SLOC | 7934 |
| Function CC sum / max | 1181 / 155 |
| Function Cog sum / max | 1376 / 204 |
| Clone pairs / duplicate lines / tokens | 23 / 161 / 978 |

Both runs returned the same SQLite snapshot ID and all comparison deltas were
zero. These are full-file cohort measurements, not the earlier pilot's selected
function sums, and not whole-project SpecGraph totals.

## Source locations in PR reports

Pass `--candidate-locations` when collecting both checkouts. The optional v1
inventory records only candidates that contribute to U, using the same
partition as the primary counter. Coordinates are one-based lines and UTF-8
byte columns. The stored evidence includes the scan-relative path, kind and
scanner fingerprint. Raw source excerpts are omitted.

```sh
specification-metrics collect --candidate-locations --config base/metrics.toml --output before.json
specification-metrics collect --candidate-locations --config head/metrics.toml --output after.json
specification-metrics compare before.json after.json --output diff.json
specification-metrics compare before.json after.json --github-markdown OWNER/REPO --output locations.md
```

Archive the full JSON and append the Markdown section to the downstream PR
report. Supply the repository slug from trusted workflow configuration. The
section shows up to 20 locations within a 12 KB row budget. For each candidate
file, collection compares the scanned bytes to the Git blob at the reported
revision and repository-relative path. Matching files can link to that commit.
Other files retain their local anchor with a revision-link-unavailable label.

The versioned `opportunity_changes` object identifies both source digests,
revisions, scan prefixes and manifest digests. Under a compatible collection
contract, matching groups use language, scan-relative path, syntax kind and
the scanner's whitespace-normalized subtree hash (fingerprint without its
occurrence suffix). A line shift within a file preserves the key. A changed
key, including a file rename or subtree edit, produces removal and addition
evidence. This measures changes in the U inventory, including crossings of
the Specification boundary.

If a key exists on both sides, compare its multiplicity. Equal counts cancel.
For unequal counts report the complete before/after group as ambiguous,
because occurrence numbers cannot identify which duplicate survived. The
difference in U equals added minus removed plus the net change in ambiguous
groups. The order of locations within a group carries no correspondence claim.

Markdown labels the ambiguous contribution separately and spells out the total:
`Total ΔU: 23 − 2 + (+0) = +21.` Zero contribution from ambiguous groups does
not mean zero total change. The equation uses the full inventory comparison,
even when the location list is truncated. See the [SpecGraph PR 852 control](specgraph-852-u-location-control.md)
for a real example and a proposed mechanics/policy interpretation.
Counts, status and the total ΔU calculation stay visible. Nonempty source
location lists are collapsed by default under `<details>`; zero-change and
unavailable comparisons do not create an empty spoiler. Truncation notices
remain inside the location block, while full JSON is unchanged.

Missing inventories (including older snapshots), unsupported inventory
versions or different known repository prefixes make locations unavailable.
An incomplete primary measurement labels the location comparison provisional.
Counts inconsistent with an inventory, duplicate fingerprints or incompatible
collection contracts fail comparison. Location reporting leaves the counting
rule and the primary collection contract digest intact.

### Function complexity hotspots

`compare` also emits version 1 of `function_changes`. The same
`--github-markdown OWNER/REPO` output appends its Python hotspot table, so an
existing consumer of that output does not need another command. Collection,
S/U, tool versions, counting rule and contract digest are unchanged.
The function section is collapsed by default in a `<details>` block. Its
`<summary>` shows the comparison status; the table, limitations and unavailable
details expand together. JSON remains complete regardless of display state.

The section uses the already retained per-file `cognitive` and `cyclomatic`
observations. Both Python supplements must be complete and have the same
nonempty Radon and complexipy versions. Absent/invalid function details give
`unavailable`; failed supplements or different tools give `not_comparable`.
Neither produces a successful empty table. A provisional primary cohort labels
the comparison `provisional`. No requested Python metrics means `not_requested`
and no Markdown section. No source imports, execution or provider calls occur.

For each tool separately, match only the same path and reported name when
that key has exactly one observation on each side. Keep both original line
anchors; compute the score delta for a changed score. Line shifts alone are
omitted. This is structural correspondence, not proof of semantic identity:
a replacement can retain its name, and the available records contain no body
hash or change history. The section does not detect edits whose scores stay
equal and is not a complete list of functions edited by the PR.

If a key exists on only one side or has duplicate names on either side, retain
each observation as an unmatched row, with a null counterpart and null delta.
In Markdown these are `—` and `not established`. They can represent a move,
rename, addition, removal or ambiguous same-named methods. Do not call them
new/deleted code or fill their unknown baseline with zero. Tool naming differs
(for example Radon's bare method names versus complexipy's qualified names),
so CC and Cog observations are not joined by line or array order. Existing
tool limitations, including incomplete lambda coverage, still apply.
For duplicated keys whose score multisets are equal, omit the entire unchanged
metric group without asserting correspondence between its members. If the
multisets differ, keep every member on both sides as unmatched evidence.

The full JSON retains all rows. Markdown ranks by the larger available score
within each metric, displays at most five CC and five Cog rows, and applies a
12 KB row budget. Scores from the two tools are not combined into a quality
score. Path/name labels are escaped and kept as plain locations: unlike the U
inventory, these legacy function observations have no per-file blob verification
receipt for a trustworthy commit link. Source digests and the U comparison's
revision metadata remain in the encompassing comparison report.

For the historical SpecGraph PR 855 measurement (`39b66a60ad0d` →
`ccd8b4df11f7`, [original report](https://github.com/0al-spec/SpecGraph/pull/855#issuecomment-6554479153)),
local replay of the original six-file CI artifact (artifact `13072404710`,
collection run `41281100140`, analyzer `cd2bc093fec82983ec370536fa9f1d6014ab86e2`)
produced 13 function observations, with 10 shown in Markdown. Selected rows:

| Metric | Function | Before | After | Delta / correspondence |
| --- | --- | ---: | ---: | --- |
| Cog | `capture_project_context` | 109 | 119 | +10, same path and unique reported name |
| Cog | `check_packages` | — | 77 | not established |
| CC | `check_packages` | — | 44 | not established |
| Cog | `_reference_sites` | 13 | — | not established |
| Cog | `reference_sites` | — | 13 | not established |

The two reference-site names illustrate a possible rename without assigning
a zero baseline to either side. The project Cog maximum delta remains zero
while `check_packages` is visible. That observation
does not attribute 77 units to new logic. The project-wide Cog sum delta +97
and U delta +27 remain unchanged independent aggregate observations. This
replays stored metrics without recollecting sources or posting to the historical PR.
