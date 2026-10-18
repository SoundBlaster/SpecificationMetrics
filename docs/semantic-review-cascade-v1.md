# Semantic review cascade v1

Date: 2026-10-18. Status: agreed direction and implementation contract;
the runtime cascade and PR publisher are not implemented by this document.

## Purpose

Use inexpensive, fast System One classification first. Give an unresolved
semantic decision one ordinary-Luna review. If uncertainty remains, publish it
explicitly as `needs_review`. These are semantic suggestions, not permission to
modify the accepted registry, S/U, source code or existing merge gates.

The [current provider comparison](../evals/jev-classification/provider-comparison-2026-10-18.md)
supports Jev as a provisional first stage and `gpt-6-luna` / low through
Jev4Mellea Responses as the reviewer. Backend selection is configurable; native
Luna Decision is a separate backend from ordinary Luna. No additional provider
fan-out or reasoning-effort increase is implicit.

```mermaid
flowchart TD
    A[Bounded source evidence and checked structural facts] --> B[System One]
    B --> C{Contract and required evidence satisfied?}
    C -->|Yes| D[Proposed classification]
    C -->|Semantic uncertainty| E[One ordinary Luna review]
    C -->|Transport or provenance failure| F[Analysis incomplete]
    E --> G{Review validated and uncertainty resolved?}
    G -->|Yes| D
    G -->|No| H[PR review: needs_review, reasons and missing evidence]
    E -->|Transport or provenance failure| F
    F --> H
```

## Routing rules and precedence

Bind each assessment to repository, revision, exact decision span, evidence
digest, rubric and category versions, requested action, and required axes.
Evaluate the following in order; record every applicable reason even when an
earlier row determines the route.

| Condition | Route and reason |
| --- | --- |
| Source identity/digest is invalid, response is missing/invalid, or transport fails | Mark `analysis_incomplete`; report operational cause separately. Do not turn failure into a semantic label or silently invoke another model. |
| A required definition or intent/proposal/spec document is known to be missing | Select `ordinary_review`, reason `missing_premises`, status `needs_review` (`review_status=not_run` until execution). Preserve the gap through any completed review; it cannot resolve by guessing or omission. An earlier operational failure instead selects `stop_incomplete` / `analysis_incomplete`, while retaining this semantic reason. |
| Existing SpecificationCore consistency rules reject the tuple | Ordinary review, `inconsistent_answers`. Preserve all original labels. |
| `concern_kind=unknown`, or evidence support is `insufficient` or `limited` | Ordinary review, `unresolved_role` and/or `insufficient_evidence`. |
| A required axis is unknown, or supplied trusted facts contradict a material claim | Ordinary review, `required_axis_unknown` or `evidence_conflict`. |
| A future calibrated uncertainty rule fires | Ordinary review, `calibrated_uncertainty`, recording calibration/configuration version. No numeric threshold is enabled in v1. |
| Otherwise | Retain a proposed classification, not an accepted fact or proof. |

Unknown owner/tool is not globally an escalation trigger. For a role assessment,
require a known role and supported evidence; owner/tool may remain unknown.
For a proposal to reuse a particular Specification or exclude a rule as already
owned, require that ownership and exact decision binding. For a proposal to
delegate to a formatter/linter, require an identified tool/rule and its binding.
Do not turn unknown ownership into a recommendation to create a new rule when
that recommendation assumes no existing owner.

The existing `RoleSupportConsistentSpec` and
`ResponsibilitiesCompatibleSpec` remain unchanged. Implement routing and
resolution as named SpecificationCore rules in separate modules, with traces;
do not replace the shared rules with duplicated procedural predicates.

## Ordinary review and resolution

1. Give Luna the same bounded evidence, architectural purpose, category catalog
   and semantic guidance. First obtain its independent assessment without the
   System One labels or Sol/reference labels. Compare the results afterwards.
