# Ownership fact acceptance v1

This offline boundary supplements [recommendation policy v1](formal-recommendation-policy-v1.md).
It accepts only previously unknown same-decision Specification ownership. Role,
tool responsibility, intent lookup and existing ownership are never silently
rewritten. No provider calls, automatic refactoring, production S/U changes or
authenticated approval service are introduced.

## Why positive and negative evidence differ

One verified same-decision owner can establish `existing_specification`.
Failure to retrieve one cannot establish `absent_in_scope`. Negative evidence
needs explicit scope, complete search coverage, a closed candidate catalogue and
a completed comparison of every candidate with the target decision. Dynamic or
unresolved boundaries must stay visible.

Scope is an exact list of repository-relative files and their SHA-256 digests,
repository/revision identity and a description of the bounded search. It binds
the entire input Facts fingerprint, including target state and scope binding.
The calling application selects that scope independently of the submitted search.
The adapter checks exactly those source bytes; it does not walk the filesystem
or claim that this list covers the entire repository. A broader search requires
a new scope and fresh approvals.

## Evidence paths

### 1. Pinned structural proof

`pinned_bdd` accepts only the existing BDD case/state/scope at SpecGraph revision
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`. It reruns the v2 verifier against the
full pinned modules: declaration containment, inheritance, target in findings,
evaluation path, membership and consumer. Its positive ownership result is a
bounded static fact under ordinary Python bindings and the library contract,
not a runtime identity proof. No reviewer assertion or model confidence is used.
Simple Boolean composition remains eligible for reuse via the previous policy;
this adapter does not introduce a general composition resolver.

### 2. Separately approved search and adjudication

`reviewed_search` takes source bytes and three immutable artifacts:

1. **Scope:** caller-selected source inventory and Facts fingerprint.
2. **Search:** exact scope digest, processed-file identities, producer identity,
   retrieval configuration/query/index digests, candidate kinds with source spans and
   excerpt digests, completion status and unresolved limitations.
3. **Review:** exact search digest and Facts fingerprint, candidate comparisons
   (`same_decision`, `different_decision`, `unknown`, `conflicting`), status,
   unresolved issues and judgment of catalogue closure in the declared scope.

`Trust` is supplied separately by the application: the selected scope digest and
sets of approved search/review digests. An artifact cannot approve itself by
claiming an author or setting `approved: true`. An edited review needs a new
approval. Digests bind content; they do not authenticate a human, a model or a
reviewer's competence. Whoever configures Trust is the authority boundary.

The caller must obtain approval from its authorized review workflow. This PR
does **not** provide that workflow or promote model output automatically. Generic
scanner JSON is not sufficient: an adapter/reviewer must approve its exact
catalogue, account for recognition limits and unresolved imports/dynamic exports,
and settle semantic comparisons. Source spans prove association, not that a class
is a Specification or implements the same decision. Those semantic judgments
remain the responsibility of the approved reviewer.

A candidate kind distinguishes a confirmed code Specification from procedural
code, an intent document or an unknown declaration. A matching intent document
or procedural implementation is useful context, but cannot establish an existing
Specification for reuse. Both the approved declaration kind and same-decision
comparison are required on the reviewed positive path.

The contract is ready for a future adapter to the repository's Rust scanner; it
does not replace that scanner or claim its current syntactic matches prove a
complete semantic catalogue. Test approvals are synthetic fixtures only. No
negative ownership fact for the real SpecGraph project is approved in this PR.

## Acceptance rules and failure semantics

| Priority | Evidence | Result |
|---|---|---|
| 1 | Existing ownership, conflicting facts, or positive ownership conflicting with established tool responsibility | `needs_review`; input unchanged |
| 2 | Pinned proof, or approved non-failed search plus completed review with an unconflicted same-decision candidate | Accept `existing_specification` |
| 3 | Approved complete exhaustive catalogue; all scope files processed; no search/review limitations; closure established; every candidate judged different | Accept `absent_in_scope` |
| fallback | Missing approval, partial coverage, unknown relation or incomplete review | `needs_review`; input unchanged |

Positive reuse can be established even when unrelated candidates remain unknown;
those limitations remain in `reasons`. Any explicit conflicting comparison or
unresolved review limitation blocks the positive path. A genuinely empty
exhaustive catalogue still needs explicit approved closure: emptiness alone is
not evidence. Ranked search can never take the negative path.

Malformed JSON/schema, duplicate identities/keys, substituted target/scope,
stale cross-artifact digests, changed source bytes and invalid excerpts raise
`ValueError`. Insufficient evidence is a normal typed `needs_review` outcome.
Accepted transitions return a new Facts snapshot and ordered rule trace; they
never modify input facts or write to a registry. Reusing an old review against
the resulting new snapshot fails its fingerprint binding.

## RAG / similarity retrieval

RAG is useful upstream as candidate generation. A cheap pilot can combine names
and rule IDs, normalized-code similarity and local semantic embeddings. Index
functions, Specification declarations and intent/spec fragments with their
source identities; update changed chunks by hash. Use exact lookup first,
retrieve a small candidate set, then adjudicate same-decision ownership.

`retrieval.kind=ranked_candidates` records a positive limit plus query, index and
configuration digests. `status=complete` here means the retrieval operation
completed, **not** that all potential analogues were found. Neither a zero-hit
result nor a low similarity score can establish absence, even with an approved
review. An exhaustive catalogue must be a separately produced artifact with no
top-k limit. Similarity is not equivalence or calibrated confidence.

A possible prototype is local FastEmbed + Qdrant: local embeddings and client
local mode are documented in [Qdrant integration documentation](https://qdrant.tech/documentation/frameworks/langchain/);
[hybrid retrieval](https://qdrant.tech/documentation/tutorials-develop/hybrid-search-fastembed/)
combines lexical and semantic signals. No engine/model is installed or selected
by this PR. Measure retrieval recall@k on known Specification/inline pairs,
latency, incremental indexing cost and stale-index rejection before choosing it.
Use existing historical pairs for development and separate held-out decision
families for the final evaluation; avoid comparing a snippet to its own copy.

## Verification

```bash
../../.venv/bin/python -m unittest -v test_ownership_acceptance_v1.py
../../.venv/bin/python replay_ownership_acceptance_v1.py
../../.venv/bin/python replay_recommendation_policy_v1.py
```

Run from `evals/jev-classification`. Tests cover 256 negative-readiness
combinations, missing authority, stale scope/review, modified source, omitted or
duplicate candidates, incomplete coverage, conflicts, empty ranked results and
positive reuse through ranking. The source-bound BDD replay starts from a
deliberately ownership-unknown snapshot and then applies the existing proof. It
tests a handoff, not a new discovery, model accuracy or performance improvement.

Next: implement a bounded retrieval adapter and review packet with frozen source
provenance. Keep candidate ranking, semantic adjudication, fact acceptance and
recommendation as separate stages.
