# Matched public Codex envelope ablation — results

Completed 2026-10-19 under the user-approved
[preregistered protocol](../../codex-envelope-ablation-v1.md). Producer preparation
commit `af147fd`; exact 12-request manifest committed as `fec08e0` **before**
inference. No source, rubric, request, scoring rule or producer was changed after
freezing. The transport and classification analysis are separate evidence stages.

## Result

**The predicted ownership regression did not reproduce.** Both conditions returned
the same four labels for all three controls in both repetitions.

| Observation | Minimal classifier | With public Codex default prompt |
| --- | ---: | ---: |
| Valid responses | 6/6 | 6/6 |
| Matching Sol comparator axes | 24/24 | 24/24 |
| Complete-view agreement | 6/6 | 6/6 |
| Consistency violations | 0 | 0 |
| R01 ownership | existing_specification, twice | existing_specification, twice |
| Reported input tokens | 20,212 | 46,408 |
| Reported output tokens | 959 | 962 |
| Reported reasoning tokens | 725 | 728 |
| Cached input tokens | 14,583 | 36,413 |
| Cache-write input tokens | 5,611 | 9,977 |
| Summed attempt/backoff seconds | 40.81638 | 32.487795 |

The public envelope adds **4,366 reported input tokens in every matched pair**,
including both repeats. The treatment changes the `instructions` string only;
model, provider, medium effort, source state, question definitions, schema and
our instruction placement are held fixed. Repeated labels agree in all six
case/arm groups; this small selected sample does not estimate general stability.

| Control | Labels in both arms and both repeats |
| --- | --- |
| R01: workspace allocation Specification | policy / supported / existing_specification / unknown |
| R02: procedural transition policy | policy / supported / unknown / unknown |
| R03: authorization parsing mechanics | mechanics / supported / unknown / unknown |

The model recognized the existing Specification rather than merely classifying
all code as policy or all ownership as unknown. No label/reference was supplied
in the inference requests; the frozen Sol comparator was used only afterward.
Comparator agreement is **not independently established semantic accuracy**.

## What this establishes and leaves open

For the tested **public template**, adding generic coding-agent instructions
increased reported context without changing the answers. Our preregistered
narrow prediction is `not_supported_same_stable_owner`. The smaller arm was
sufficient for these controls, but the experiment is too small for backend
selection, a repeatability claim, or a general quality/cost/latency conclusion.
The longer arm happened to have lower summed elapsed time; caching and provider
variance make that a descriptive observation, not evidence of a speed benefit.

This is **not an exact reconstruction of the earlier CLI**: the pinned public
template differs from its server-cached template, both API arms place our rules
in `instructions`, and the CLI used a different execution envelope/provider
route. The earlier CLI ownership abstention remains real and unexplained.
Do not change the earlier report to count its disagreement as a success.

The API returned nonzero reasoning tokens and echoed medium effort in both
conditions. The earlier CLI reported zero reasoning output tokens. These are
different observed telemetry, not proof that CLI effort was ignored.
[Static follow-up](cli-followup-audit.json) found `use_responses_lite: true` in
the old task's model cache. At the pinned upstream revision, that conditional
branch moves base instructions into a **developer** input fragment and clears
the top-level `instructions` field, while still constructing and including
reasoning settings. The fragment role is explicit in `BaseInstructionsFragment`.
Cached configuration and static source are not a capture of the actual server
request and do not prove the route caused the incorrect ownership answer.

## Transport, usage and integrity

- **12 logical requests, 12 network attempts, 12 potentially billable POSTs**.
  No TLS retries, ambiguous POSTs, semantic retries or new Sol calls.
- Transport interval: `08:11:55.219567`–`08:13:08.543816 UTC`, about 73.3 seconds.
- Each request was stateless, `store: false`, no tools/session history/fallback.
- The reused transport retained complete JSON response objects and the durable
  ledger. It does not preserve original HTTP whitespace/body bytes or headers.
- Gross input counts include cache-related tokens; they are **not currency
  charges**. `billing` contains a payer field, not a monetary amount. No price or
  charge is fabricated. [usage-audit.json](usage-audit.json) preserves the detailed
  counters and paired differences with the response-file binding.
- `result-receipt.json` binds the manifest, preparation receipt, attempt ledger,
  responses and transport receipt. The manifest binds source inputs, producer
  closure, exact request bodies and the public template's Apache-2.0 provenance.
- Semantic consistency was checked using the existing named Specifications.
  The result has no native probabilities, accepted-fact authority or metric effect.
- The active credential value was checked against the run files before
  publication; no credential is included. No account/model cache is published.

## Offline verification and lessons

All six experiment tests pass with **Jev4Mellea 0.9.0** and with the historical
**0.8.0** environment used by root CI. The actual 0.9.0 live environment and
provider source fingerprint are recorded, not replaced with replay metadata.
Tests cover the one-field treatment difference, AB/BA balance, offline-only
preparation, rebinding rejection, single-use execution, synthetic treatment
effects, invalid/refused/wrong-model responses, capture tampering and replay of
this real comparison. Existing Cargo CI invokes them without model access.

The preparation round-trip test exposed a tuple/list serialization mismatch in
retry policy before freezing. Its normalization fix and regression are described
in the protocol. No other pipeline defect or model-internal cause is established
by this run; no prompt was optimized against these answers.

Next: prepare a separate **instruction-placement ablation**, holding API, model,
effort, public envelope and evidence fixed while moving our unchanged rules
between developer-level `instructions` and user input. This requires a new
versioned protocol and inference budget. No additional calls are authorized by
the completed run.