2. Request a strict structured review envelope containing labels, evidence
   references with source quotations, missing evidence, and a short rationale.
   This is a new reviewer contract: the current label-only categorical result
   does not already supply those fields. Never synthesize native probabilities
   for ordinary models, and never equate model certainty with evidence support.
3. Validate response identity/schema, enum values, exact quote/span membership,
   required axes and the shared consistency rules. Source-quote existence is a
   structural check; it does not prove the model's semantic interpretation.
4. Clear a support-only inconsistency when the known role is unchanged, Luna
   supplies supported evidence, and all required validations pass. A material
   disagreement about role, ownership or tool responsibility remains
   `needs_review` unless checked structural facts settle that specific claim.
   Do not simply overwrite the first answer because the second model is larger.
5. Keep missing premises, remaining contradictions, invalid citations, refusal,
   truncation, budget exhaustion or absent review visible. An unavailable review
   is `not_run`/`failed`, never `resolved` or a clean scan. No recursive escalation
   or silent prompt/context expansion follows.

At most one logical ordinary review per candidate/evidence/configuration binding.
Reuse an exact matching receipt where available. Before hosted execution, freeze
the request/token/time budgets and approval scope. Keep transport retry policy
separate, bounded and explicit; ambiguous dispatches must not be silently retried.
This document authorizes no new paid run or retry policy.

## PR review output

Show counts of examined, proposed, escalated, resolved, unresolved, failed and
not-run decisions. Display per-request latency scopes and usage buckets; show
cost as unknown unless request-attributable billing or a labeled rate estimate
exists. Publish one idempotently updated report bound to the PR head revision.
Follow the repository's trusted workflow/credential boundary; a PR cannot grant
itself authority to invoke paid inference or publish an authoritative clean bill.

Every unresolved item names the exact code site, evidence revision/digest,
original System One labels, Luna review status/labels, routing rule/reason IDs,
remaining disagreement or missing premise, and the next required evidence or
human decision. Link both receipts and model/prompt/configuration identities.
Never fabricate an explanation for a native provider that only returned scores.

Example of a synthetic unresolved report, not an observed new model result:

> **Needs review — policy or mechanics remains unresolved.**
> Site: `path/to/module.py:42`, revision `<head>`, exact decision `<id>`.
> System One: `unknown / insufficient`. Luna: `policy / limited`.
> Missing: the intent/specification defining whether this branch controls
> publication or only renders a diagnostic. Supply that contract or adjudicate
> explicitly. No automatic exclusion or accepted S/U change was made.

Use informational mode first. Uncertainty is not a fabricated duplicate violation
or an implicit new merge blocker; existing authoritative gates keep their scope.
It must also not be rendered as zero findings or a complete successful analysis.

## Delivery and acceptance

1. **Offline routing:** typed context, named specifications, deterministic
   precedence, traces and replay. The current Jev sample selects one of eight
   views for review; owner/tool unknown alone selects none of the other seven.
2. **Review adapter:** versioned structured review and evidence validation,
   first with synthetic Responses payloads. Test unresolved role, limited
   evidence, material disagreement, missing required owner/tool, bad citations,
   refusal, invalid schema, stale evidence, timeout and exhausted budgets.
3. **PR report:** render resolved/unresolved/failed/not-run distinctly, verify
   head binding and idempotency, then use an explicitly bounded live pilot.
4. **Qualification:** independently labeled held-out families, same-input
   repeats and deliberate insufficient-context controls. Measure escalation,
   supported resolution, false resolution, missed escalation, latency, expense
   and human workload. Audit a separately budgeted sample of coherent first-stage
   proposals: a self-consistent wrong answer may never trigger escalation.

Acceptance requires retaining every unresolved or incomplete case in the report,
zero invalid-citation resolutions in deterministic regression cases, unchanged
accepted facts/S/U, and no inference during offline checks. Declare live quality
thresholds and sample size before qualification. A retrospective 32/32 selection
on four development targets does not qualify the cascade.
