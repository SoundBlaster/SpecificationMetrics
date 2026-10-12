# Exact-expression comparison preparation

Status: source/context preparation and fresh model-reference annotation complete;
provider API preparation pending. **No Jev/Luna inference or quality score.**

## Independent model reference

A fresh subagent received no conversation history and was restricted to reading
`reference-packet.json`. It reported reading only that file; previous labels,
author proposals, source mapping and provider outputs were not supplied. This
restriction was prompt-scoped, not a filesystem sandbox. No model override was
requested; exact inherited model identity is not reported by the tool.

| Cases | Opportunity | Primary responsibility | Basis |
| --- | --- | --- | --- |
| 01, 03, 07 | eligible | policy | Readiness exception, criterion coverage, bootstrap allocation authorization |
| 02, 04 | excluded | policy | The selected same-decision assemblies already use named Specifications |
| 05, 06, 08 | excluded | mechanics | Dictionary/string representation and slug normalization |

All eight classifications include exact quotes from supplied target/context;
state and packet digests match. Both axes agree with the preparation author's
proposals on 8/8 cases. This is **agreement between annotations**, not Jev/Luna
accuracy, a held-out validation set or human gold.

The annotator retained two limitations (cases 02/04): runtime execution and trace
emission are not demonstrated. Integration review retained these verbatim and
made no label overrides. They do not prevent classification of the shown explicit
assemblies; they do prevent liveness/tracing claims. No material label disagreement
remains. One reference-agent task was used; zero Jev/Luna requests were made.

## What changed

The eight targets are the exact expression snapshots already exported by the
Rust analyzer, not the former whole functions. The new rubric evaluates only
these expressions; helper/data/use fragments supply evidence. Every fragment is
an exact UTF-8 slice of its pinned SpecGraph Git file, with full-file digest,
line/byte spans and fragment SHA-256 recorded in `source-mapping.json`.

The context selection is explicit and proposed by the preparation author:

| Case | Expression / context improvement | Context code bytes | Full state bytes |
| --- | --- | ---: | ---: |
| expression-01 | pre-SIB helper call: helper body, readiness/string dependencies and immediate finding/warning | 1,643 | 4,342 |
| expression-02 | Existing pre-SIB FirstMatch assembly: assignment, constructor import, input and outcome types | 1,169 | 4,646 |
| expression-03 | Reference coverage: existing ID/reference derivation and normalization helpers | 2,586 | 5,368 |
| expression-04 | Existing acceptance-criterion FirstMatch assembly: constructor binding, input/outcome types and reference parsing | 1,491 | 5,120 |
| expression-05 | Dict representation condition and immediate fallback | 93 | 2,539 |
| expression-06 | String representation condition and immediate fallback | 131 | 2,608 |
| expression-07 | Allocation conjunction: local data derivation, effect resolution and enforcement; replaces almost the entire large caller | 1,823 | 4,955 |
| expression-08 | Slug fallback: local representation normalization and regex import | 147 | 2,645 |

Limits: 8 KiB total context code and 16 KiB canonical JSON state per case. No
truncation is permitted. Unlisted/cross-file dependencies are explicitly omitted;
the packet does not prove whole-program identity or absence of Specifications.
The full state includes the architectural intent profile. Neither LOC savings nor
multiple uses are prerequisites for a suitable product rule.

The two factory assemblies remain **whole selected assemblies**, including their
predicates. They are controls for existing Specification composition, not a claim
that each assembly is a single semantic intent atom. Responsibility kind is
judged independently of opportunity; a composition can be policy and excluded
because it already expresses its decision through Specifications. The mixed
type/coverage assembly particularly needs reference review of primary responsibility.

## Artifacts and reference boundary

- `reference-packet.json`: the **only task input** to an isolated annotator,
  containing the exact same profile, target, context and questions intended for
  providers. No legacy case IDs, source mapping, previous labels, predictions or
  author proposals. Case IDs are presentation identifiers, not stable rule IDs.
