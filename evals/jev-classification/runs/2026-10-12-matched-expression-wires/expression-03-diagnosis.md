# expression-03: repair policy, source facts and remaining uncertainty

## Conclusion and evidence status

The `eligible / policy` reference is defensible under the supplied
`specificationcore.intent-centric` profile. The selected expression decides
whether this repair pass should generate an acceptance-criterion placeholder;
it is not merely interpreting an input representation. This is a narrow repair
policy, **not proof of meaningful or complete requirement coverage**.

This diagnosis is a nonblind, post-results integrator review. It is not a new
independent annotation, human gold, or proof of canonical human intent. The
original model reference and all raw predictions remain unchanged. No new
provider requests were made.

## Exact target and source

```python
refs and all(ref in existing_ac for ref in refs)
```

- Source: SpecGraph revision `99b69a9eda02f44b336f7460244abbe9016af18a`,
  `tools/candidate_repair_loop.py`, `_repair_acceptance_criteria`, lines 335–378.
- Target: line 348, UTF-8 byte span `[12336, 12384)`.
- Full file SHA-256: `183b6d897aa1d25f35b50b3b906282108491f3dfeb8f0aa1a08ca1c9788a3059`.
- Expression SHA-256: `4019fa210a0807c03aba6048eae75d2bb766cbf7ca3f4b9b8eca896e9f2b0a15`.
- Shared state SHA-256: `39611fa4b9e41c7aed7543f7e69a1a62e04f34c2b3ee38d30cbbca5d15f29289`.

The [source mapping](../2026-10-12-expression-reference/source-mapping.json)
binds these bytes, context fragments and their hashes. The offline construction
replay regenerated the complete eight-case packet/mapping from pinned Git
sources and required exact equality with the frozen artifacts.

## What decision does the expression make?

The surrounding code derives `refs` from the current requirement and
`existing_ac` from criterion IDs **inside the current node**. When the condition
is truthy, `continue` skips repair generation. Otherwise the function appends an
`add_acceptance_criterion` operation, marked `applied_to_preview`, with a
reviewable placeholder and `repair_generated: True`.

The semantic question is:

> Does this requirement already have at least one criterion reference, with
> every reference resolving in this node, so this pass should skip generating
> a repair placeholder?

The two outcomes are **skip placeholder** and **propose placeholder in the
repair preview**. A possible descriptive rule name is
`RequirementReferencesResolveInCurrentNode`; it should not be named
`RequirementIsFullyCovered`. No new Specification or canonical requirement is
introduced by this diagnostic.

The membership/all calculation is technical. Its application to suppress a
specific domain repair gives the selected expression its policy interpretation.
Under the supplied profile, a stable addressable rule can qualify even with one
use and low complexity. Conversely, this does not mean that every membership
check, graph reference check, or conditional should become a Specification.

## Behavior table and refactoring boundary

| `refs` | `existing_ac` | Condition truthy? | This repair pass |
|---|---|---|---|
| `[]` | `{}` | No; raw result is `[]` | Add placeholder |
| `[]` | `{'a'}` | No; raw result is `[]` | Add placeholder |
| `['a']` | `{}` | No | Add placeholder |
| `['a']` | `{'a'}` | Yes | Skip placeholder |
| `['a', 'b']` | `{'a'}` | No | Add placeholder |
| `['a', 'b']` | `{'a', 'b'}` | Yes | Skip placeholder |
| `['a', 'a']` | `{'a'}` | Yes | Skip placeholder |

The first conjunct prevents vacuous `all([]) == True` from suppressing repair.
Python `and` returns an operand: with empty `refs`, the original value is `[]`,
not the Boolean `False`. A future Boolean Specification can preserve this `if`
decision's truthiness while changing the exact return value. That distinction
must be checked if the expression is consumed outside a condition.

Input helpers retain only nonempty stripped string references and strip
criterion IDs. Duplicate valid references still satisfy the rule. The predicate
does not inspect criterion statements, semantic adequacy, uniqueness, global
references, or approval. Even a resolving placeholder may satisfy it.

## What context was actually supplied?

Both providers received the same canonical state with:

- the exact expression and complete containing repair function;
- derivation of the two collections and the immediate skip/add effect;
- `_nodes`, `_text`, `_list`, `_text_list` and an extra `_dict` fragment;
- the architecture profile and explicit bounded-context limitations.

