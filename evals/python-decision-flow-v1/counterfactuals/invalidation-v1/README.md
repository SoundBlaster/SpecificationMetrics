# Source-derived invalidation counterfactuals v1

## Purpose and boundaries

**Three unchanged real positive controls and six explicitly synthetic negative
variants, from three SpecGraph families.** The controls reuse existing corpus
cases `specgraph-05`, `specgraph-02` and `specgraph-03`; they are not three newly
discovered real examples. Each control is paired with an overwrite and a
deletion. The same positive is reused across its two pairs: six contrasts,
nine target-case observations, three source families, one source repository.

The [preceding bounded search](../../searches/not-linked-2026-10-25/README.md)
found no qualifying new real negative. This dataset supplies controlled
counterfactuals without relabeling unresolved examples or fabricating a claim
that real bugs were found. Original corpus counts, labels, independent Astra
review and historical assessments remain unchanged.

These are author-declared contract checks, not an independent benchmark or a
population estimate. All source sites and invalidation syntax were already
known during analyzer development. There is no held-out accuracy claim.

## Exact construction

[cases.json](cases.json) was committed as **`be01f71` before the first analyzer
run**. The frozen manifest records the source corpus hash, full source revision,
original case/family/link, original file hash, exact insertion, mutated file
and excerpt hashes, unified diff and expected status/reason/stop anchor.

Source revision: `59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe` in SpecGraph.
Sources and excerpts keep their upstream license, retained in
[licenses/specgraph.txt](../../licenses/specgraph.txt). The runner verifies
that copy against the pinned repository license. No source checkout is edited.

The entire selected original dependency snapshot is reconstructed from Git for
each run. Only one target file receives one additional line, immediately before
the original next `if`, with its original indentation. No other byte changes.
The three baselines use unmodified full-source files. Targets:

| Existing case | Original origin / branch | Scope | Insertions, separately |
| --- | --- | --- | --- |
| `specgraph-05` | `traceability/publication.py:238 / 246` | Function | `binding_error = None`; `del binding_error` |
| `specgraph-02` | `candidate_repair_loop.py:425 / 426` | Nested for body | `decision = None`; `del decision` |
| `specgraph-03` | `candidate_repair_loop.py:530 / 531` | Nested for body | `decision = None`; `del decision` |

Paths in the table are relative to the `tools` import root. All origins precede
their insertion, so origin line/column anchors remain unchanged; the original
branch shifts down one line in each synthetic variant.

For example, the real acceptance decision reads:

```python
            decision = _ACCEPTANCE_CRITERION_DECISION.decide(context)
            if decision.value == _AcceptanceCriterionDisposition.ADD_PLACEHOLDER:
                actions.append(_acceptance_criterion_action(context))
```

Its overwrite variant reads:

```python
            decision = _ACCEPTANCE_CRITERION_DECISION.decide(context)
            decision = None
            if decision.value == _AcceptanceCriterionDisposition.ADD_PLACEHOLDER:
                actions.append(_acceptance_criterion_action(context))
```

The deletion variant inserts `del decision` instead. These are intentional
damaged programs, **not behavior-preserving refactorings**. Overwriting
`binding_error` with `None` would suppress its subsequent truthy guard; reading
`.value` after setting `decision` to `None` would raise `AttributeError` if
reached. Reading a deleted local would raise `UnboundLocalError` if reached.
No such runtime path is executed or dynamically verified here.

## Result

See [assessment.json](assessment.json). The analyzer binary SHA-256 is
`e3742383b1854984abb1e38f0bc9c70c2be46bfb3f1c8a5b999f3c1947d4fcba`, matching
the previously recorded loop/enum implementation at `1bc73af`. The manifest's
`analyzer_contract_source` identifies that support contract; the runner records
the actual binary hash rather than inferring its build source from Git HEAD.

| Target group | Expected | Observed | Reason |
| --- | ---: | ---: | --- |
| Unchanged real controls | 3 linked | 3 linked | `local_straight_line_read` |
| Synthetic overwrite variants | 3 not linked | 3 not linked | `binding_reassigned_or_mutated` |
| Synthetic deletion variants | 3 not linked | 3 not linked | `binding_deleted` |

**9/9 target checks match**: call category, flow status/reason, exact stop
anchor, and the presence of the original branch link for controls or its absence
for negatives. All nine full reports are non-provisional and have
`metric_effect: none`. Other calls in each full dependency snapshot are not
counted as additional corpus cases. Source/scope/report hashes and target
application IDs bind the retained evidence; raw full reports are run artifacts.

This establishes local invalidation sensitivity for these two operators in the
three selected scopes. It does not prove that the Specification itself is dead,
that its call has no side effects, or that all consumers of its value are
absent. It does not expand runtime/CFG support or change raw S/U. Even a
`not_linked` value can have been consumed elsewhere in a more general program;
the claim here is about the tracked origin and its bounded next branch.

## Reproduction

Use a local SpecGraph clone containing the pinned Git revision. No network,
source imports, provider calls, dependency installs or source execution occur.
The existing `replay.py` source verifier and application-ID join are reused.

Verify source and exact mutations without running the analyzer:

```sh
.venv/bin/python -B evals/python-decision-flow-v1/counterfactuals/invalidation-v1/replay.py \
  --repo /path/to/SpecGraph
```

To replay, append `--binary /path/to/specification-metrics` and
`--output /path/to/new/external-artifacts/invalidation-run`. Output must be a
new directory outside the source checkout. Hash, excerpt, mutation, identity,
count and license validation complete before output creation. The runner only
parses the modified Python to validate syntax. It runs the Rust analyzer on
isolated full-source copies with an explicit application-role scope manifest.
This is a selected evaluation scope, not a production-wide SpecGraph metric.

Offline harness checks:

```sh
.venv/bin/python -B -m unittest discover \
  -s evals/python-decision-flow-v1/counterfactuals/invalidation-v1 -p 'test_*.py' -v
```

The six tests cover exact byte preservation, arbitrary extra insertions,
hash/excerpt/diff drift, wrong variable, source-corpus drift and unsafe output
placement. Their small fixture is only a harness test, not a dataset case.
The five existing parent replay tests also pass. Ruff format/check pass.
Rust implementation and CI workflows are unchanged; no broad Rust suite was
repeated for this evaluation-only task.

Next: add separately labeled benign counterfactuals (for example, an unrelated
primitive assignment or a local annotation) to check that insertion alone does
not cause loss of the original link. Keep these separate from real examples
and measure only the chosen branch dependency.
