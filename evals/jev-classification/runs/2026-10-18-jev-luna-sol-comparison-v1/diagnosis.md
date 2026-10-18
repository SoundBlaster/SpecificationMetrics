# Jev/Luna versus the empirical Sol top line

## Completed transport, separate semantic result

All 16 planned responses were captured and locally verified against exact
request bytes, ledger, receipt and native identities. All native response shapes
were valid. No TLS errors, retries, ambiguous POSTs or duplicate execution were
observed. This is local consistency evidence, not remote backend attestation.
The 29.1-second run used the original frozen paired requests and profile; no Sol
labels entered provider states and no semantic result was retried or repaired.

| Agreement / behavior | Jev 1.13.0 | Luna Decision `gpt-6-luna` |
|---|---:|---:|
| Role agreement | 7/8 | 1/8 |
| Ownership agreement | 8/8 | 6/8 |
| Primary-axis agreement (role + ownership) | **15/16** | **7/16** |
| Evidence-support agreement | 2/8 | 0/8 |
| Tool-responsibility agreement | 8/8 | 8/8 |
| All-axis agreement | **25/32** | **15/32** |
| Native category-consistent responses | **3/8** | **7/8** |
| Responses requiring consistency review | 5/8 | 1/8 |
| Role abstentions (`unknown`) | 1/8 | 7/8 |

These are raw categorical agreements with the model-specific Sol comparator,
not accuracy. Missing/invalid answers were not dropped: coverage is 8/8 per
provider. Category-consistent does not mean correct: an unhelpful abstention can
be internally consistent. Conversely, correct individual labels do not make an
incoherent tuple acceptable. Existing Specification-based consistency gates
correctly kept all six conflicting tuples in `needs_review`; no facts were
accepted automatically.

## Baseline versus retrieval

| Descriptive comparison | Jev baseline | Jev retrieval | Luna baseline | Luna retrieval |
|---|---:|---:|---:|---:|
| All-axis matches | 11/16 | 14/16 | 7/16 | 8/16 |
| Primary-axis matches | 7/8 | 8/8 | 3/8 | 4/8 |
| Role matches | 3/4 | 4/4 | 0/4 | 1/4 |
| Support matches | 0/4 | 2/4 | 0/4 | 0/4 |
| Ownership matches | 4/4 | 4/4 | 3/4 | 3/4 |

Jev's +3 all-axis match change consists of R01 support (+1) and R04 role/support
(+2). Luna's +1 is R02 role, **while support remains insufficient**, creating a
consistency conflict. It is therefore not a newly usable accepted judgment.
There were no new nonunknown ownership assertions from unrelated retrieved
Specifications. This control cohort's baseline already contains sufficient
role evidence according to Sol and the source audit: these shifts are recognition
changes, not proof that retrieval supplied previously absent decision facts.
Four target pairs with one native observation per view do not establish a
population effect or provider repeatability.

## Concrete disagreements and source audit

### R01 — an explicit Specification is visible in the target

```python
WORKSPACE_ALLOCATION_SPEC: PredicateSpec[WorkspaceAllocationContext] = PredicateSpec(
```

The body matches identity/ref/commit/digest and requires both authorization
flags. Jev recognizes policy and the exact owner in both modes, but its baseline
support is `insufficient`. Retrieval changes support to `supported`.
Luna returns `unknown / insufficient / unknown` in both modes, missing even the
directly visible declaration as an owner. Target self-hit exclusion applies to
retrieval candidates; it did not remove this target code from either request.

### R02 — explicit lifecycle and append-only constraints

```python
if after.revisions[:-1] != before.revisions or after.current_revision != before.current_revision + 1:
    ...
```

This excerpt summarizes the supplied multi-line check; the complete original
body is bound in the preparation. Jev selects policy in both views, Luna only
with retrieval. All four provider support choices are `insufficient`, despite
known policy labels in three answers. Retrieved review/approval/allocation rules
do not establish ownership of this exact append-only transition decision;
ownership remains unknown in all answers, agreeing with Sol.

### R03 — parsing authorization data is not authorizing a write

```python
return SubjectWriteAuthorization(
    data["request_sha256"],
    ...,
    tuple(_list(data["transition_refs"])),
)
```

Jev classifies mechanics in both modes but again reports insufficient support.
Luna abstains in both. The visible extraction/conversion supports the primary
representation role; `_object`, `_version`, `_list` and constructor bodies are
unavailable, so no claim is made that the entire authorization workflow lacks
domain policy. This boundary was also explicit in the independent Sol answers.

### R04 — lexical workspace-path policy

The supplied target rejects empty strings, absolute/home-prefixed paths,
backslashes, colons and parent traversal. Jev moves from unknown/insufficient to
policy/supported with retrieval; the supplied caller rejects required workspace
fields using this predicate. Luna abstains in both modes. This does not establish
filesystem containment or symlink safety. No ownership is inferred from the
related workspace-allocation Specification.

## Confirmed observations versus cause hypotheses

**Confirmed:** Jev usually agrees with the role/owner distinction but repeatedly
violates the coupled role/support invariant. Luna strongly prefers abstention in
this particular native task projection. All eight Luna support answers are
insufficient; seven role answers and all ownership answers are unknown. The
native contract checks and source-state/hash audit found no dropped target,
wrong model identity, question mapping error or transport failure.

**Unconfirmed:** the serialized `accepted_facts` explicitly starts with role
unknown/support insufficient and unknown ownership. Those defaults could anchor
the S1 decisions, or the prohibition on turning predictions into accepted facts
could be interpreted too conservatively. Another possibility is weakness in the
support question or the independent selection of answers to logically coupled
questions. The observed probabilities and absent rationales cannot identify the
model's internal cause. Do not call anchoring or a provider bug established.

This is an operational pipeline comparison, not a pure model-only ranking.
Jev/Luna receive the same state/profile and rubric definitions via their native
APIs, but Sol additionally received its frozen source-evidence annotation brief.
API serialization, task framing and execution formats differ. Thus these results
do not establish that Jev is intrinsically stronger than Luna or that Luna cannot
perform this classification under another controlled formulation.

## Provider diagnostics

One Jev role distribution (R02 retrieval) sums to **0.99**, accepted under the
existing pinned absolute allowance of 0.01 for 3/4-option Jev questions. Raw values
and a provenance warning were retained, without normalization. No new tolerance
or gate waiver was introduced. It is separate from semantic disagreement.

Provider-reported usage: Jev 27,949 input / 1,374 output tokens; Luna 23,563 input /
0 output tokens. Luna returned four choice distributions per request despite its
zero output-token counter; that counter does not mean an empty or failed response.
No billing amount or calibrated error estimate is inferred from these fields.
Summed transport time was about 13.09 seconds for Jev and 15.36 for Luna; these
single-run measurements do not establish latency distributions or service SLAs.

## Next controlled diagnostic, not executed

Freeze a new 2-target × 2-provider × 2-state-variant diagnostic (**8 calls**) on
R01 and R03 baseline views. Hold code, profile, question definitions/order and
routes fixed; compare the original state with a state omitting only unresolved
`accepted_facts` placeholders. Both variants are sent anew, interleaved, and
neither contains Sol labels. This tests the anchoring hypothesis directly with
positive ownership and mechanics controls, before changing instructions or
weakening consistency rules. The necessary new preparation/reference binding
must explicitly account for that state change. This proposal does not authorize
or execute further inference.

If the controlled diagnostic changes nothing, investigate task wording/API
projection separately. Preserve all present failures and formal gate outcomes;
do not repair support labels from role labels or silently count abstention as
equivalent to a supported domain decision.
