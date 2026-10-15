# Formal recommendation policy v1

Offline development policy for the Python evaluation pipeline. The Rust CLI,
production S/U, prompts already sent to providers and historical H1/H2 results
are unchanged. SpycificationCore is pinned by full Git commit in
`requirements-policy.txt`; each concrete rule has its own module.

The native diagnostic exposed two distinct problems: both providers changed a
fixed path-role premise; some actions contradicted the supplied premises. The
provider's internal cause is unknown. This policy prevents the orchestration
layer from delegating an already-decided recommendation policy back to a model.
It cannot establish whether its semantic inputs are correct.

## Inputs and authority

`Facts` is an immutable, strict, scope-bound snapshot containing role/support,
same-decision Specification ownership, tool responsibility, bounded intent lookup
and explicit conflicts. Non-unknown claims require artifact digest + locator +
authority. A digest proves association, not truth. The generic evaluator trusts
caller-established premises; it does not read files, verify arbitrary source
claims, search a repository or elevate a model answer into a fact.

Explicit conflicts use the versioned `specmetrics.explicit-conflict/v1` record:
`description` plus at least one `Source` (artifact, SHA-256, locator, authority).
Bare strings and missing/empty provenance are rejected. The enclosing fact
snapshot and decision table remain v1; existing snapshots without conflicts
are unchanged. This validation repair does not establish the truth of a conflict.

The replay adapter verifies the frozen v4.1 examples, source-bound BDD witness
and historical live report before constructing facts. Examples remain
`development_premise`, not independently adjudicated gold. BDD ownership uses
the full-module containment check from v2. No absence-of-ownership claim is
invented for path, gate or YAML. Missing documents may coexist with a completed
*bounded* lookup: completion means the supplied evidence was inspected, not that
all intent is known. A changed source/scope requires a new snapshot.

## Decision table (first match)

| Priority | Condition | Recommendation / basis |
|---|---|---|
| 1 | Explicit conflict, conflicting fact, or simultaneous Specification and tool ownership claims | No action; `needs_review` |
| 2 | Same-decision Specification or simple composition established | `reuse_specification` / existing Specification |
| 3 | Formatter/linter responsibility established | `use_tool_rules` / tool responsibility |
| 4 | Supported policy or variant behavior | `formalize` / domain contract |
| 5 | Supported ordinary mechanics | `keep_procedural` / mechanics |
| 6 | Limited/insufficient role support **after** bounded intent lookup | `formalize` / formalization preference |
| fallback | Insufficient prerequisites | No action; `needs_review` |

Specific ownership takes precedence over role-based defaults. Explicit conflicts
always precede ownership. This v1 conservatively requests review when tool and
Specification ownership overlap; it does not silently decide a migration.
Simple NOT/AND/OR composition needs no new Specification wrapper. It is preserved
in the ownership fact even though both reuse routes select the same action.

`recommended_in_scope` means the premises suffice for this recommendation.
`provisional` preserves an action with unresolved prerequisites, including an
unchecked ownership search. Reuse can be recommended from proven same-decision
ownership even with unresolved role/tool facts; those remain listed. Nothing
authorizes refactoring, deleting a check or changing metrics. In particular,
`use_tool_rules` does not certify that an exact configured rule enforces behavior;
verification of that configuration is required before replacing runtime code.

The ordered trace records satisfied, unsatisfied and skipped rules. Duration is
deliberately excluded from reproducible reports; runtime library traces retain it.

## Model boundary

`proposals.task` exposes only unresolved role, ownership and tool-responsibility
questions. Supported roles and established ownership cannot be proposed again.
The question plan retains the global SpecificationCore architecture profile,
role rubric and response schema. It is not an executable provider request: an
adapter must attach the exact bound source evidence before a future live run.
Conflicting accepted facts produce no model questions and require adjudication.
Intent lookup completion is an orchestrator fact, never a model vote.

`inspect_proposals` binds responses to the entire facts snapshot, requires exactly
the pending fields, checks vocabulary and role/support consistency, and returns
`proposed_not_accepted`. It cannot modify `Facts`. Source locators are for review,
not verified proof. No automatic acceptance path, provider wire adapter or live
inference is added. A later reviewed fact-establishment step is necessary before
proposals can become a new snapshot. Existing live clients are not rewired yet.

## Replay and verification

```bash
../../.venv/bin/python -m pip install -r requirements-policy.txt
../../.venv/bin/python -m unittest -v test_recommendation_policy_v1.py
../../.venv/bin/python replay_recommendation_policy_v1.py
```

Replay keeps all 18 raw observations separate from four formal decisions:

The active replay report is **v1.1** in
`runs/2026-10-15-formal-recommendation-policy-v1-1/`. It corrects the original
v1 interpretation: only the BDD case has source-bound ownership; the other
three retain development premises and unknown ownership. The original report
is preserved byte-for-byte as historical evidence, including its incorrect
"all cases" claim. The corrected report binds its digest and verifies that
all four historical decisions and 18 observations are unchanged.

| Case | Decision | Remaining limitation |
|---|---|---|
| Manifest path predicate | `formalize`, provisional | Role remains unknown; ownership/tool responsibility unchecked |
| Gate precedence | `formalize`, provisional | Ownership/tool responsibility unchecked |
| BDD invalid-step check | `reuse_specification`, recommended in scope | Tool responsibility unchecked; same-decision ownership is source-bound |
| YAML final newline | `use_tool_rules`, provisional | Ownership unchecked; configured enforcement not established |

Every observation is compared with the same orchestration facts, including the
BDD witness even for baseline observations. This is a policy comparison with
additional established facts, **not** a paired accuracy improvement or another
H1/H2 experiment. An action difference can be a granularity difference (e.g.
`keep_procedural` vs `use_tool_rules`) rather than a model error. No percentages
of model accuracy are computed from these development fixtures.

Tests enumerate the 840 valid role/ownership/tool/lookup/conflict combinations,
check conflict precedence, absence-vs-unknown behavior, reuse, mechanics and
uncertainty invariants, exact skipped-rule traces, immutability, invalid inputs,
and stale/overreaching model proposals. They verify policy conditional on facts;
they cannot prove those facts' semantic correctness.

Next: review the fact-establishment boundary, particularly evidence sufficient
for same-decision ownership and scoped absence. Then prepare a versioned native
fact-only experiment with independent annotations; request a separate bounded
live budget only after offline preparation.
