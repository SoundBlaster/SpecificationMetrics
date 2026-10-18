# Sol 6.1 Medium: repeatability and top line

## Execution and evidence boundary

User authorized exactly 24 fresh contexts on `gpt-6.1-sol`, reasoning `medium`,
then disagreement analysis, treating the strong-model measurement as a top line.
The [configuration](configuration.json) and [run start](run-start.json) were
written before the first dispatch. The fixed
[preparation plan](../2026-10-18-paired-reference-repeatability-v1/plan.json)
was executed in order, three blocks of eight, with explicit model/effort overrides
and `fork_turns=none`. No historical annotator was reused; no new retries or
additional annotation contexts were requested. Each task received the exact
prepared six-line prompt and only its assigned four read-only inputs. No previous
labels, parent conversation or integrator catalog were passed in the prompt.

This is requested configuration plus recorded tool dispatch, not independent
backend attestation. Revision, decoding parameters and seed are unavailable.
Filesystem isolation was instructional, not an OS sandbox; hidden reads and
runtime isolation were not independently audited. No CoreInfra requests occurred.
These 24 Codex model tasks are inference, not an offline-only experiment.

The root integrator captured delivered final JSON values with normalized
formatting. For the last two blocks, exact returned quote spans were expanded
from the pinned supplied source during transcription and matched to delivered
quotes; rationale, labels, locators and unresolved facts were retained. Files are
not authenticated provider wire bytes. Ledger timestamps record registration
after tool responses, sometimes after completion, **not exact spawn or completion
times**. `run-start.json` preserves its original `running` state; the completion
receipt is the final lifecycle artifact.

## Results

| Measurement | Observed |
|---|---:|
| Completed fresh annotation contexts | 24/24 |
| Views with all three primary-axis judgments identical | 8/8 |
| Same-view primary-axis pair agreement | 48/48 |
| Same-view all-axis pair agreement | 96/96 |
| Label-consistency conflicts | 0 |
| Categorical differences from the historical view reference | 0/32 |

Each view supplies three repeat pairs, so 8 × 3 = 24 pairs per axis; four axes
give 96 comparisons. These are **not 96 independent samples**, nor 96 examples
classified correctly. There are 24 outputs nested in eight views of four target
decisions. Unknown-to-unknown counts as stable; it does not resolve ownership.
The historical 0/32 figure compares eight consensus tuples to their old tuples;
the old eight observations are not pooled into the new repeats or treated as an
independent gold reference. Historical backend settings remain unknown.

Both evidence modes produce the following judgments, with three identical
categorical tuples per mode:

| Case / target | Role | Support | Ownership | Tool responsibility |
|---|---|---|---|---|
| R01 `WORKSPACE_ALLOCATION_SPEC` | policy | supported | existing_specification | unknown |
| R02 `_check_transition` | policy | supported | unknown | unknown |
| R03 `parse_write_authorization` | mechanics | supported | unknown | unknown |
| R04 `safe_workspace_path` | policy | supported | unknown | unknown |

## Disagreement audit: no label repairs

There are no categorical disagreements to adjudicate. The integrator reviewed
the differing rationales, quote choices and unresolved facts against the supplied
views. This is a history-aware audit, not an independent fourth annotation.
No majority vote, additional evidence injection, label editing or rerun was used.

### R01: stable recognition of the exact declared Specification

All six answers identify the target declaration itself:

```python
WORKSPACE_ALLOCATION_SPEC: PredicateSpec[WorkspaceAllocationContext] = PredicateSpec(
```

Some cite only this declaration and the six field/authority checks; others quote
the full named predicate or its name separately. These are equivalent direct
witnesses. Boolean conjunction of fields is not composition of separate
Specifications. Retrieval is unnecessary to establish this owner because the
owner is already visible in the target. The answers do not establish downstream
enforcement or provenance of the authority flags.

### R02: lifecycle policy, not representation adaptation

The witnesses cover the origin prerequisites and append-only revision rules,
including preservation of containment and disposition. Source names are not the
only evidence: the conditions and rejection paths are supplied. Ownership stays
unknown in both modes: retrieved approval/review/allocation Specifications have
related vocabulary but govern different decisions.

Some rationales summarize the origin condition as requiring an activation event;
the cited body additionally requires exactly one revision and one disposition
history entry. That is a difference in summary completeness, not a contrary
judgment. Do not infer the numeric value of `current_revision` for origin solely
from a one-element history or error-message wording; type/upstream invariants
are not supplied. One repeat explicitly records this missing invariant.

### R03: authorization data does not itself authorize a write

All six answers distinguish representation handling from an authority decision:

```python
return SubjectWriteAuthorization(
    data["request_sha256"],
    data["decision_ref"],
    data["reviewer"],
    data["reviewer_authority"],
    data["recorded_at"],
    tuple(_list(data["transition_refs"])),
)
```

Some witnesses include the preceding `_version(...)` call; others begin at the
constructor. Mentioning a version helper is compatible with mechanics here,
but its actual body and the constructor's validation remain unavailable. The
answers consistently refrain from attributing an authorization decision to them.
This does not classify every callee or the entire publication workflow as
mechanics. Retrieved scope/allocation rules do not establish the same owner.

### R04: lexical acceptance rule with supporting normalization

All six answers identify the explicit rejection boundary, not merely string
operations. Retrieval answers additionally cite the caller rejecting required
workspace fields, sometimes just its two rejection lines and sometimes the
whole required-field loop. This strengthens contextual evidence without changing
the already supported policy category. The allocation Specification does not
own lexical path admissibility. None of this proves filesystem containment,
symlink safety or correctness of the entire workspace pipeline.

## How to use this top line

[top-line.json](top-line.json) is a versioned, source-auditable **strong-model
comparator** for these exact eight views and this rubric. It provides a practical
reference line for Jev/Luna label agreement and for inspecting disagreements.
It is not a mathematical upper bound: a cheaper model can be right where Sol is
wrong. Full repeatability also cannot establish semantic truth or calibrate a
1% error claim from four targets.

This cohort has a known baseline-sufficiency ceiling: all roles were already
supported without retrieval, and the only recognized owner was explicit in the
target. Therefore it is useful as a stability/control cohort, but cannot alone
establish retrieval gain. Preserve that result rather than engineer label flips.
Keep future missing-witness cases in a separately versioned cohort.

The frozen scoring v1 and qualification v1/v2 are unchanged. This run does not
retroactively grant H1/H2 eligibility or assert accepted domain facts. A consumer
can report **agreement with Sol top line** using the pinned artifact; calling it
semantic accuracy requires an independently justified reference and a new scoring
contract. Next: prepare the corresponding consumer binding and then compare the
same Jev/Luna views, with disagreements linked to exact source witnesses.
