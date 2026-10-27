# Source-derived preservation counterfactuals v1

## Question and sample

Does an inert insertion preserve the selected FirstMatch origin-to-next-branch
link, while an overwrite or deletion still invalidates it?

The dataset reuses the **same three real SpecGraph controls** as
[invalidation v1](../invalidation-v1/README.md). It adds **12 explicitly
synthetic preservation variants**, four per control, from three source
families. No additional real cases or bugs were discovered. These are
author-declared development checks, not an independent accuracy benchmark.
The original 29-case corpus and independent labels remain unchanged.

The [manifest](cases.json) was committed as **`2921730` before replay**.
It pins source corpus/revision/file hashes, source case IDs, exact one-line
insertions, mutated file/excerpt hashes, diffs and expected branch anchors.
Source revision remains `59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe` in
SpecGraph. Source excerpts retain its upstream
[license](../../licenses/specgraph.txt), verified by the runner against Git.

## Four operators

Each variant inserts one line immediately before the original `if` with the
same indentation. The full dependency snapshot otherwise remains byte-exact.

| Operator | Inserted statement | Why the tracked value is preserved |
| --- | --- | --- |
| Comment | `# Evaluation-only preservation control.` | No executable statement |
| Pass | `pass` | No value change |
| Unrelated literal | `_decision_flow_preservation_probe = None` | Assigns a fresh identifier, without evaluating a call |
| Local annotation | `decision: object` or `binding_error: object` | Local variable annotation without an RHS does not replace its assigned value |

The runner rejects the unrelated-literal operator if that probe name already
appears as an identifier or parameter in the original source. These cases
test the selected value/branch dependency. They do not establish that the
insertions are desirable production edits or pass a project's static type
checks; in particular, annotating a MatchResult as `object` can obscure its
members from a type checker. No corpus Python is executed.

For example, one variant preserves the original acceptance decision:

```python
            decision = _ACCEPTANCE_CRITERION_DECISION.decide(context)
            pass
            if decision.value == _AcceptanceCriterionDisposition.ADD_PLACEHOLDER:
                actions.append(_acceptance_criterion_action(context))
```

The real controls are publication binding (`specgraph-05`, direct function),
acceptance placeholder (`specgraph-02`, nested for body) and claim downgrade
(`specgraph-03`, nested for body). Original call anchors remain unchanged;
each synthetic branch and its stop anchor shift down exactly one line.

## Observed results

| Group | Expected | Observed |
| --- | --- | --- |
| Three reused real controls | 3 linked | 3 linked |
| Comments | 3 linked | 3 linked |
| Pass statements | 3 linked | 3 linked |
| Unrelated literal assignments | 3 linked | 3 linked |
| Local annotations without RHS | 3 linked | 3 linked |
| Replayed overwrite negatives | 3 not linked | 3 not linked |
| Replayed deletion negatives | 3 not linked | 3 not linked |

[assessment.json](assessment.json) records **15/15 preservation checks**.
[invalidation-regression.json](invalidation-regression.json) separately
records **9/9 previous invalidation checks**, including the same three real
controls. Do not add these into 24 independent observations: there are
**three reused real controls, 12 new synthetic preservation variants and six
reused synthetic invalidation variants**, across three source families.

All reports are non-provisional with `metric_effect: none`. The Rust binary
hash matches the earlier loop/enum implementation at `1bc73af`; analyzer
code, raw S/U and CI workflows did not change. The shared Python runner was
extended to accept the four new insertion operators and validate a shifted
branch for linked variants. The original invalidation manifest and assessment
stay frozen; their older runner hash remains historical evidence, and the
new regression report records the current runner hash.

## Evidence comparison and an identity lesson

[comparison.json](comparison.json) records an additional comparison:

1. Join each preservation variant to its real control by `source_case_id` and
   the original call anchor, not by `application_id` across snapshots.
2. Require a changed source digest and changed snapshot application ID.
3. Require the stop and branch line numbers to increase by exactly one.
4. Remove only the snapshot application ID and normalize those two line
   numbers. Require all remaining binding evidence to match the control,
   including condition, projections, path, status/reason, enum member and
   enclosing-loop anchors.
5. Compare the previous nine invalidation outcomes and their complete binding,
   source and scope evidence against the frozen invalidation assessment.

All 12 preservation comparisons and all nine invalidation comparisons pass.
The original corpus, first assessment, independent Astra labels, invalidation
manifest and original invalidation assessment are byte-identical to `main`.

An initial diagnostic comparison incorrectly required application IDs to stay
identical across modified sources. Inspection of
`src/liveness/python_decisions.rs` showed that these IDs deliberately include
the source snapshot digest (along with path and call byte offsets). The
comparison was corrected to preserve both snapshot IDs and use the explicit
source-case correspondence instead. The analyzer needed no fix. A comment
can change an evidence identity while leaving the decision dependency intact.

These results establish discrimination between the selected inert and
invalidating operators in three known scopes. They do not demonstrate general
false-positive/false-negative rates, dead Specification detection, arbitrary
CFG support or runtime correctness.

## Reproduction

Reuse the shared counterfactual runner with the new manifest and a local
SpecGraph clone containing the pinned revision:

```sh
.venv/bin/python -B evals/python-decision-flow-v1/counterfactuals/invalidation-v1/replay.py \
  --repo /path/to/SpecGraph \
  --cases evals/python-decision-flow-v1/counterfactuals/preservation-v1/cases.json \
  --binary /path/to/specification-metrics \
  --output /path/to/new/external-artifacts/preservation-run
```

Omit `--cases` to replay the previous invalidation dataset into a different
new output directory. Omit both `--binary` and `--output` for source, license
and mutation verification only. The runner fetches nothing, never imports
or executes source project code, and writes only isolated copies in a new
output directory outside the source repository.

Nine shared harness-integrity tests and the five parent replay tests pass;
Ruff format/check and `git diff --check` pass. New checks ensure shifted branch
anchors are validated, negative cases cannot retain branch evidence, and
the unrelated probe cannot collide with an existing identifier. The exact-byte
test now covers all six mutation operators. No Rust implementation changed,
so its broad test suite was not repeated locally for this evaluation-only task.

Next: use the source-backed pairs to review the boundary for consuming a
decision through a local alias. Keep alias support as a separate proposed
capability; the current analyzer still treats such propagation as unresolved.
