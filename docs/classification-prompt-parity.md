# Prompt parity before backend selection

Date: 2026-10-18. Status: planned correction to comparison methodology; no
additional inference is authorized or performed by this document.

## Observed framing difference

The [recorded Jev/Luna comparison](https://github.com/SoundBlaster/SpecificationMetrics/blob/0983b2468d7e4dd92b670d5be538a848629f3434/evals/jev-classification/runs/2026-10-18-jev-luna-sol-comparison-v1/diagnosis.md)
explicitly notes that Sol received a fuller source-evidence annotation brief.
The source code, architecture profile and category definitions were shared, but
the complete task instructions were not equivalent.

| Additional Sol instruction | Native task projection |
| --- | --- |
| Initial accepted unknown facts are unresolved inputs, not author gold | Classify unresolved facts; no equally explicit clarification of placeholder authority |
| Assess the target as a whole and separate mixed responsibilities from caller decisions | Classify primary responsibility; no equally explicit decision-unit guidance |
| Do not infer unavailable helper/type bodies, Intent or imported definitions | Missing-evidence guidance was less specific |
| Explain each axis and supply exact source witnesses | Finite-choice answers, without rationale or source-locator output |

These differences were documented but insufficiently prominent in short result
summaries. The observations establish agreement with the chosen Sol comparator
for the tested native pipelines, not an isolated model-quality effect or equal-
instruction cost/quality comparison. The measured role/support contradictions,
transport success and Sol's same-view repeatability remain observations; their
causes must not be attributed solely to model capability.

A richer rubric for reference annotation is legitimate. It can improve reference
quality, but its existence does not show that a cheaper classifier received all
the guidance needed to reproduce that reference. The Sol comparator is also not
independent semantic truth. Preserve the frozen runs and their limitations.

## Required comparison contract

Before using benchmark results to select a replacement backend:

1. Freeze one canonical **semantic instruction** document and rubric. Include
   decision-unit boundaries, placeholder authority, evidence/support semantics,
   handling of hidden helpers and same-decision ownership. Do not include author
   labels, target-specific expected judgments or prior model outputs.
2. Supply that semantic document to every compared backend, together with the
   exact same source/evidence view and architecture profile. Fix the accepted-fact
   representation within this experiment; changing it is a separate factor.
3. Render provider-specific envelopes from the canonical task. Record hashes of
   the common instructions, evidence, rubric, full rendered messages and adapter
   version. Audit content preservation before inference. Equivalent intent does
   not imply identical native request JSON.
4. Keep filesystem/tool restrictions and output-format instructions separate
   from semantic guidance. A local or CLI backend receives the frozen packet,
   not additional repository browsing, memory or chat history.
5. Compare the shared categorical fields under identical applicable consistency
   checks. Record optional rationale/citations and native distributions as
   backend capabilities; do not fabricate missing evidence or probabilities,
   or silently give one backend extra task guidance to produce them.
6. Pin model, reasoning setting where supported, route, context/output budgets
   and retry policy. Label the result as a tested configuration comparison;
   differing reasoning capabilities or API semantics remain declared factors.

Persist `prompt_parity_status` as verified, unverified or intentionally varied in
the future comparison contract. A report can retain unverified operational
results, but must not present them as an equal-instruction model benchmark.
This field is proposed; existing artifact schemas are unchanged.

## Next bounded experiment

First perform an offline parity audit of the canonical task and every rendered
adapter prompt. Then prepare a new versioned comparison on the explicit-owner
R01 and mechanics R03 controls, using the same full semantic guidance for each
selected backend. Ordinary Luna and Sol must also receive this common version;
do not reuse old observations as if they came from the new prompt condition.
Freeze selected configurations and request/attempt limits before execution.

If the effect of instruction detail is itself the question, use a separate
crossed design: every selected model receives both concise and full versions on
the same evidence views. Otherwise prompt richness remains confounded with model
selection. This is a plan, not a dispatch schedule or an inference request.

The previously proposed accepted-facts placeholder ablation remains a separate
diagnostic after parity is established. Do not simultaneously remove placeholders
and enrich instructions, then attribute any improvement to only one change.

## Interpretation

Use the same evidence budget and record actual input/reasoning/output usage,
end-to-end latency, coverage, abstention and consistency conflicts. Examine
disagreements against source and Intent where supplied. Then choose a backend
configuration meeting the quality floor at acceptable cost and latency.
Successful schema validation and repeatability alone do not establish semantic
correctness. Existing counting, registry authority and deterministic validation
rules remain unchanged.
