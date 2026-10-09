# Align explicit expression targets with Rust scanner anchors

## Outcome

The new Rust `extract-decision-target` command extracted **8/8 explicitly
selected historical targets**. **4/8** have an exact position match with legacy
scanner anchors. There were **zero inference calls**. The runner rebuilt the
scanner from this checkout, verified its source/binary digests through the run,
and read each complete SpecGraph source file at its pinned Git revision.

This is structural alignment, not a new semantic quality score or automatic
discovery. [selectors.json](selectors.json) records agent-proposed target
boundaries; [report.json](report.json) binds them to source and exported spans.
No old labels or Jev answers were transferred. All new targets require fresh
annotation with the same target, supporting context, profile and rubric used
for subsequent model evaluation.

## Selected units

| Historical case | Exact new analysis target | Legacy anchor match |
|---|---|---|
| sg-017 | `_pre_sib_original_blocked(pre_sib, materialization)` | yes |
| sg-018 | value constructing `_PRE_SIB_STATE_DECISION` with `FirstMatch` | no |
| sg-019 | `refs and all(ref in existing_ac for ref in refs)` | yes |
| sg-020 | value constructing `_ACCEPTANCE_CRITERION_DECISION` with `FirstMatch.with_fallback` | no |
| sg-031 | `isinstance(value, dict)` | yes |
| sg-032 | `isinstance(value, str) and value.strip()` | yes |
| sg-033 | six-part workspace-allocation conjunction passed to `require` | no |
| sg-034 | `slug or fallback` | no |

The sg-019 target is now its coverage predicate, not the complete 44-line repair
function. The condition of sg-017 calls a helper; its implementation remains a
context dependency, not an automatically counted second opportunity. The sg-033
rule is a call argument, not an `if` or a `return`. The fallback in sg-034 is
syntactically an expression; selection does not make it a domain rule.

The two constructions are assembly/control targets, not claims that each
contains only one indivisible business decision. They remain visible to the
evaluation while the independent source-bound construction check supplies its
evidence. Rust itself reports ownership `unknown` for every extracted target.

An exact anchor match links a legacy fingerprint, not a semantic equivalence
proof. A missing match does not silently exclude a target or change U. Even
matched cases need annotation of the new expression boundary rather than a
copied whole-construct answer.

## Contract and reproducibility

See [decision-target-contract.md](../../../../docs/decision-target-contract.md)
for selection grammar, source-bound IDs, UTF-8 byte positions, context limits,
explicit failures, authority boundaries and the transition plan.

From `evals/jev-classification`, with the historical SpecGraph Git objects:

```bash
python3 decision_target_alignment.py \
  --source-repo /path/to/SpecGraph \
  --scanner ../../target/debug/specification-metrics \
  --selectors runs/2026-10-10-decision-targets/selectors.json \
  --output /tmp/new-target-alignment.json
python3 -m unittest -v test_decision_target_alignment.py
```

Use a new output path. Cargo must be available; the runner builds the expected
debug binary with locked dependencies and refuses an unrelated executable.
The context and anchor may be truncated with explicit flags; the target
expression is never truncated. Source and implementation digests, build dirty
state and all eight selected units are preserved. No API key is needed.

The frozen examples are development inputs, not human-adjudicated gold or a
family holdout. The exporter only supports Python in this pilot and accepts
explicit anchors; it does not expand production scanner coverage. It does not
resolve imports or automatically collect the helper/source dependency closure.

## Next experiment

Build a bounded dependency context for the selected predicates, especially
sg-017's helper and sg-019's `refs`/`existing_ac` derivation. Freeze those inputs
and a fresh target-specific reference before the next bounded Jev run. Keep
context changes distinct from rubric changes and measure both semantic axes.