- `annotation-template.json`: pending labels, bound to packet and state digests.
  Preserved as the original unlabelled preparation template, not current reference
  status. Completed results live in a separate artifact.
- `independent-annotations.json`: original fresh annotator labels, quotes and
  uncertainties, plus explicit task/input provenance. Not human gold.
- `reference-review.json`: evidence-validation receipt, comparison against author
  proposals, uncertainty disposition and no label overrides. Integration reviewer
  is the primary agent, not an additional independent annotator.
- `annotation-proposals.json`: fresh expression-level reasoning by the context
  author, who has seen previous results. **Non-blind proposals, not gold or an
  independent reference.** Do not give these to the independent annotator or
  providers. Similarity to historical labels is not a transfer/validation claim.
- `source-mapping.json`: source/target identity, exact fragments, budget inventory
  and existing formal construction evidence for a separate offline gate analysis.
  Do not give this mapping to the annotator/providers; it contains gate evidence
  not present in their shared semantic task.
  Its `awaiting_independent_annotation` field records preparation-time state;
  current status and reference digests are in `comparison-plan.json` and
  `reference-review.json`. Packet and mapping were not rewritten after annotation.
- `context-selectors.json`, `rubric.json`: reviewable preparation inputs.
- `comparison-plan.json`: proposed matched-provider diagnostic and explicit
  success/failure criteria. It is **not an executable live manifest**.

Use a fresh annotator with no previous labels/history and only the reference
packet. An isolated model reference still is not human gold. Resolve material
disagreement before new provider outputs are seen; preserve dissent/uncertainty.
Do not fill the independent template from author proposals. After any change to
state or rubric, regenerate bindings and obtain annotations for the changed task.

## Proposed comparison

Eight cases × two providers × two same-input repeats = **32 logical requests**;
the new retry protocol reserves **at most 96 network attempts**. This draft is
not authorization to spend that budget. The fresh model reference is now bound
in the plan. Execution remains blocked on Luna's actual CoreInfra URL/model/native schema, typed decoders and a
frozen executable wire plan. Jev endpoint/model are historical verified inputs;
they were not live-probed here. Luna availability is user-reported; no endpoint
or payload is guessed.

The preregistered draft requires per-provider/per-repeat agreement ≥7/8 on each
axis, recovery of all eligible reference cases, zero false positives among
reference mechanics/owned controls, and stable categorical labels across repeats.
Derive stratum denominators from the **new reference**, not author proposals.
An empty eligible stratum makes recall unassessable. Operational failures keep
their original denominator and cannot become semantic `needs_review`.

Report raw model results and formal-gate composition separately. Passing supports
only these development cases. Failing rejects the proposed strong reliability
claim here; it does not invalidate SpecificationCore. There is no missing-context
ablation, so neither context causality nor a comparison to old whole-function
accuracy can be inferred. No production prompt, registry or S/U change.

## Reproduction

From `evals/jev-classification`, with the historical SpecGraph objects available:

```sh
python3 prepare_decision_reference.py \
  --source-repo /path/to/SpecGraph \
  --run runs/2026-10-12-expression-reference --check
python3 -m unittest -v test_prepare_decision_reference.py
python3 -m unittest -v test_validate_expression_reference.py
```

`--check` rebuilds packet/mapping in memory from pinned source and compares exact
saved artifacts. CI performs offline artifact/budget/template checks without
requiring a SpecGraph clone. Creating a new preparation directory uses the same
command without `--check` and exclusive output creation.

## Subsequent transport prerequisite verification

The [separate CoreInfra Luna smoke](../2026-10-12-coreinfra-luna-contract-smoke/README.md)
now verifies the native operation/model on one mixed request. Original packet and
annotation provenance above remain unchanged. The matched comparison itself has
sent zero requests; general typed decoders and frozen wires are still pending.

## Frozen matched-provider wires

The [separate executable manifest](../2026-10-12-matched-expression-wires/README.md)
now binds all 32 exact native requests and strict two-axis response decoding.
Preparation is offline; comparison inference and semantic scoring have not run.
