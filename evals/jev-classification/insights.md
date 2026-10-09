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
| I14 | [Eligibility diagnosis](runs/2026-10-09-eligibility-diagnosis/README.md): reference explicitly allows single-use addressable/observable rules and qualifies mechanics; Jev's direct criterion uses reusable and unqualified technical enforcement. All three references acknowledge missing ownership context. | Low agreement remains measured relative to that model reference, but task mismatch and unresolved target boundaries prevent declaring each disagreement an objective Jev error. Align tasks before tuning or assigning causes. |
| I15 | [Source-boundary diagnosis](runs/2026-10-09-eligibility-diagnosis/README.md): sg-019 is a 44-line mixed function, while its reference selects an internal coverage predicate. Historical sg-017 consumer confirms findings affect readiness, but that consumer was omitted from Jev input. | Define target decision versus supporting code and avoid duplicate caller/helper opportunities. Context facts discovered afterward cannot retroactively change the old input or score. |
| I16 | [Matched-rubric diagnostic](runs/2026-10-10-rubric-alignment/README.md): both repeats move opportunity agreement 4/8 to 5/8, eligible recall 0/3 to 2/3 and concern-kind 7/8 to 8/8, but owned false positives 1/2 to 2/2. Fresh isolated model reference retains all prior labels. | Composite task alignment helps semantic discovery on these cases but fails the no-new-control-errors success criterion. Separate formal ownership from semantic suitability before rollout; do not claim a universal prompt win or individual-word causality. |
| I17 | [Source-bound construction replay](runs/2026-10-10-ownership-gate/README.md): exact historical source, symbol/span and resolved imports identify two direct constructions. Routing them before the semantic callback moves recorded aligned agreement 5/8 to 7/8, owned false positives 2/2 to 0/2; recall remains 2/3. No new inference. | Deterministic construction evidence can protect a semantic discovery rubric. Unknown construction stays on the semantic route. This development-set composition result does not change the old prompt hypothesis or establish production quality, runtime identity or whole-project ownership. |
| I18 | The same [audit](runs/2026-10-10-ownership-gate/README.md) runs the actual Rust scanner on all eight full historical files. Both already-constructed declarations and sg-033 have zero selected-range control-flow candidates. Rust already filters `inside_specification`, but names are syntactic and outer `FirstMatch.with_fallback` is not recognized. | Whole-declaration API examples and Rust branch candidates are different units. Zero discovery is not semantic exclusion; do not attribute this replay's improvement to the production filter. Define a shared target unit and import-identity contract before generalizing the classifier evaluation. |
| I19 | [Explicit target alignment](runs/2026-10-10-decision-targets/README.md): the Rust exporter binds 8/8 proposed expression targets to exact historical bytes; 4/8 match legacy branch anchors. The sg-019 target becomes its internal coverage predicate; sg-033 is a `require` argument. No inference or old-label transfer. | Distinguish target expression from supporting declaration and assembly controls. A changed boundary requires fresh annotation; anchor equality does not prove semantic equivalence. Shared target artifacts are implemented experimentally, while production scanner/classifier units and S/U remain unchanged. |

## Current decision

Continue using Jev as an optional recommendation source. The current evidence
supports explicit architecture intent, formal ownership filtering and preserving
uncertainty. It does **not** support unattended opportunity exclusions, metric
writes or declaring a production classifier ready. No production defaults were
changed by the transport/grouping/order experiments.

## Next evaluation slice

The [source-bound replay](runs/2026-10-10-ownership-gate/README.md) now protects
two existing constructions while preserving semantic recall. Define a shared
target unit for Rust discovery and semantic evaluation, with resolved import
identity and evidence provenance. The [explicit exporter](runs/2026-10-10-decision-targets/README.md)
now binds expressions and legacy anchors. Add bounded helper/data dependencies
and fresh target-specific annotation before the predicate-context study. New-family,
human-adjudicated confirmation is needed before production-quality claims.
Further inference requires a frozen hypothesis, fixed inputs and a bounded
budget; do not iterate until the diagnostic set happens to pass.

New experiments should append an evidence link and explicit scope here;
contradictory results should revise a conclusion rather than disappear from the
ledger. Actual billed dollars and remaining credential balance must not be
inferred from reported token counts.
