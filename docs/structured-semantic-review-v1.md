# Structured ordinary-Luna review v1

Date: 2026-10-18. Status: offline request preparation, captured Responses adapter
and provisional resolution policy implemented. No network executor, live rich
review, budget enforcement service or PR publisher is enabled by this module.

This implements delivery step 2 of the [cascade contract](semantic-review-cascade-v1.md)
on top of the [first-stage router](semantic-review-cascade-v1.md#implemented-offline-routing).
The consumer lives in `evals/jev-classification/structured_semantic_review_v1`.
No new dependency, historical producer or accepted-fact contract is introduced.

## Request and identity

`prepare(context, state_json=..., questions_json=...)` only accepts a validated
first-stage context routed to `ordinary_review`. It checks the captured state
digest, original questions/configuration digest and category catalog. It requires
the architectural goal, repository/revision, decision ID and target source span.
Source fragments come from `source` objects inside that same captured state;
their excerpt digest, revision and line count must match their metadata. There
is no separately supplied quote corpus that could be swapped behind the state
digest. Review v1 requires the four named Jev-style question objects; native
Luna's different question-list wire format needs an explicit future conversion.

`request_body(prepared)` builds a strict-schema Responses request for
`gpt-6-luna`, reasoning `low`, output cap 1,024, `store=false`, `stream=false` and
disabled truncation. The configured future endpoint is CoreInfra's exact
`https://hub.coreinfra.ai/openai/api/v1/responses`. Request rendering does not
contact it or read credentials. It preserves the original state and question
guidance; first-stage answers and Sol labels are not copied into the request.
The task digest additionally binds the reviewer instructions/settings, known
missing premises and extracted fragments. The response must echo both that
task digest and the original decision-binding digest.

This is a separate rich-review protocol. Jev4Mellea 0.8.0's categorical Responses
provider returns labels, not citations/rationales. The new consumer does not
invent those fields, call private SDK methods, or reinterpret previous label-only
responses as rich reviews. Actual endpoint/schema compatibility and semantic
quality still require a separately authorized bounded live pilot.

## Review envelope

All fields are required and unknown fields are rejected:

| Field | Meaning |
| --- | --- |
| `contract` | `specmetrics.structured-semantic-review/v1` |
| `task_sha256` | Prepared review task identity |
| `decision_binding_sha256` | Original decision/evidence/configuration identity |
| `labels` | Unchanged four-axis categories; no synthetic probabilities |
| `citations` | Axis, fragment ID, absolute start/end lines and exact whole-line quote; at most 16 |
| `missing_evidence` | Explicit unresolved evidence IDs/descriptions; at most 16 |
| `rationale` | Nonblank explanation, at most 2,000 characters; a model statement, not proof |

`inspect(prepared, raw_bytes, captured_request_sha256=...)` verifies the supplied
request digest, response model and completed envelope, strict JSON and schema,
and echoed task/decision digests. The caller-supplied request identity is not
authenticated transport evidence. There is a 1 MiB response parsing limit;
duplicate JSON keys, nonfinite values, ambiguous messages, refusals and incomplete
responses remain explicit failures instead of becoming a classification.

## Citation and resolution rules

Concrete policies are named SpecificationCore classes, each in a separate file.

- `CitationMatchesSourceSpec`: quote bytes represented as text must match the
  exact declared whole-line span within a supplied fragment. No fuzzy matching
  or newline repair is performed. This verifies an excerpt locator, not the
  current checkout, code behavior or semantic interpretation.
- `MissingCitationCoverageSpec`: a known role needs a citation to `target/source`;
  positive owner/tool claims need citations on those axes. An exact quote from a
  similar retrieved fragment alone cannot establish the target's role.
- `MaterialDisagreementSpec`: changing or losing a previously known role,
  owner or tool claim remains unresolved unless checked input evidence settles
  that specific claim. Moving from unknown to a supported role is not itself
  a disagreement. Known claims are preserved in the report.
- `UnresolvedRoutingSpec`: reuse the first-stage consistency, required-axis,
  action-binding and evidence-conflict policies on the reviewer's labels. A quote
  does not become the exact Specification/tool binding required by those rules.
- `MissingReviewEvidenceSpec`: neither a supported label nor omitted model gaps
  can erase original missing premises. New gaps also prevent resolution.
- `ReviewResolvedSpec`: all required checks must pass for a `resolved_proposal`.
  This resolves an advisory classification only; it accepts no canonical fact.

Empty citation lists do not claim locator verification. Both quote membership
and required coverage are reported. A plausible explanation or exact quote is
never reported as verified semantic correctness. Existing checked claims remain
caller-established premises; the model cannot create or upgrade them.

## Outcomes and evidence

| Status | Review status | Meaning |
| --- | --- | --- |
| `resolved_proposal` | `completed` | All advisory resolution checks pass; disposition remains `proposed_not_accepted`. |
| `needs_review` | `completed` | Review exists, but conflicts, gaps, citations or required bindings remain unresolved. |
| `analysis_incomplete` | `not_run` or `failed` | Missing execution, exhausted budget, transport/refusal/truncation, malformed response or identity mismatch. Disposition is `needs_review`. |

Reports preserve the original assessment and routing trace, complete valid
review envelope, all resolution findings/traces, both binding digests, request
and response digests, returned model and reported usage. Monetary cost remains
null without a billing observation. `transport_verified=false`,
`semantic_correctness_verified=false`, `automatic_fact_acceptance=false`,
`write_authority=false` and `metric_effect=none` are explicit. Provider usage is
metadata, not inferred price or an attested execution count.

The inspector performs zero hosted requests. Future execution must separately
enforce one logical review per candidate/evidence/configuration binding, approval
scope, durable dispatch receipts, token/time/byte limits, and explicit TLS retry
policy. Passing `execution_status` to this offline consumer does not enforce a
runner's budget. No silent retry, fallback or prompt expansion occurs here.

## Offline checks and next delivery

```bash
cd evals/jev-classification
../../.venv/bin/python -W error -m unittest -v test_structured_semantic_review_v1.py
../../.venv/bin/python -W error -m unittest -q test_recommendation_policy_v1.py test_retrieval_fact_adapter_v1.py
```

The current 26 new tests cover preparation binding, architectural purpose,
category drift, independent request contents, quote/span/coverage checks,
material disagreement, missing evidence, structural-premise resolution, schema,
refusal/truncation, stale identities, budget/not-run reporting and invalid JSON.
The real selected SpecGraph R04/baseline evidence view prepares without new
inference. Its structural resolution test uses a hand-authored synthetic response;
this is not a new Luna quality result. A saved historical label-only Responses
body is deliberately rejected as a rich review. Existing policy CI composes this
suite through `unittest.load_tests`; workflow files are unchanged.

Next: render a revision-bound PR report for all three statuses and prepare a
bounded one-review execution with a dispatch receipt. Publish or invoke hosted
inference only within separately established authorization and budget.
