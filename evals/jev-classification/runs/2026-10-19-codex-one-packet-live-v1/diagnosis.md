# Ownership abstention: evidence, unknown cause and prevention

## Observed failure

The selected target declares the complete six-condition decision as:

```python
WORKSPACE_ALLOCATION_SPEC: PredicateSpec[WorkspaceAllocationContext] = PredicateSpec(
    lambda context: (
        context.allocation["workspace_identity"] == context.requested_workspace_identity
        and context.allocation["source_ref"] == context.requested_source_ref
        and context.allocation["expected_commit"] == context.requested_expected_commit
        and context.allocation["identity_allocation_authorized"] is True
        and context.allocation["source_ref_initialization_authorized"] is True
        and context.allocation["declaration_sha256"] == context.requested_declaration_sha256
    ),
    name="subject_publication.workspace_allocation",
)
```

The original packet contains this exact declaration. Its full source witness
also imports `PredicateSpec` from `specification_core`, although the model excerpt
starts at the declaration and does not include that import or the library body.
The source-bound Sol reference and historical API Luna answer identify
`existing_specification`. Codex Luna returns `unknown`. Source review supports
the existing-Specification interpretation; this review does not write an accepted
ownership fact or change the frozen references.

## Confirmed facts versus hypotheses

Confirmed: transport succeeded, the answer is schema-valid, all four questions
arrived unchanged, the model saw the declaration, the raw answer/report agree,
and no tool/error events appear. This is **not** the earlier malformed-output
or tool-configuration failure. No adapter bug explaining this answer is known.

The result has no rationale; its internal cause is **unresolved**. Candidate
explanations include:

1. Anchoring on the supplied unresolved `accepted_facts.ownership: unknown`,
   despite explicit instructions that placeholders are not gold. This alone
   cannot explain the discrepancy: the historical API answer saw the same state
   and chose `existing_specification`.
2. Insufficient recognition of the `PredicateSpec` factory/library contract from
   the excerpt. A missing import/body is an evidence limitation, but the visible
   typed declaration and name are meaningful witnesses. Missing bodies do not
   prove they caused the response.
3. Transport/system-envelope, decoding, backend/model revision or stochastic
   differences. Requested medium and zero reported reasoning tokens do not
   establish the server's actual reasoning behavior.

No explanation above is promoted to a confirmed root cause. There was **no
second model call** to obtain a preferred answer or add rationale after seeing
the reference.

## Lesson and bounded prevention

Passing the transport/schema gate must remain separate from semantic acceptance.
A successful adapter report cannot establish correct ownership or justify
generating a duplicate Specification. Preserve this successful capture **with
its disagreement** as an offline regression fixture. The capture verifier checks
that `ownership: unknown` remains in the raw result/comparison, while Sol and the
historical API label remain `existing_specification`; it must never turn three
matching axes into complete-view agreement. No metric/registry is updated.

The observation is too small to select a backend or conclude medium is worse than
low. It also exposes reported context overhead worth measuring on a controlled
set; the extra reported tokens cannot all be attributed to a particular prompt
component from this capture.

## Next diagnostic — plan only, not authorized here

First connect captured label proposals to the existing deterministic semantic
consumers, preserving abstention and review routing. Do not invent probabilities
for the Codex result or feed its labels straight into accepted facts.

Before any larger comparison, prepare a versioned matched diagnostic with two
separate ablations: (a) explicit library/import contract evidence while keeping
placeholders; (b) omission of unresolved accepted-facts placeholders while keeping
source evidence unchanged. Freeze settings and select additional ownership
controls in advance. Treat changes in evidence as new conditions; reuse Sol only
for unchanged evidence. A new reference or inference budget requires separate
authorization. No large refactor, new threshold or prompt patch is supported by
this single observation.

## Subsequent offline context audit — 2026-10-19

The [context audit](context-audit.json) separates visible task growth from
reported token growth:

| Component | Measured characters |
| --- | ---: |
| Historical API `input` | 3,909 |
| Historical API `instructions` | 11,777 |
| API visible total, excluding schema/transport envelope | 15,686 |
| Codex task on stdin, excluding its schema/agent envelope | 16,801 |
| Visible increase | 1,115 (7.11%) |
| Cached Codex Luna instruction template | 18,037 |

The source state/questions remain equal. Both old and new tasks already repeat
common guidance across four questions; this repetition is not a newly introduced
threefold expansion. The new wrapper adds another common semantic paragraph and
structural guidance. These character measurements are not tokenizer counts.

The task home's `models_cache.json` was fetched at
`2026-10-19T07:25:05.678999Z` by CLI 0.156.1. Its `gpt-6-luna` metadata includes a
substantial generic Codex instruction template as well as persistent-mode and
other optional message templates. The audit records only the selected template's
length/hash and non-sensitive metadata; the full cache includes account metadata
and is not published. **Do not sum all cached templates as active context.**
This supplies a concrete candidate for substantial CLI overhead, but no full
rendered server request was captured, so it cannot allocate the exact 7,518-token
difference to individual components or prove identical token accounting.

Another confirmed difference is **instruction placement**: the historical SDK
places all question instructions/criteria in the Responses `instructions` field,
and state in `input`; the CLI receives the whole packet on stdin as the user task,
under its generic agent instructions. Equality of semantic strings did not
establish equality of their message roles, priority or surrounding instructions.
This is a comparison-control gap, not evidence that more source context was
supplied. The historical endpoint is CoreInfra Responses; the CLI requests its
OpenAI provider and uses the existing Codex authentication. The shared model alias
does not attest identical backend revisions or server execution routes.

These differences make the ownership change less surprising, but its internal
cause is still unresolved: the available response contains no rationale and one
observation cannot establish that the template or instruction placement caused
the abstention. Greater token count supplied no additional source evidence and
does not entail a better answer.

Before comparing quality again, extend the matched-condition protocol to record
instruction placement, effective envelope evidence, provider route and requested
effort alongside task hashes. Attribute unknown portions explicitly. Changing
the CLI's base instructions would be a new capability/profile version requiring
separate preparation, not a silent patch to this frozen run. No new model call
was made during this audit.

## Confirmed offline verifier defect: distinct serialization stages

The first replay check failed with `ValueError: authorization preparation`.
The pre-dispatch CLI output has **39,121 bytes**; the runtime adapter copy has
**39,120 bytes**. Their parsed objects are equal, and the sole byte difference
is a terminal newline in the CLI output. The verifier incorrectly assumed that
the artifact selected for authorization and a runtime reserialization had
identical bytes. This does not invalidate the executed semantic packet or its
typed/digest checks, but it made the new capture verifier fail.

Correction: preserve the exact original as `authorized-prepared.json`, verify
its original authorization SHA-256, retain runtime `prepared.json` with its own
capture digest, and separately require complete parsed equality. Do not rewrite
the authorization or either artifact to make hashes agree. The offline capture
regression exercises this real stage difference and rejects altered answers,
masked disagreement and false automatic acceptance even if local file hashes
are recomputed. The fix requires zero model calls.
