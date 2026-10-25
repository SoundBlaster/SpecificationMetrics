# Loop-body origins and verified enum-member comparisons

This extends the opt-in `python-decision-flow-v1` diagnostic after the
[independent review](../../reviews/astra-medium-2026-10-23/README.md). It leaves
the original 29-case corpus, first assessment and independent labels unchanged.
The same pinned source files are measured; no source project was modified or
executed. No provider calls are involved.

## Expected change, frozen before corpus replay

[expected-deltas.json](expected-deltas.json), committed as `e2c98f6`, identifies
two intended category/status changes: `specgraph-02` and `specgraph-03` become
`linked`. All other categories and flow statuses remain unchanged. The preview
case `specgraph-04` stays unresolved but now reaches the explicit assertion
barrier rather than stopping at its enclosing loop scope.

Loop-body origins and enum comparisons are separate capabilities. Unit tests
exercise each independently and together; neither implies path joins, tracing
iterations or complete CFG analysis. Enum identity is checked against a direct
standard `Enum` base and actual literal member declarations in the same file.
See the [current contract](../../../../docs/decision-flow-contract.md).

## Real-source result

| All five snapshots, same 29 cases | Baseline | Expanded |
| --- | ---: | ---: |
| Immediate identifier bindings | 9 | 9 |
| Linked | 1 | 3 |
| Unresolved | 8 | 6 |
| Not linked | 0 | 0 |
| Inventoried `.decide` calls | 23 | 23 |

Two previously unsupported real branches are now linked:

| Case | SpecGraph source branch | Verified member |
| --- | --- | --- |
| `specgraph-02` | `tools/candidate_repair_loop.py:426` | `_AcceptanceCriterionDisposition.ADD_PLACEHOLDER` |
| `specgraph-03` | `tools/candidate_repair_loop.py:531` | `_UnsupportedClaimDisposition.DOWNGRADE` |

Each link retains its original application identity, scanner candidate
fingerprint, exact condition, enum class/member declaration anchors and two
enclosing loop anchors. `specgraph-04` still stops unresolved at `assert` on
line 681. Other-API `.decide` methods and ordinary-code analogues do not become
Specification links.

[assessment.json](assessment.json) records binary/source/scope hashes, full
expected-delta observations, new-link evidence and 15 byte-identity checks:
`measure`, `python-if-v1` and `python-decisions-v1` are byte-identical between
the preserved baseline and expanded binaries on the same source root/manifest
for each of the five snapshots. Raw S/U and `metric_effect: none` are preserved.
The original accepted link and the other six unchanged binding rows also match
the baseline exactly; only the three declared rows change.

## Why the original replay returns nonzero

The unmodified original `replay.py` compares the old full expectations,
including reason codes. With this binary it intentionally exits **1**, reporting
**26/29** agreement: two formerly unsupported scopes become linked, and the
preview's reason/stop changes to the assertion barrier. This is retained as the
historical baseline comparison, not hidden or called a passing old benchmark.

Comparing categories/statuses with the separately frozen extension expectations
gives **29/29 intended outcomes**, plus the expected preview reason change.
This is development/regression evidence for two known cases, not a new
independent annotation run or population precision/recall estimate.

## Verification and boundaries

- 147 Rust tests passed, including independent loop/enum tests and a CLI
  regression checking declaration/loop evidence and unchanged prior reports.
- Fmt and clippy passed with warnings denied.
- Tests retain uncertainty for missing/fake/mutated/shadowed enums, wildcard
  imports, selected local `enum.py`, unsupported enum shapes and comparisons,
  intervening effects, assertions, break/continue/return, scope directives,
  nested unsupported blocks and loop-else. Overwrites invalidate the origin.
- Scanning stops within the current loop body. It does not follow back edges,
  exit paths, branch bodies or the code after the loop.
- Only the narrow same-module Enum subset is supported. Imported enum classes,
  aliases of those classes, IntEnum/StrEnum, mixins, methods and `auto()` are
  intentionally left unresolved in this first extension.

The corpus still has only three accepted links and no real `not_linked` example.
Next: independently review the two new links and enum-resolution boundaries
before considering any connection to opportunity exclusions.
