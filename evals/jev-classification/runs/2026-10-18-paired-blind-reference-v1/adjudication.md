# Source audit and disagreement analysis

## Actual outcome

Eight newly spawned agents received no conversation fork (`fork_turns=none`),
prior labels, other views or author hypotheses. Each read only the common brief,
the fixed four-question rubric and one assigned packet/template. Assignments
retain A1/A2, B1/B2, C1/C2 and D1/D2; **actual agent identities are eight unique
invocations**, not four returning people. All four baseline annotations were
stored and sealed before any second-wave agent was started. The dispatch ledger
records registration times, not independently authenticated exact spawn times.

The stored `raw/*.json` files preserve delivered annotation values, rationale
and witnesses; JSON formatting was normalized during integrator transcription.
Their hashes identify these stored files, not a provider wire response. Input
and prompt hashes, actual task names and the no-fork configuration are recorded.
File access was instruction-bounded on a shared filesystem, not OS-sandboxed.
No claim is made that arbitrary filesystem reads or hidden backend memory were
independently audited. All eight used the same requested inherited configuration
without overrides; the actual model/runtime identity is not exposed by the
spawn result and must not be invented.

| Case | Baseline role / support | Retrieval role / support | Ownership in both | Tool in both |
|---|---|---|---|---|
| R01 | policy / supported | policy / supported | existing_specification | unknown |
| R02 | policy / supported | policy / supported | unknown | unknown |
| R03 | mechanics / supported | mechanics / supported | unknown | unknown |
| R04 | policy / supported | policy / supported | unknown | unknown |

There are **0 changed category tuples out of 4 target pairs**, and **0 changed
axis values out of 16 paired-axis comparisons**. All 8 outputs passed source
quote/span checks and the two existing category-consistency conditions. These
counts compare *different evidence views*; they are not same-view inter-rater
accuracy, Cohen's kappa, 32 independent observations, or Jev/Luna results.

The integrator has seen project history and both views. The following audit is
therefore explicit source-based adjudication, not an independent ninth vote.
No raw category was changed, no conflict was resolved by majority, and missing
Intent was not supplied by inference. The resulting view reference is provisional
evaluation data; it does not create accepted domain Facts or affect S/U.

## R01 — exact declaration is visible in both arms

The target itself is declared as:

```python
WORKSPACE_ALLOCATION_SPEC: PredicateSpec[WorkspaceAllocationContext] = PredicateSpec(
```

Its body compares requested identities/ref/commit/digest and requires both
authorizations (target lines 7–16). This directly supports policy and exact
Specification ownership in either view. AND between ordinary field conditions
does not turn it into composition of supplied Specifications. Additional hits
neither establish a new owner nor contradict the directly visible one. Retain
both annotations. This is a sufficiency control; its own target was never hidden.

## R02 — related approval rules do not own revision-history admissibility

The target requires, among other things:

```python
after.revisions[:-1] != before.revisions
or after.current_revision != before.current_revision + 1
```

It also preserves containment and disposition and constrains initial activation
(target lines 226–250). These are product lifecycle constraints. The retrieved
reviewed-record Specification compares scope digests; transition approval binds
approval outcome/reviewer/time/rationale; allocation binds bootstrap identity and
authorities. Those are distinct decisions. Neither similarity nor shared domain
vocabulary makes them a same-decision Specification or simple composition for
this function. Retain policy/supported and ownership unknown. Unknown concerns
only supplied evidence; it is not a repository-wide absence claim.

## R03 — adapting authorization is not itself the hidden authority decision

The target visibly reconstructs a typed representation:

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

Both views contain this code (lines 209–216); neither supplies the constructor
body or `_object`/`_version`/`_list` definitions. The visible primary operation is
representation adaptation. Domain field names alone cannot establish that the
parser owns the product's publication permission. Retain mechanics/supported
for **this supplied target view**, with unknown ownership. This does not classify
the constructor, its hidden validations, the caller or the whole publication
feature as mechanics. Their semantics and authored Intent remain unresolved.

## R04 — additional caller witness, unchanged category

The target excludes empty/absolute/home-relative paths, backslashes, colons and
parent traversal (lines 57–62). Its Boolean predicate already supports a path
admissibility policy; conversion/trimming support that decision.

The retrieval view additionally supplies `product_environment` lines 87–90:

```python
required_fields = policy.get("workspace_contract", {}).get("required_fields", [])
for field in required_fields:
    if not safe_workspace_path(workspace.get(field)):
        raise ValueError(f"unsafe or missing workspace.{field}")
```

The second annotator cites this caller. It strengthens the link to workspace
configuration admissibility, but the coarse role-support category was already
supported. The allocation Specification in the hits does not own path validity.
Retain both labels. Neither formatter/linter responsibility nor its configuration
is supplied; `unknown` must not be replaced with an inferred negative.

## What this cohort can and cannot test next

There was no categorical disagreement to reopen. The useful change is in R04's
witness set, not its label. All baseline roles are already supported; the only
established owner is visible in the target itself. This creates a ceiling for
measuring added fact resolution and supplies no independently demonstrated
hidden-owner positive. Therefore the cohort can test native/transport plumbing,
abstention and resistance to related-but-different ownership distractors. It
cannot establish a general recall gain, an error rate near 1%, provider ranking
or the benefit of repository RAG at scale.

Keep these results intact. A future semantic-gain cohort should preregister
targets whose supplied baseline genuinely lacks a decision-bearing helper or
same-decision Specification witness, with independently checked relevance in
the retrieval view. Do not replace these cases after seeing provider results.
The current Jev/Luna live run, scoring implementation and external replication
remain unperformed.
