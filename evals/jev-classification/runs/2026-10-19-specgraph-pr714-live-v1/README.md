# PR714 live route pilot · 2026-10-19

Authorized by the user after merging PR93. Producer committed as `d21870c`, exact
requests/limits frozen before dispatch in `3768a1d`. Source: historical SpecGraph
PR714 at `3ad8836b9e14c501bdfb5aeec11bdfdd65974eea`, using the corrected v2 packets.
Frozen producers, prompts, questions, source views and routing rules were not
changed after observing the responses. No Sol call or new prompt experiment.

## Observed execution

- **4 logical native batches, 4 network attempts, 4 possible POSTs.**
- All HTTP responses 200, requested/returned model metadata `jev-1.13.0`.
- TLS retries: 0; ambiguous POSTs: 0; timeouts: 0.
- Four retained advisory proposals; conditional ordinary reviews selected: **0**.
- Dispatch phase: **9.706058 s**, including child startup, request verification,
  transport, SDK capture parsing and routing between calls.
- HTTP operation time: **7.985958 s total**, mean **1.9964895 s** per native batch.
  This includes connection/send/read, not a provider-only generation latency.
- Provider-reported usage: **41,221 input tokens, 676 output tokens**.
- Request-attributable monetary cost was not returned; billed cost is **unknown**.
  Token counts are not a price estimate.
- No accepted facts, S/U, SpecGraph source or merge gates changed.

Only the first stage and the decision to retain its proposals were exercised
live. Ordinary Luna review was not selected, so this is not a new live validation
of that branch or a Jev-versus-Luna comparison. The approved maximum was eight
logical requests, not a requirement to spend the unused conditional-review budget.

## Actual classifications

All four have `evidence_confidence=supported`, `ownership=unknown`,
`tool_responsibility=unknown`, and final status `proposed_not_accepted`.
Unknown ownership does not establish absence or authorize creating a new Spec.

| Case | Source decision | Jev concern_kind | Native confidence for concern_kind | Largest reported category probability |
| --- | --- | --- | --- | --- |
| D01 | `next_sequential_spec_id` | `variant_behavior` | 0.24 | 0.43 |
| D02 | Locked-reservation ID selection | `variant_behavior` | 0.24 | 0.43 |
| D03 | Migration alias validity | `policy` | 0.31 | 0.48 |
| D04 | Namespaced ID parser | `mechanics` | 0.95 | 0.96 |

These numbers are provider metadata, not calibrated correctness probabilities.
The source and exact spans are listed in the v2 preparation; raw answers and
complete distributions are preserved under `D01-jev` through `D04-jev`.

## Interpretation and limitation

The output separates the parser from the three domain-related decisions.
D01/D02 receive the same category. The author's provisional selection discussion
had called them policy candidates; `variant_behavior` is a different proposed
role within the intended Specification-centric domain surface. That difference
requires source/intent adjudication; it is not automatically a wrong answer.
There is no independent gold reference and no measured accuracy percentage.

A more concrete routing observation is now visible: low native confidence and
spread category probabilities do **not** trigger this frozen router. Its declared
rules check category/evidence consistency and action-specific premises, with no
numeric confidence threshold. Each returned known role plus `supported` is
consistent under that contract, so all four are retained without ordinary review.
This explains the observed route; it does not establish that the classifications
are correct. A coherent wrong answer could likewise be retained.

This is not a runtime/rule implementation failure under the frozen contract.
It identifies a possible mismatch with the broader goal of escalating Jev doubt.
Any future confidence/margin signal requires an explicit versioned policy and
validation; no post-hoc threshold or extra model call was introduced here.
The present data can motivate that design but cannot calibrate it.

## Artifacts and offline verification

`report.json` preserves exact labels/distributions/usage, decision/source binding,
all routing traces, transport counters, local timing and receipt identities.
`report.md` is a deterministic summary. Each request directory contains its exact
frozen request, durable attempt events, raw successful body with SHA-256, transport
and process execution records. `result-receipt.json` seals the complete published
inventory; the ignored `local-execution.json` is only a local preparation path.

Use the recorded local execution environment (Python 3.11.13 / Jev4Mellea 0.9.0):

```bash
../../.venv/bin/python -B specgraph_pr714_live_v1.py verify
```

This verifier requires the frozen execution runtime/provider fingerprints to
match. A different host/Python build may fail runtime qualification even when
the captures are intact; cross-host portable result replay is not claimed.
Synthetic no-network tests run in current-SDK CI, and the transport/CLI regression
suite also runs under the historical SDK environment. Local producer/receipt
hashes are integrity evidence, not signed or remote model attestation.

The preparation-level dispatch reservation is spent. Do not repeat this run or
silently fill the unused review slots. Future additional dispatch needs its own
explicitly authorized, bounded plan linked to these preserved observations.
