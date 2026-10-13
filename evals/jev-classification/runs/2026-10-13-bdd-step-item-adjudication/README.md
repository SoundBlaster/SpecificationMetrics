# BDD step-item disagreement: integrator adjudication

**Status:** completed integrator review; advisory, not human gold or an approved
provider-scoring reference. Recommended labels for this exact task:
**`excluded / unknown`** under the unchanged, frozen expression-fit v2 rubric.

The [balanced diagnostic](../2026-10-13-bdd-steps-balanced-factorial-results/analysis.md)
retains three annotations for `bdd-values-step-item` in cell 03: the packet
includes the same-decision Specification evaluation link and omits the validity
contract. All three chose `excluded`; one chose `policy` and two chose `unknown`
for primary responsibility. This review evaluates their evidence against the
existing rubric rather than deciding by majority vote.

The reviewer is the integrating agent, with prior exposure to the other evidence
cells, their labels, and the study's hypotheses. This is not a fresh, blind or
independent annotation. The judgment below is restricted to what cell 03
supplies; withheld contracts and other cells cannot justify its label. Model
identity is unverified. [adjudication.json](adjudication.json) binds the review
to the exact input files, original labels, task identity and quoted witnesses.

## Exact decision and observed arguments

The selected expression is `not step.valid`, not the whole values validator.
Its subject is an individual BDD step, its alternatives are valid / invalid,
and its visible role is deciding whether to emit an `invalid_value` finding.
The meaning and implementation of `step.valid` are not supplied.

| Original annotation | Opportunity | Concern kind | Argument in the original rationale |
| --- | --- | --- | --- |
| [annotator-01](../2026-10-13-bdd-steps-balanced-factorial-results/annotations/annotator-01.json) | excluded | policy | The invalid-step finding sits in the BDD values policy and its policy pipeline. The uncertainty explicitly acknowledges that the precise validity criterion is absent. |
| [annotator-02](../2026-10-13-bdd-steps-balanced-factorial-results/annotations/annotator-02.json) | excluded | unknown | A finding and its Specification path establish ownership; the missing validity meaning leaves domain constraint and representation check plausible. |
| [annotator-03](../2026-10-13-bdd-steps-balanced-factorial-results/annotations/annotator-03.json) | excluded | unknown | The evaluator establishes existing ownership; class and field names do not settle the missing validity contract. |

## Why opportunity is excluded

The packet establishes a concrete chain, beyond a name or import:

1. The exact `not step.valid` filter occurs inside
   `BDDScenarioValuesSpec.findings` and controls the finding.
2. `BDDScenarioValuesSpec(BDDPolicy)` inherits through
   `BDDPolicy(Specification[BDDContext])`.
3. The satisfaction evaluator uses `return not self.findings(candidate)`.
4. `POLICIES` includes `BDDScenarioValuesSpec()` and the supplied loop invokes
   `policy.is_satisfied_by(context, recorder=recorder)` and `policy.findings(context)`.

E5 and the frozen opportunity question accept this explicit, same-decision
declaration and evaluation path as existing representation. Missing validity
semantics do not erase that structural evidence. The packet supports `excluded`
as a new opportunity; this bounded judgment does not certify canonical S/U
accounting or prove that every runtime context executes the check.

## Why responsibility remains unknown

The frozen concern-kind question says:

> A validation branch can enforce either role: rejection, an unsafe message,
> names and file location alone do not settle it.

Its `unknown` criterion says:

> The supplied evidence does not establish a reliable primary responsibility;
> do not guess from names or silently split a mixed target.

The review protocol separately requires:

> Keep same-decision ownership evidence separate from primary responsibility
> and architectural fit.

`issue("invalid_value", f"{path}.steps[{i}]")` establishes rejection of a step
value. It does not establish what validity means or why the constraint is a
domain obligation. The inheritance and invocation chain establish the use of
SpecificationCore, but that framework can also contain technical validation.
The identifiers `BDDPolicy`, `rule_ref` and `spec_id` provide a topic and an
address; the packet does not resolve those addresses to their contract text.

Both a representation check and a BDD domain-admissibility check are consistent
with the supplied fragments. These are alternative interpretations, not claims
about unshown source. The specific missing witness is the meaning and purpose
of `step.valid`: its implementation with sufficient type context, or a
declared contract establishing the exact predicate's domain role. Every caller
or an executing writer is not required.

Annotator-01's rationale moves from a demonstrated Specification evaluation
path to a semantic `policy` label without supplying that witness. This is an
observable gap in its justification. It does not prove that the real source
check is mechanics, that `policy` is false under fuller evidence, or that the
model internally relied on names. Annotators 02 and 03 identify the material
missing fact required by E2 and E6. Their `unknown` label is better supported
under the frozen rubric.

## Consequences and prevention

- **No rubric revision is needed for this adjudication.** E2, E5 and E6 already
  distinguish semantic responsibility from structural ownership. A future
  changed acceptance rule or classifier prompt would require a new identity.
- **Keep the original observations.** The raw split remains 2–1, concern-kind
  unanimity remains 15/16 target-cell groups, and all 48 original annotations,
  their hashes and the failed earlier H2 remain unchanged. This review covers
  one task; the other fifteen groups have not been semantically adjudicated.
- **Keep authority explicit.** The review recommends one evidence-bounded
  label pair. It does not create human gold, approve v2 for provider scoring,
  activate a classifier, or update metric storage.
- **Check each witness against its axis.** A finding is a rejection witness;
  inheritance and invocation are ownership witnesses; a defined decision role
  is a responsibility witness. A quoted identifier may support one claim
  without supporting another. Exact substring validation alone cannot establish
  that a quote entails the assigned semantic label.

The confirmed observations are the missing validity definition/contract and
the rationale's reliance on the finding and policy evaluation path. The
integrator judges that support insufficient for `policy` under v2. Model-name
bias, cross-case carryover and ordinary sampling variation remain untested
explanations. The observed minority answer does not establish which explanation
caused it.

## Next bounded diagnostic

Prepare a new packet version before running more classification:

1. Retrieve the pinned implementation/type contract behind `step.valid` and
   identify exactly which additional fragment, if any, settles its primary role.
   A generic validity helper alone may still leave that role open.
2. Build a source-derived naming control by consistently renaming the owning
   classes and registry symbols while preserving inheritance, the selected
   expression and evaluation structure. Mark it as a transformed diagnostic
   input, with provenance; do not present it as verbatim source.
3. Freeze cases, task digests, hypotheses and fresh-context assignments. Test
   whether ownership classification survives neutral names and whether a
   semantic witness changes responsibility. Expected behavior is a hypothesis,
   not a gold label inferred from this adjudication.

Include a control with a locally explicit decision role and no external contract
excerpt. This guards against turning this case-specific lesson into blanket
abstention whenever an external requirement is absent. Keep evidence modes
balanced across distinct targets and give each fresh context one view per target.

This separates a possible naming effect from a missing semantic witness. It
does not authorize provider requests. A live Jev/Luna run needs its own frozen
bounded protocol and authorization under the evaluation instructions.

## Verification

The associated receipt records file SHA-256 digests, the shared state/task/rubric
identity of all three repetitions, each original label and the exact packet/rubric
quotes used here. A read-only check compared those bindings with the frozen
artifacts and replayed the balanced preparation. The review adds documentation
and a separate advisory record; it does not rewrite the preparation or results.
