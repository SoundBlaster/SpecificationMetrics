# BDD steps evidence-factor diagnostic preparation

> Superseded before dispatch by the [balanced multi-target preparation](../2026-10-13-bdd-steps-balanced-factorial-preparation/README.md).
> Review found that this draft assigned one evidence condition per annotator,
> confounding condition with annotator. Preserve this directory as the original
> reviewable draft; do not dispatch its assignments.

**Status: superseded before dispatch; four annotation inputs and twelve blank
assignments are retained as a reviewable draft.**

The [rubric-v2 reference](../2026-10-13-rubric-v2-reference/README.md) failed
its decisive-coverage control on `not entry.steps_is_list or not entry.steps`.
That input showed the method body only. This follow-up checks which additional
evidence changes fresh annotators' labels. It is a context-sensitivity
diagnostic for one expression family, not a classifier-accuracy study or a
replacement reference.

## What the source establishes

All facts below were checked at SpecGraph commit
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.

1. The source has an adopted, human-approved native BDD values contract.
   `SG-SPEC-0070` says `steps` is a nonempty ordered list of nonempty strings
   and classifies an empty list as invalid. See the
   [contract values](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/specs/nodes/SG-SPEC-0070.yaml#L397-L399),
   [acceptance evidence](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/specs/nodes/SG-SPEC-0070.yaml#L64-L69),
   and [approval status](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/specs/nodes/SG-SPEC-0070.yaml#L427).
   The characterization test
   [`test_steps_require_a_nonempty_list_of_nonempty_strings`](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tests/test_native_bdd_characterization.py#L154-L160)
   includes the empty-list case.
2. The exact implementation decision is already linked to SpecificationCore.
   `BDDScenarioValuesSpec` carries the rule reference; `BDDPolicy` inherits
   `Specification[BDDContext]` and binds `SG-SPEC-0070`; its evaluator delegates
   to `findings`; and the composition registers and evaluates that policy. See
   [`values_spec.py`](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/native_bdd/values_spec.py#L7-L22),
   [`policy.py`](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/native_bdd/policy.py#L8-L32),
   and [`composition.py`](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/native_bdd/composition.py#L13-L39).

The source therefore rules out a repository-wide missing-contract explanation.
The original `context-03` packet omitted both the approved value contract and
the class/base/evaluation linkage. This confirms what evidence was absent from
that input; it does **not** prove that the omission caused either abstention.

The adopted contract defines input shape and validity. By itself it does not
say whether nonempty steps protect domain completeness or are only a data
representation requirement. Under rubric v2 that leaves the `policy` versus
`mechanics` boundary open. The diagnostic must not seed `policy` as its expected
concern kind.

## Frozen 2×2 design

The four cells all use the exact same target expression, method body,
architecture profile, questions, v2 rubric bytes and annotation instructions.
Only two evidence groups vary:

| Cell | Adopted nonempty-steps contract | Same-decision Specification evaluation link |
|---|---|---|
| 01 | Absent | Absent |
| 02 | Present | Absent |
| 03 | Absent | Present |
| 04 | Present | Present |

The contract group contains only the approved criterion, the explicit values
rule, and its approval status. It omits code materialization bindings. The
implementation-link group shows the concrete class, base Specification, rule
reference, evaluator and composition path, but omits the normative value
contract. The full fragments and exact source hashes live in the
integrator-only `source-mapping.json`; each annotator packet receives only its
own bounded state.

Each cell is assigned to **three fresh independent contexts** (12 annotations
total). An annotator sees exactly one condition, never another view of this
target. The replicates show label and abstention patterns descriptively; with
one expression and three judgments per cell they do not support significance
claims. Agent model identity remains unverified unless exposed by the runtime.

The pre-registered observations are opportunity labels, concern-kind labels,
decisive coverage, within-cell agreement and whether rationales cite the added
evidence. Expected changes are directional hypotheses, not gold labels. In
particular, the contract factor tests whether stated validity resolves
uncertainty; it does not dictate `policy` over `mechanics`. The implementation
link factor tests whether a visible same-decision evaluation path changes the
opportunity axis. The combined cell checks whether annotators distinguish
existing representation from responsibility classification.

No results are present. Do not dispatch this draft or edit the failed H2
outcome, v2 annotation files, provider prompts, production behavior or metric
storage based on it. Use the balanced replacement linked above.

## Reproduction

From `evals/jev-classification`:

```sh
python3 -m unittest -v test_prepare_bdd_steps_factorial.py
python3 prepare_bdd_steps_factorial.py
```

These checks replay the frozen inputs offline. Preparation refuses to overwrite
existing artifacts and reports zero provider requests and zero metric effect.
The upstream SpecGraph excerpts are licensed under Apache-2.0; the license is
copied to [upstream-LICENSE.txt](upstream-LICENSE.txt).
