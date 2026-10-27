# Source-derived local-alias contrasts v1

## Result and interpretation

**The current Rust analyzer does not discriminate these alias variants.**
Three unchanged real controls link successfully, but all 12 synthetic alias
variants stop as `unresolved / intervening_expression_barrier` at the first
alias assignment. Six variants are author-labeled as retaining the selected
guard's dependency on the original decision; six are labeled as losing it.
The analyzer establishes neither conclusion for those variants.

The [assessment](assessment.json) matches all 15 predeclared bounded-contract
expectations. **15/15 here is expected-refusal conformance, not successful
alias analysis or semantic classification accuracy.** No alias propagation
feature, metric exclusion, or raw S/U change is introduced.

## Sample and frozen expectations

Reuse the same three SpecGraph controls as
[invalidation v1](../invalidation-v1/README.md) and
[preservation v1](../preservation-v1/README.md): publication binding
(`specgraph-05`, direct function), acceptance placeholder (`specgraph-02`,
nested for body) and claim downgrade (`specgraph-03`, nested for body).

The [manifest](cases.json) was committed as **`7c42bf9` before replay**. It
records source-case/family correspondence, full source revision and file
hashes, exact insertions and branch-line rewrite, mutated file/excerpt hashes,
diffs, author semantic expectations and separate bounded analyzer expectations.
There are **three reused real controls and 12 new synthetic variants across
three families**, not 15 new real observations. All semantic labels are
author-declared; no independent review was performed.

The source remains SpecGraph `59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe`,
reconstructed from pinned Git objects with the original selected dependency
snapshot. Excerpts retain the verified upstream
[license](../../licenses/specgraph.txt). Source repositories are read only.
Corpus code is parsed but never imported or executed; no provider is called.

## What the contrasts mean

For each original guard, insert a fresh alias immediately before it and replace
exactly one AST identifier reference in that guard with the alias name. No
other condition token or body statement changes. Four variants are generated
separately; the two-line variants add one reassignment/deletion before the guard.

| Variant | Insertions before guard; guard reads alias | Author expectation for the selected guard | Actual analyzer result |
| --- | --- | --- | --- |
| Alias copy | `alias = decision` | Reads original result | unresolved |
| Original name rebound | `alias = decision`; `decision = None` | Still reads original result through alias | unresolved |
| Alias rebound | `alias = decision`; `alias = None` | Does not read original result | unresolved |
| Alias deleted | `alias = decision`; `del alias` | Cannot read original result; local alias is absent | unresolved |

The table abbreviates the actual fresh identifier
`_decision_flow_alias_probe` as `alias`; publication uses `binding_error`
instead of `decision`. Each variant has three source-family instances.
The generator rejects identifier/parameter collisions and guards with more
than one occurrence of the selected original name. These are local name
bindings; no mutation of the shared object, property setter, call or scope
directive is inserted.

For example, this synthetic acceptance guard still reads the original
MatchResult even though the original local name was rebound:

```python
            decision = _ACCEPTANCE_CRITERION_DECISION.decide(context)
            _decision_flow_alias_probe = decision
            decision = None
            if _decision_flow_alias_probe.value == _AcceptanceCriterionDisposition.ADD_PLACEHOLDER:
                actions.append(_acceptance_criterion_action(context))
```

Replacing the third line with `_decision_flow_alias_probe = None` loses that
dependency; evaluating `.value` would raise `AttributeError` if reached.
In the publication payload case, a `None` alias would instead make the truthy
guard false. Deleting the alias would raise `UnboundLocalError` at its guard
read if reached. Those paths were not dynamically exercised.

The semantic label names only the selected guard's dependency, conditional on
reaching it. It does not claim whole-program behavior preservation, reachability
or equal outcomes. In particular, publication's branch body still reads the
original `binding_error` name for the finding message: rebinding that original
name can change the body output even while the alias guard reads the old
result. These synthetic variants are not proposed production refactorings.

## Why the diagnostic refuses

`python-decision-flow-v1` follows the original immediate identifier binding.
For an intervening assignment, it accepts a narrow literal/pass/annotation
subset or reports a barrier. `alias = decision` reads another identifier; it
is not a permitted literal assignment. The analyzer stops there, before
the later alias rebind/delete or rewritten guard.

The original call anchor remains unchanged in every variant. Its immediate
consumer is still a direct application. Its first flow stop is the inserted
alias assignment at the original branch line, with no linked-branch evidence.
The actual branch moves down one or two lines. An unresolved row must not
be relabeled as a negative or interpreted as a dead Specification.

[comparison.json](comparison.json) separates these groups:

| Origin / author expectation | Count | Actual |
| --- | ---: | --- |
| Reused real controls, guard reads origin | 3 | linked |
| Synthetic aliases, guard reads origin | 6 | unresolved |
| Synthetic aliases, guard loses origin | 6 | unresolved |

## Regressions and provenance

The shared runner was extended to validate the four exact alias operators,
fresh names, a single same-line guard rewrite and the operator's author label.
Its assessment carries the author dependency label separately from observed
status/reason. The Rust analyzer is unchanged; its binary hash matches the
previously recorded loop/enum implementation at `1bc73af`.

The same runner reproduced both earlier datasets:

- [Preservation regression](preservation-regression.json): **15/15**.
- [Invalidation regression](invalidation-regression.json): **9/9**.

Their outcomes, complete binding evidence, source/scope digests and frozen
case-manifest hashes match the earlier assessments. Only run-specific report
hashes and the extended runner hash differ. Original real corpus, original
assessment, independent Astra labels and both prior counterfactual manifests
and assessments remain unchanged from the parent PR #106.

The three real controls are shared by all three datasets. Do not report
39 independent cases by summing the three run totals. Explicit source-case
correspondence pairs modified snapshots; snapshot `application_id` values
are not stable cross-revision identities.

## Reproduce

```sh
.venv/bin/python -B evals/python-decision-flow-v1/counterfactuals/invalidation-v1/replay.py \
  --repo /path/to/SpecGraph \
  --cases evals/python-decision-flow-v1/counterfactuals/alias-v1/cases.json \
  --binary /path/to/specification-metrics \
  --output /path/to/new/external-artifacts/alias-run
```

Omit `--binary` and `--output` for source/license/mutation verification only.
Use the previous manifests and separate new output directories to repeat the
two regressions. The runner validates all sources, exact mutations and hashes
before output creation and rejects output inside the source repository.

Fourteen shared harness tests and five parent replay tests pass. New checks
cover byte changes limited to the declared alias prefix/guard, alias name
collisions, unrelated guard edits, multiple guard reads and inconsistent
operator labels. Ruff format/check and `git diff --check` pass. No broad Rust
suite was rerun locally because neither analyzer nor CI code changed.

Next: design a separate bounded alias-propagation contract. It must track the
original value through copies, distinguish rebinding a name from changing its
other aliases, and preserve unresolved states outside its support boundary.
Use both positive and damaged variants before changing analyzer behavior.
