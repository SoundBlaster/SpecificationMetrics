# One live rich review on SpecGraph

Observed: 2026-10-18 16:43:47.464–16:43:58.032 UTC. Status: completed review,
remaining semantic uncertainty. This is one historical development view, not
an accuracy estimate, model ranking or production qualification.

## Result

The first-stage router selected only `R04-baseline-jev-coreinfra`, targeting
`safe_workspace_path` in `tools/product_workspace_next_moves_support.py`,
lines 55–62 at SpecGraph revision `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.

| Question | Jev | Ordinary Luna rich review |
| --- | --- | --- |
| Concern kind | policy | policy |
| Evidence support | insufficient | limited |
| Same-decision Specification | unknown | unknown |
| Tool responsibility | unknown | unknown |

Luna supplied an exact whole-line quotation of the target. Schema, echoed
request/task/decision bindings, source quote and target coverage checks passed.
The contradictory Jev tuple `policy / insufficient` became the coherent
`policy / limited`. No material role/ownership/tool disagreement was introduced.

The final status is **`needs_review`**: support remains limited. The review
identifies missing intent/proposal/specification context establishing this path
admissibility rule's domain purpose. It also records unavailable evidence of
same-decision Specification ownership and formatter/linter responsibility.
No facts, S/U, source code or merge gates changed.

Read the generated [Markdown report](../evals/jev-classification/runs/2026-10-18-structured-luna-review-live-v1/report.md)
and [machine-readable report](../evals/jev-classification/runs/2026-10-18-structured-luna-review-live-v1/report.json).

## What the model actually received

The independently answerable request reused the exact original state and four
question definitions, including the architectural purpose. It did not include
Jev's answer or the Sol comparator. The original state explicitly marks intent
documents as not supplied, accepted intent lookup as `not_done`, and ownership
and tool facts as unknown. Baseline retrieval is empty. The reported evidence
gaps therefore describe the bounded packet, not proof that those documents,
Specifications or tool rules do not exist in SpecGraph.

The response's rationale says the nonempty/path-form restrictions are evidence
of a path-admissibility rule, while absent intent limits confidence in its domain
purpose. This explanation is the model's statement, not a verified semantic proof.
The source quote matches the supplied excerpt; it does not establish the full
function's product contract or current-main behavior.

## Transport, usage and reproducibility

| Measure | Observation |
| --- | ---: |
| Planned and attempted logical reviews | 1 |
| Network attempts | 1 |
| Potentially billable POSTs | 1 |
| Ambiguous POSTs / retries | 0 / 0 |
| HTTP status | 200 |
| Returned model | gpt-6-luna |
| Requested reasoning | low |
| Exact request size | 20,606 bytes |
| HTTP operation time | 10.468120 s |
| Reported input / output | 4,016 / 739 tokens |
| Input cache writes / reads | 4,013 / 0 tokens |
| Input outside those cache buckets | 3 tokens |
| Reasoning within output | 240 tokens |
| Billed monetary cost | unknown |

Output was bounded to 1,024 tokens; response to 1 MiB; request to 64 KiB. Socket
timeout was 30 seconds, not a hard end-to-end deadline. Verified TLS and the
exact CoreInfra HTTPS Responses endpoint were used without redirects. The
existing exact-byte HTTP transport was reused, with one total attempt rather
than its optional retry setting. Timing covers HTTP transport, not SDK latency.

The preparation, request bytes, producer source closure and budget were frozen
before dispatch. A preparation-wide exclusive reservation and fsynced dispatch
ledger bind the one allowed POST; repeating the run or using another staged
directory cannot spend that preparation again. Credentials and headers are
not saved. HTTP-error bodies and responses reflecting the credential are dropped.
The successful safe HTTP-200 bytes are preserved with their digest. These are
local transport records, not remote execution attestation.

Artifacts:

- [Predeclared protocol](../evals/jev-classification/rich-review-live-pilot-v1.md).
- [Frozen preparation](../evals/jev-classification/runs/2026-10-18-structured-luna-review-preparation-v1/manifest.json).
- [Dispatch ledger](../evals/jev-classification/runs/2026-10-18-structured-luna-review-live-v1/attempts.jsonl).
- [Transport receipt](../evals/jev-classification/runs/2026-10-18-structured-luna-review-live-v1/transport-receipt.json).
- [Sealed result receipt](../evals/jev-classification/runs/2026-10-18-structured-luna-review-live-v1/result-receipt.json),
  SHA-256 `25bc5df1412d62b8daf1ee2d129bc9e3e39161c4816d486e5dea36f905eedcbd`.

`rich_review_pilot_v1.py --verify` reproduces JSON and Markdown without inference.
The saved-capture regression pins the result receipt. Existing policy CI also
checks synthetic successful, unresolved and incomplete outcomes, one-spend
reservation across run directories, TLS/HTTP failures, secret-reflection
rejection, capture tampering and fencing of model-controlled Markdown.
No GitHub review comment is posted by this runner.

## Interpretation and next controlled step

The live result confirms the configured endpoint/schema/identity/quote pipeline
on this input. It also exercises the desired unresolved branch: review exists
and is coherent, but uncertainty remains visible instead of becoming acceptance.
It does not establish general reviewer quality or repeatability.

The previous label-only Luna response on this view was `policy / supported`;
this rich review is `policy / limited`. The output contract and reviewer
instructions changed to request citations, rationale and missing evidence. One
observation under a changed protocol cannot establish accuracy regression or
isolate why the support judgment changed. Preserve both records; do not repair
the label or rescore the old run as a rich review.

Owner/tool gaps are optional for the current role-only action. They do not mean
that a Specification must be created or a linter installed. Review v1 preserves
all model-declared gaps as resolution blockers; future requiredness should be
scoped to the requested action so optional unknowns cannot become blanket
escalation requirements. This run remains unresolved independently because its
role support is limited. Clarifying optional gaps would not turn this saved
outcome into success.

Next: prepare a new versioned packet with verified callers and the relevant
intent/specification evidence at the same revision, explicitly separating
role-required gaps from optional owner/tool unknowns. Predeclare the hypothesis
that this evidence helps establish the rule's purpose and repeat only within a
new approved budget. Keep this first result unchanged.