No fragment was truncated. `_dict` is not used in this selected function path.
Definitions of `_action` and `_slug`, broader callers, cross-file declarations,
runtime bindings and canonical product requirements were not included. The
immediate operation kind and preview status are visible; complete downstream
execution semantics and human intent are not proved.

This supports the narrow interpretation above, but there was no missing-context
ablation. We cannot conclude that the context is scientifically sufficient, that
more context would help, or that its size caused the disagreement. Source facts
establish implementation behavior; normative architectural fit remains a
profile-dependent judgment. A different approved definition would require a new
rubric/reference version and separately reported scoring.

In later pinned revision `cd5dd5e2bc30da59eb936372c8cd6e8d1dcdd4ae`, the
`_ACCEPTANCE_CRITERION_DECISION` assembly (lines 83–108) names a corresponding
`acceptance_criterion.already_covered` rule with `IGNORE` and `ADD_PLACEHOLDER`
outcomes. This illustrates the historical refactoring style. It is not
independent semantic validation and does not transfer a label from that whole
assembly to this expression.

## What did the models return?

All four native responses select `excluded / mechanics`.

| Provider/repeat | P(eligible) | P(excluded) | Opportunity confidence | P(policy) | P(mechanics) | Concern confidence |
|---|---:|---:|---:|---:|---:|---:|
| Jev 1 | 0.19 | 0.78 | 0.67 | 0.23 | 0.76 | 0.68 |
| Jev 2 | 0.19 | 0.78 | 0.67 | 0.30 | 0.69 | 0.59 |
| Luna 1 | 0.36 | 0.61 | 0.42 | 0.37 | 0.49 | 0.32 |
| Luna 2 | 0.36 | 0.61 | 0.42 | 0.37 | 0.49 | 0.32 |

These are provider-native uncalibrated values, not comparable probabilities of
correctness or production fallback thresholds. Complete distributions remain in
[native-validation.json](native-validation.json).

No textual rationales were requested or returned. Possible explanations remain
**untested hypotheses**:

1. Familiar `all`/membership syntax was interpreted as mechanical referential
   integrity without giving enough weight to the repair effect it controls.
2. The rule is implicit in suppression of an action, rather than named in the
   procedural example; surrounding repair scaffolding may obscure that choice.
3. The policy/mechanics boundary is genuinely ambiguous without an approved
   canonical requirement or a more explicit decision boundary in the rubric.

Shared disagreement does not establish either model error in an objective sense
or reference correctness. Under this frozen reference it is a false exclusion;
its cause has not been measured. Do not rewrite the old score or tune against
this one case until it passes.

## Separate formal construction replay

[construction-replay.json](construction-replay.json) applies the existing formal
construction route to recorded semantic answers. It recognizes **only**
`expression-02` and `expression-04`: each selected expression is the exact whole
assigned call, with a verified absolute `specification_core` import binding,
full-file/excerpt hashes, symbol and span. A nested predicate does not inherit
whole-assembly exclusion. Unknown construction is not proof of being unowned.

| Metric, identical in both repeats | Jev raw → routed | Luna raw → routed |
|---|---:|---:|
| Opportunity agreement | 5/8 → 7/8 | 5/8 → 7/8 |
| Existing-composition false positives | 2/2 → 0/2 | 2/2 → 0/2 |
| Eligible recall | 2/3 → 2/3 | 2/3 → 2/3 |
| Concern-kind agreement | 7/8 → 7/8 | 6/8 → 6/8 |
| Preregistered strong criterion | fail → fail | fail → fail |

The gate fixes the two formally recognizable construction errors and leaves
`expression-03` unresolved. Luna also retains its concern-kind disagreement on
`expression-01`. This is offline composition over previously paid answers, not
a fresh end-to-end inference study. Raw labels, probabilities/confidence,
transport artifacts and the reference are unchanged; no S/U writes.

## Next bounded step

Review the narrow skip/add repair rule as a rubric example, then design
contrastive domain/mechanics probes with the same computational shape. Freeze
the hypothesis, target/context variants, reference and budget before any new
inference. Keep this inspected case in development; use new families and human
adjudication for confirmation rather than treating a tuned score as validation.
