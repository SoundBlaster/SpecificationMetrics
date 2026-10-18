# Native fact-response adapter v1

The offline `adapt_retrieval_facts_v1.py` entry point decodes saved Jev/Luna
responses for the four-question retrieval preparation contract. It verifies the
preparation receipt, selects the provider request, binds the accepted-fact
fingerprint and questions, and preserves exact response-byte and wire hashes.
The preparation and raw response files are never overwritten.

```bash
cd evals/jev-classification
../../.venv/bin/python adapt_retrieval_facts_v1.py \
  --preparation /path/to/context-preparation \
  --provider jev-coreinfra \
  --response /path/to/captured-response.json \
  --output /path/to/new-adaptation-report.json
```

For Luna use `--provider luna-decision-coreinfra`. This command reads local files;
it does not need credentials, EmbeddingGemma or a network connection. Use the
existing policy environment (`pydantic==2.13.5`, `requirements-policy.txt`).

## Output states

| Condition | Status | Exit | Result |
|---|---|---|---|
| Exact native shape and consistent proposed categories | `proposed_not_accepted` | 0 | Values retained as proposals |
| Valid native shape with contradictory categories | `needs_review` | 2 | Labels retained; no fact proposals emitted |
| Invalid native envelope/distribution/identity | `rejected` | 2 | Fixed rejection code; no prediction emitted |
| Invalid preparation or accepted-fact binding | Command fails | nonzero | No adaptation report |

Model/question identity errors set `stop_required=true`; a caller must resolve
attribution before continuing a future run. Other native errors remain explicit
rejections. Neither report status nor exit 0 authorizes a code change or promotes
a model label into `Facts`.

## Native and semantic contracts

Jev must return a named answer object, Luna a named answer array. Both require
exactly `concern_kind`, `evidence_confidence`, `ownership`, and
`tool_responsibility` with complete, duplicate-free choice coverage. Refusals,
unknown labels, non-finite/Boolean/nonnumeric probabilities, malformed confidence,
nonmaximum choices and old three-axis results are rejected. Numeric provider
confidence is separate from ordinal evidence support. Raw probabilities and
labels are retained without renormalization or correction.

The probability sum tolerance is 0.000001. The established Jev 1.13.0 exception
allows deviations up to 0.01 for questions with **3 or 4 choices**, with a warning
containing the observed total. It does not apply to the two-choice tool question
or Luna. `absent_in_scope` is outside this projection: ranked retrieval cannot
prove ownership absence.

Two named SpycificationCore rules evaluate an immutable proposal context:

- `RoleSupportConsistentSpec`: unknown role iff insufficient evidence support.
- `ResponsibilitiesCompatibleSpec`: simultaneous Specification/composition
  ownership and affirmative tool responsibility requires adjudication, matching
  the existing formal recommendation policy's conflict boundary.

Both rules run independently and produce a deterministic trace. A conflict does
not invalidate the captured native response or change its labels. It prevents
emission of a coherent fact proposal. The 72 category combinations contain 28
consistent and 44 review-required tuples; these are contract states, not measured
model errors. Parsing and I/O remain procedural adapters.

## Evidence boundaries

The report associates the operator-selected response file with a verified local
request. The native body validates the returned model but does not echo a trusted
request hash. This is **not authenticated transport attribution**;
`transport_verified=false`. A future live-run inspector must additionally verify
its transport receipt/request ledger. A same-model response from another request
cannot be distinguished by these native bytes alone.

The report records the selected request wire, model state, scope, target-state,
accepted-fact fingerprint and exact response SHA-256, plus adapter producer
digests. The inventory follows the conservative static import closure of the
adapter entry point and hashes installed SpecificationCore, Pydantic/core and
their validation typing dependencies, including distribution and Python runtime
identities. PR72 review exposed that the original explicit list omitted direct
and transitive dependencies; regression checks now require those paths and
verify that changing their bytes changes provenance. This is a confirmed
reproducibility repair, without rewriting earlier reports or semantic labels.
It does not create rationale, quotes or source locators that native
Choice did not return. Therefore `rich_proposal_compatible=false`: these values
cannot be passed off as the citation-bearing `fact-proposal/v1` response or
automatically accepted by the ownership adapter. Accepted facts, metric counts
and recommendations are unchanged.

Existing preparation packets retain their original `response_adapter_ready=false`
metadata. This adapter is selected explicitly after preparation; its existence
does not rewrite historical readiness claims or grant live-run authority. Old
two/three-question decoders and historical experiment artifacts are preserved.

## Verification and next experiment

Offline regressions cover both envelopes, all category combinations, malformed
and duplicate identities, exact captured-byte hashes, Jev mass boundaries,
probability/confidence validation, stale accepted facts, known-field overwrite
rejection, no preparation mutation, CLI exit states and exclusive output writes.
Synthetic response fixtures are test data, not provider observations or gold.

The [paired study v1](paired-retrieval-study-v1.md) now freezes baseline/retrieval
inputs and blank independent-reference packets, stages a bounded execution and
connects this adapter to a local transport inspector. The later
[eight-agent annotation run](runs/2026-10-18-paired-blind-reference-v1/README.md)
supplies view-conditioned annotations and a provisional integrator-audited
label candidates. Its actual-annotator allocation is unbalanced and a separate
qualification rejects use as an H1/H2 paired reference. Separately authorized live inference and scoring remain pending. Source
retrieval quality and semantic accuracy require that experiment; an offline
decoder test cannot establish them.
