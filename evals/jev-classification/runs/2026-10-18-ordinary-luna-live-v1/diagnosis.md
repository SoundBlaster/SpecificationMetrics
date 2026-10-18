# Ordinary-Luna pilot: observations and limits

## Per-target result

All four axes matched the unchanged Sol comparator in both evidence views:

| Target | Role / support | Ownership |
|---|---|---|
| R01 `WORKSPACE_ALLOCATION_SPEC` | policy / supported | existing_specification |
| R02 `_check_transition` | policy / supported | unknown |
| R03 `parse_write_authorization` | mechanics / supported | unknown |
| R04 `safe_workspace_path` | policy / supported | unknown |

Tool responsibility is unknown in all eight views. Consistency traces contain
`RoleSupportConsistentSpec` and `ResponsibilitiesCompatibleSpec`, both satisfied
for every tuple. No downstream gate repaired an answer or inferred accepted facts.

R01 supplies an explicit Specification declaration, which ordinary Luna correctly
recognizes even without retrieval. R02's transition checks establish a rule in
the supplied code; related Specifications do not prove ownership of that exact
decision. R03 decodes authorization fields; calling it mechanics does not approve
any subsequent write. R04 rejects lexical path forms; policy/supported does not
prove filesystem containment or symlink safety. These decision-unit distinctions
agree with the source-auditable Sol annotations and remain bounded by their inputs.

Compared to native Jev, ordinary Luna resolves the one R04 baseline support
disagreement (`policy/insufficient` → `policy/supported`). Compared to native Luna
Decision, it resolves five unknown role judgments, seven support disagreements
and two ownership disagreements, without losing agreement on any axis. This
accounts for gains of 1/32 and 14/32 respectively. It does not mean every native
disagreement is intrinsically a model error; Sol is a model-specific comparator.

## Interpretation

Confirmed compatibility now extends beyond the library's small ticket probe:
the pinned SDK handled all eight real SpecGraph source packets, emitted matching
requests, returned complete label sets and reproduced them through the same SDK
offline. Successful schemas and internal consistency do not independently prove
semantic truth, although all selected labels also agree with this reference.

The observed ordinary-Luna condition is promising for the common label contract:
32/32 agreement and zero conflicts. It has greater observed client latency than
the historical native transports. No price or billing receipt was reported;
token counts are not monetary cost. Therefore an unconditional claim of being
both better and cheaper/faster would exceed the evidence.

Unresolved causal factors include joint generation of four labels, ordinary
reasoning versus a native Decision API, provider backend revisions, wire
serialization/instruction framing and stochastic/time effects. The model aliases
are reported/requested metadata, not remote backend attestation. The test is not
a controlled isolation of any one factor. No additional native or Sol calls ran.

All targets are development examples whose baseline already supports the
reference; R01 ownership is explicit. Eight views are only four source decisions,
not eight independent domain cases. Retrieval's zero difference here is a ceiling
effect and cannot establish that retrieval is useless elsewhere. Broader blinded
contrastive data and repeatability checks are needed before generalization.

## Engineering findings and prevention

The initial SDK audit assumed a buffered request. Synthetic tests exposed
`httpx2.RequestNotRead` because the exact-endpoint router forwards a stream, while
MockTransport ordinarily reads it later. The consumer now materializes the stream
before byte identity checks and forwards the same bytes. A direct streamed-body
regression and full SDK mock execution passed before any paid call. Upstream
Jev4Mellea was not patched; the defect was in the consumer's auditing wrapper.

At the user's direction, Python was raised from the local 3.10.19 environment to
the common 3.11 baseline, with local 3.11.13, `.python-version`, shared SDK lock,
CI setup versions and current documentation updated together. The old environment
was retained only for rollback. The original 92 decision tests, 34 retrieval tests
and three classic-metrics tests passed under 3.11 before inference; historical
producer sources/receipts and all model outputs remain unchanged.

Typed SDK failure tests cover refusal, unfinished generation and returned-model
mismatch. They stop after one dispatch, preserve errors and planned denominators,
and do not turn failures into unknown labels. An SDK/raw-result tampering test
rebinds file hashes but still fails result reconstruction. The live run needed
none of these failure paths; all eight calls completed without retries.
