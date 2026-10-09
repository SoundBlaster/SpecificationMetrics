# Jev classification: evidence and insights

This ledger records what the experiments establish, what remains uncertain,
and the resulting engineering decisions. References are mostly model
annotations; they are not human-approved gold. Diagnostic development cases
must not be presented as a confirmation holdout. No entry authorizes autonomous
registry exclusions or changes to Specification counts (S/U).

## Findings

| ID | Insight and supporting evidence | Engineering consequence and limits |
|---|---|---|
| I01 | A previous diagnostic label in source context is label leakage. The [first smoke run](runs/2026-10-04-publication-site-069.md) contained an earlier policy diagnosis. | Freeze corrected inputs as a new version; do not reuse the old score as evidence for them. |
| I02 | More prompt variants do not by themselves improve classification. The [independent comparison](runs/2026-10-05-independent-reference/README.md) made 92 fresh requests without demonstrating improvement over baseline. | Fix the objective, rubric, reference source and family splits before tuning. A blind model reference is useful but remains distinct from human gold. |
| I03 | Task evidence, code facts and architecture intent answer different questions. [Context ablation](runs/2026-10-05-context-ablation/README.md) and the [intent-profile comparison](runs/2026-10-05-intent-profile-ablation/README.md) separate these inputs. Explicit project intent changed opportunity agreement from 4/8 to 7/8 on those examples. | Supply the SpecificationCore architecture goal explicitly rather than assuming a generic refactoring rubric. This is directional development evidence; changing the goal may require renewed reference adjudication. |
| I04 | Semantic suitability and existing ownership are different facts. The [RustJev run](runs/2026-10-08-rustjev-coreinfra/README.md) and [key-order run](runs/2026-10-09-state-key-order/README.md) incorrectly propose already-owned controls. | Use static/proven ownership as a separate filter before AI. Keep proof provenance. Semantic predictions alone do not prove ownership, liveness or permission to change S/U. |
| I05 | `concern_kind` and `opportunity` are orthogonal. Procedural policy examples sg-017 and sg-033 are recognized as policy but still excluded in the recent runs. | Score each axis, eligible recall, false exclusions and owned false positives separately. Do not infer eligibility from `policy`. |
| I06 | Formal response acceptance is not semantic accuracy. All 16 answers in the [RustJev diagnostic](runs/2026-10-08-rustjev-coreinfra/README.md) passed core validation while opportunity agreement was 4/8 and eligible recall 0/3. | Retain typed/numeric validation, independent semantic evaluation and human approval as distinct gates. |
| I07 | Joint questions can reduce overhead without changing observed categorical output. [Question grouping](runs/2026-10-08-question-grouping-persistent/README.md): all labels matched separate calls; reported token usage decreased 44.6%. Probabilities/confidence changed. | Consider a native batch API separately. This direct diagnostic does not add batching to RustJev or evaluate RustDecision routing; token savings do not establish dollar savings or universal quality equivalence. |
| I08 | Operational failure must remain separate from semantic abstention. Three [stopped grouping attempts](runs/2026-10-08-question-grouping-persistent/README.md) precede the complete run. | Preserve failed attempts, unattempted cases, planned denominators and consumed usage. Do not pool partial arms as complete evidence or turn transport failures into model `needs_review`. |
| I09 | A reusable HTTPS client completed the grouping experiment after per-call TLS failures. A pinned-address attempt still failed. | Connection reuse is a working strategy in this environment; neither the root cause nor provider reliability is established. Preflight success does not guarantee inference success. |
| I10 | Equivalent JSON representations did not preserve all observed labels. [State key order](runs/2026-10-09-state-key-order/README.md): sg-018 changed; insertion scored 3/8, canonical 4/8, eligible recall 0/3 both. Numeric changes reached 0.17 probability and 0.25 confidence. | Freeze serialization for reproducibility and add metamorphic evaluation. One sample per arm lacks a same-byte variability control; do not assert ordering as the sole causal mechanism or select thresholds from this sample. |
| I11 | Restoring historical insertion order did not restore historical 7/8 performance. Grouping also did not recover it. | Do not blame sorting or grouping for the whole regression. Provider path, date/checkpoint and envelope/question-order differences remain hypotheses, not findings. |
| I12 | Model names and valid responses do not establish reproducibility or calibrated confidence. Recorded runs share the returned name `jev-1.13.0`, with numerical and categorical differences. | Record requested/returned model, endpoint, time, exact inputs and digests. Calibrate fallback thresholds on adjudicated validation data and test on a held-out family split. |
| I13 | [Same-byte repeat controls](runs/2026-10-09-repeat-controls/README.md): 32/32 responses, zero categorical differences in 16 same-byte and 16 cross-arm comparisons per axis. Identical-wire probability/confidence deltas reach 0.09/0.14 for opportunity. The earlier sg-018 flip does not reproduce, and semantic recall remains 0/3. | Numerical stability is separate from label stability and semantic quality. The previous pair cannot establish deterministic key-order causality. Two repeats do not prove invariance or justify thresholds; stop repetition and inspect eligibility criteria before prompt tuning. |

## Current decision

Continue using Jev as an optional recommendation source. The current evidence
supports explicit architecture intent, formal ownership filtering and preserving
uncertainty. It does **not** support unattended opportunity exclusions, metric
writes or declaring a production classifier ready. No production defaults were
changed by the transport/grouping/order experiments.

## Next evaluation slice

The [frozen repeat controls](runs/2026-10-09-repeat-controls/README.md) now provide
a first baseline for numerical variability, without a reproduced label flip.
Before more prompt tuning, inspect the false-exclusion cases against explicit
eligibility criteria, keeping ownership and responsibility kind separate.
Any further inference needs a frozen hypothesis, fixed inputs and a bounded budget.
Adjudicate disputed sg-019 against the architecture goal before calling its
reference authoritative. A separate direct-provider/proxy comparison needs
provider-specific credentials, its own budget and an otherwise matched protocol.

New experiments should append an evidence link and explicit scope here;
contradictory results should revise a conclusion rather than disappear from the
ledger. Actual billed dollars and remaining credential balance must not be
inferred from reported token counts.
