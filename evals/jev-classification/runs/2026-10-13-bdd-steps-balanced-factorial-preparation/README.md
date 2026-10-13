# Balanced BDD evidence-factor diagnostic

**Status: source-grounded packet set prepared; nothing has been dispatched.**

The [v2 independent reference](../2026-10-13-rubric-v2-reference/README.md)
failed its decisive-coverage control on a BDD `steps` expression. The source
audit found that the pinned SpecGraph revision already has both an approved
values contract and a SpecificationCore evaluation path. The first follow-up
draft omitted that evidence, and review found it also confounded evidence cell
with annotator. The [superseded draft](../2026-10-13-bdd-steps-factorial-preparation/README.md)
is preserved for traceability and must not be dispatched.

## Question

For these four related decision sites, how do the adopted contract and visible
Specification ownership/evaluation evidence affect the opportunity and
concern-kind labels under the unchanged v2 rubric?

The diagnostic tests which evidence changes labels. It does not set a gold
answer, prove classifier accuracy, or explain the model's internal reasoning.
The source contract establishes validity requirements but does not settle
whether a particular concern is domain policy or representation mechanics.

## Source-grounded target sites

All source facts are pinned to SpecGraph commit
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.

| Target | Exact expression | Enclosing class and method |
|---|---|---|
| `bdd-values-steps-list` | `not entry.steps_is_list or not entry.steps` | `BDDScenarioValuesSpec.findings` |
| `bdd-values-id` | `not entry.id.valid` | `BDDScenarioValuesSpec.findings` |
| `bdd-values-step-item` | `not step.valid` | `BDDScenarioValuesSpec.findings` |
| `bdd-fields-optional-title` | `entry.title_supplied and not entry.title.valid` | `BDDScenarioFieldsSpec.findings` |

Both classes inherit `BDDPolicy`, whose `spec_id` is `SG-SPEC-0070` and whose
base is `Specification[BDDContext]`. The linked evidence presents each exact
target inside its contiguous class-and-method excerpt, then shows the base
Specification, evaluator and composition registration. The contract evidence
is independently varied and includes its approved criteria, explicit values
requirements and approval status. The full source mapping stays
integrator-only.

## Balanced 2×2 design

Each case uses the same target-specific body-only context when Specification
linkage is absent. When linkage is present, that excerpt is replaced by the
contiguous enclosing class and method and accompanied by the Specification base
and evaluation path. Contract and linkage vary independently:

| Cell | Approved values contract | Specification class/evaluation link |
|---|---|---|
| 01 | Absent | Absent |
| 02 | Present | Absent |
| 03 | Absent | Present |
| 04 | Present | Present |

Twelve fresh contexts receive one packet and one blank template each. Every
packet contains all four targets, one target per case, and exactly one case
from each evidence cell. No context sees two views of the same target. Each
target-cell has three fresh annotations, and each evidence cell occurs three
times at every packet position. This crosses evidence condition with
annotator, target and case position instead of assigning one mode to one
annotator.

The prompt asks annotators to judge each case from its own evidence. Since each
context sees related cases with different evidence, cross-case carryover cannot
be ruled out; order is balanced by condition but not statistically eliminated.
This remains a small descriptive diagnostic, not a significance test.

## Interpretation limits

- Four predicates from two classes under one Specification lineage are related
  observations, not an independent sample of the codebase.
- Three annotations per target-cell are useful for descriptive comparison, not
  significance or general accuracy claims.
- The contract says which supplied values are valid; it does not explain the
  domain purpose behind every check or resolve `policy` versus `mechanics`.
- Agent model identity is inherited and remains unverified unless the runtime
  exposes it.
- No provider calls, author labels, metric writes, production prompt changes or
  changes to the failed v2 H2 result are included.

## Reproduction

From `evals/jev-classification`:

```sh
python3 -m unittest -v test_prepare_bdd_steps_balanced_factorial.py
python3 prepare_bdd_steps_balanced_factorial.py
```

The producer binds the saved receipt to the producer digest and every generated
artifact. It refuses to overwrite an existing packet set. Run it without
`--write` to replay the checked-in preparation. The upstream SpecGraph excerpts
are licensed under Apache-2.0; the license is copied to
[upstream-LICENSE.txt](upstream-LICENSE.txt).
