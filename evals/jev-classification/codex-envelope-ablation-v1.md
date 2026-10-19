# Public Codex envelope ablation v1 — preregistered protocol

Date: 2026-10-19. Authorization: user **«Ок, делай»**, following the proposal to
vary only the generic Codex envelope while holding the API/model/effort and the
placement of the classification instructions constant.

## Question and scope

Does adding a generic programming-agent prompt change the four-axis
Specification classification, particularly recognition of an existing rule?
The earlier CLI observation changed provider route, effort, message placement
and the surrounding envelope simultaneously. This experiment controls those
factors within one API; it does not reconstruct the complete earlier CLI call.

Use the **public default instructions** from OpenAI Codex 0.156.1 commit
`b412ff32c417f855c2b2d1581b77058eed87c84b`, path
`codex-rs/protocol/src/prompts/base_instructions/default.md`. The immutable
[fixture](fixtures/codex-envelope-0.156.1/provenance.json) includes upstream blob
and SHA-256 bindings, Apache-2.0 license and NOTICE. **This public prompt differs
from the server-cached 18,037-character template of the earlier CLI run.** No
private account/model cache is copied or published. The result is evidence about
this public-template treatment, not attribution of the exact CLI failure.

## Controlled design

- Provider/endpoint: CoreInfra Responses,
  `https://hub.coreinfra.ai/openai/api/v1/responses`.
- Requested model `gpt-6-luna`, reasoning effort `medium` for both arms; no model
  substitution, effort fallback, tools, session history or new retrieval.
- Same 1024-output-token limit, 30-second socket timeout, 1 MiB response bound,
  strict four-question JSON Schema, `store: false`, `truncation: disabled`.
- Both arms place the canonical question instructions and criteria in Responses
  `instructions`. State remains in `input`. `minimal` sends those instructions;
  `codex_default` prepends only the pinned public template plus two newlines.
  Our common instructions remain the identical suffix in the same field.
- Use unchanged **baseline** tasks from the historical ordinary Luna preparation:
  **R01** existing workspace-allocation Specification; **R02** procedural
  `_check_transition` domain policy; **R03** `parse_write_authorization` mechanics.
  Source revision, target excerpts, helpers, unresolved facts and criteria stay
  unchanged. Old labels and results never enter either model request.
- Two fresh stateless requests per case/arm: **3 × 2 × 2 = 12 logical requests**.
  Each case receives AB and BA order; the second block reverses case order.
  There is no shared conversation or `previous_response_id`. This is a small
  screening experiment; two repeats are not a stability estimate.

The public Jev4Mellea categorical SDK renders the minimal request offline and
decodes captured response objects through a mock transport. The existing
`coreinfra_retry_run`/`coreinfra_transport` sends the frozen **actual** wire bytes.
The SDK's offline decoder request is not represented as the treatment request
actually submitted. SDK render compatibility with historical tasks is verified;
the live SDK environment must match the preparation environment. CI may replay
using the supported historical environment only if rendering/decoding agree.

## Budget, persistence and failure handling

Freeze producer closure, inputs, exact request bodies, order, model/settings,
reference and SDK inventory **before** inference. Reserve at most **36 network
attempts**, at most three per logical request using the existing verified-TLS
retry protocol. Retry only its enumerated transient TLS/incomplete-HTTP failures,
with identical bytes and durable attempt events. A post-send transport failure
can create ambiguous/duplicate billing; report it explicitly. HTTP errors,
refusal, schema/label failures and disagreements do not trigger semantic retries.
No hard currency cap is asserted; no new Sol call is planned.

Use a fresh single-use run directory. Persist the manifest before dispatch,
durable attempt ledger and response prefix during the run, then transport and
experiment receipts. Preserve incomplete cohorts. Provider JSON response objects
are retained; the reused transport does not retain the original response's
whitespace/byte representation or response headers. Never claim their exact raw
HTTP body identity or invent a header request ID. Invalid responses remain
failures, not manufactured `unknown` labels. No fact/registry/metric update.

## Preregistered interpretation

Primary narrow prediction: R01 ownership is `existing_specification` in **both**
minimal repeats and `unknown` in **both** public-envelope repeats. This pattern
would support a reproducible envelope-associated abstention on this control
under the tested API conditions; it would not prove the cause of the earlier CLI
answer or establish independent semantic truth.

If R01 ownership is identical across both arms in both repeats, this prediction
is not supported for the tested template/settings. Mixed results are inconclusive
and must be shown individually. Do not continue calling until a pattern appears.

Report all 12 planned responses and all 48 axis slots, each arm's 24 slots,
complete-view agreement with the unchanged empirical Sol comparator, consistency
violations from the existing named Specifications, ownership answers by repeat,
within-arm repeat agreement, reported tokens, elapsed attempt/backoff time and
transport/billing ambiguity. A partial/invalid cohort has no complete-cohort
quality conclusion. Comparator agreement is not semantic accuracy. Cost is
reported only if available; requested settings are not backend attestation.

Only the baseline Sol labels matching the unchanged evidence/rubric are reused.
They remain evaluation comparators, not accepted domain facts. No new Sol calls,
new annotations, large backend refactor or prompt/threshold optimization are
authorized by this experiment.

## Commands

From this evaluation directory, using the repository environment:

```sh
../../.venv/bin/python -B -m unittest -v test_codex_envelope_ablation_v1.py
../../.venv/bin/python -B codex_envelope_ablation_v1.py prepare
../../.venv/bin/python -B codex_envelope_ablation_v1.py verify
# Separate live action under the user authorization recorded above:
../../.venv/bin/python -B codex_envelope_ablation_v1.py run --live
../../.venv/bin/python -B codex_envelope_ablation_v1.py analyze
```

The commands never resume or overwrite a captured run. A new inference attempt
after exhaustion requires a new version/run and new authorization.

## Preparation failure lesson

The initial synthetic prepare/verify regression failed with `frozen experiment
differs`: the retry policy's tuple backoff becomes a list after JSON serialization.
Normalize the constructed policy through the same strict JSON representation
before comparing frozen inputs. The full synthetic round-trip test exercises
this boundary and guards against both false rejection and silent changes of
effort/budget. The correction preceded freezing and inference.
