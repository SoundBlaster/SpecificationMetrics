# Expression-fit v2 independent annotation reference

**Status: 36 fresh annotations completed. H1 repeat agreement passed; H2
decisive-coverage control failed. Not approved or frozen for provider scoring.**

This run evaluates the unchanged machine-readable
[expression-fit v2 rubric](../../rubrics/expression-fit-v2.json) on the same
eighteen source states and six SpecGraph expression families as the
[balanced v1 round](../2026-10-13-balanced-context-reference/README.md).
Inputs, rubric bytes, assignment identities and prospective criteria were
frozen in commit `7024f51` before dispatch. The pinned source is SpecGraph
commit `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`. A task digest binds source
state, questions, instructions, rubric bytes and annotation prompt; matching a
state hash alone is not treated as a same-task repeat.

Six fresh annotation contexts each received one balanced packet and its blank
template. No annotator saw two evidence views of the same target. The parent
retained the combined mapping. Inputs were copied byte-for-byte and checked
again after completion. This is conversation-level isolation on a shared
filesystem, not an enforced filesystem sandbox. The agents had no inherited
conversation context and no model or effort override; their actual model
identity was not independently verified. All raw files are retained unchanged.

## Frozen criteria and result

The prospective plan required two independent annotations per each of 18
states. H1 required at least 16/18 matches on each axis and at least 15/18
joint matches. H2 required both axes to receive decisive labels in both rounds
for ten development controls chosen from the v1 data. These controls are not
human gold labels.

| Measure | Result | Outcome |
|---|---:|---|
| Opportunity agreement | 18/18 | H1 threshold met |
| Concern-kind agreement | 18/18 | H1 threshold met |
| Joint agreement | 18/18 | H1 threshold met |
| Decisive opportunity labels, each round | 10/18 | Coverage decreased |
| Decisive concern-kind labels, each round | 10/18 | Coverage decreased |
| Joint decisive labels, each round | 10/18 | Coverage decreased |
| H1 repeat agreement | 18/18 | Pass |
| H2 decisive coverage on development controls | 9/10 controls | **Fail** |

The sole H2 control failure is `context-03`, the BDD steps predicate. Both
rounds abstained on both axes, producing four abstention events. It remains in
the result; it was not removed or relabeled after seeing the outcome. Nine
other controls retained decisive labels on both axes in both rounds.

The v1 runs agreed on 15/18 labels per axis and 14/18 joint states. Their
decisive counts were 13–14/18 per axis and 13–14/18 jointly. Thus v2 answers
were more repeatable in this sample, while fewer answers were decisive. This is
a descriptive cross-rubric comparison: the annotators and batches differed,
the prompt bookkeeping changed, and there was no concurrent randomized v1
arm. It does not show that the rubric caused the agreement increase or that
either rubric is more accurate.

## Labels by evidence view

Both rounds produced the same table:

| Target | Expression only | Containing declaration | Evidence bundle |
|---|---|---|---|
| YAML newline | excluded / mechanics | excluded / mechanics | excluded / mechanics |
| Manifest path | needs_review / unknown | needs_review / unknown | needs_review / unknown |
| Criterion coverage | needs_review / unknown | eligible / policy | eligible / policy |
| Canonical mutation flag | needs_review / unknown | eligible / policy | eligible / policy |
| Active gate | needs_review / unknown | eligible / policy | eligible / policy |
| BDD scenario steps | needs_review / unknown | **needs_review / unknown** | excluded / policy |

Coverage by view per round was:

| Evidence view | Decisive per axis | Joint decisive |
|---|---:|---:|
| Expression only | 1/6 | 1/6 |
| Containing declaration | 4/6 | 4/6 |
| Evidence bundle | 5/6 | 5/6 |

These views differ in evidence and have one annotator per case per round; their
differences are not a causal context effect. In particular, the bundle for BDD
steps includes an explicit `Specification` declaration, rule reference and
evaluation path, while the declaration view does not establish those facts.
That bundle keeps `excluded / policy`, showing that existing ownership and
responsibility are separate labels. It does not isolate which added fact
resolves the method-only abstention.

## Failure analysis: BDD steps control

The selected expression is:

```python
not entry.steps_is_list or not entry.steps
```

Its method emits an `invalid_value` finding for non-list or empty BDD steps.
Both fresh annotators identified a missing contract that would establish
whether nonemptiness is a BDD domain-completeness rule or an input/schema
representation rule. One also noted that the enclosing type and same-decision
Specification path were absent. The rubric explicitly says missing ownership
alone does not require opportunity abstention; therefore the reported concern
about the absent semantic contract remains material under the rubric.

**Confirmed:** the preregistered coverage criterion failed on this control.
**Not confirmed:** why annotators abstained internally, whether the v2 wording
caused excess abstention, whether the BDD contract is underspecified in the
source context, or whether the earlier v1 decisive labels were overconfident.
The annotations are provisional judgments, not gold labels. Do not infer a
model reasoning defect from their written rationale alone.

Two other patterns are stable abstentions rather than proven improvements:
all three path views are `needs_review / unknown`, and the isolated permission
flag is `needs_review / unknown` in both rounds. The active-gate declaration is
consistently `eligible / policy`, in line with the rubric's obligation-priority
rule. These observations describe repeatability and coverage, not semantic
correctness.

## Interpretation and disposition

This experiment supports a narrow conclusion: **v2 improved repeat agreement
in this selected sample, at the cost of decisive coverage; it did not establish
better classification.** The reference is not ready for Jev/Luna scoring. No
provider calls, metric writes, label overrides, production prompt changes or
S/U changes occurred.

Keep both v1 rounds and this v2 run as immutable evidence. Any changed rubric,
context or acceptance rule requires a newly frozen task identity. A provider
scoring reference needs a separate review of semantic correctness and coverage;
repeat agreement alone is insufficient.

## Next diagnostic

Prepare a source-grounded BDD diagnostic around the exact same predicate and
rubric. First locate the relevant declaration and requirement evidence at the
pinned SpecGraph commit. Then check whether the source supports independent
context factors for (1) the semantic contract for nonempty steps and (2) the
Specification ownership/evaluation path. If the evidence permits it, compare
the four bounded combinations while holding the expression and rubric fixed.
Use fresh annotations, keep task digests distinct for each context, and do not
seed the earlier v1 labels as expected answers. If those facts cannot be varied
independently from real source evidence, document that limitation rather than
inventing a factorial design. Do not edit this frozen run to turn H2 green.

## Reproduction

From `evals/jev-classification`:

```sh
python3 -m unittest -v test_context_reference_v2.py
python3 prepare_context_reference_v2.py
python3 validate_context_reference_v2.py
```

All commands are offline. The preparation replay verifies the frozen inputs;
the validator checks raw outputs, task/rubric/state identities, fresh
assignments, coverage and criteria. Tests also require that perfect agreement
cannot erase a failed coverage control. The JSON
[annotation receipt](annotation-receipt.json) is a reproducible structural
report, not semantic adjudication. SpecGraph source excerpts remain under the
upstream Apache-2.0 license, preserved in [upstream-LICENSE.txt](upstream-LICENSE.txt).
