# Balanced BDD evidence diagnostic — results

**Status:** 12 valid fresh-context annotations, 48 decisions, independent and not adjudicated. No Jev/Luna requests; no metric effect.

## Design

This run executes the frozen 2×2 evidence study in [the preparation run](../2026-10-13-bdd-steps-balanced-factorial-preparation/). It covers four exact predicates from `BDDScenarioValuesSpec` and `BDDScenarioFieldsSpec`; each target-condition cell has three fresh subagent contexts. Each context saw one view of each target and one case from each evidence condition.

| Cell | Approved value contract | Explicit same-decision Specification link |
| --- | --- | --- |
| 01 | absent | absent |
| 02 | present | absent |
| 03 | absent | present |
| 04 | present | present |

“Absent” means that evidence group was omitted from that packet, not that it is absent from the source repository.

## Results

| Cell | Opportunity labels (n=12) | Responsibility labels (n=12) | Decisive coverage: opportunity / responsibility |
| --- | --- | --- | --- |
| 01 | `needs_review` 12 | `unknown` 12 | 0/12 · 0/12 |
| 02 | `eligible` 12 | `policy` 12 | 12/12 · 12/12 |
| 03 | `excluded` 12 | `unknown` 11, `policy` 1 | 12/12 · 1/12 |
| 04 | `excluded` 12 | `policy` 12 | 12/12 · 12/12 |

All three annotators agreed on the opportunity label in every target×cell group (16/16 groups). Responsibility labels were unanimous in 15/16 groups; the sole 2–1 split is `bdd-values-step-item` in cell 03 (`unknown` 2, `policy` 1). Full counts are in [aggregate-results.json](aggregate-results.json); raw retained outputs are in `annotations/`.

## Reading the three evidence effects

For this interpretation, **H1** is the contract effect, **H2** is the implementation-link effect, and **H3** is their combined effect. These are the directional questions in this diagnostic; they do not replace or rescore the earlier Jev/Luna H2 result.

- **H1 — contract evidence:** With no implementation link, adding the contract moves all 12 decisions from `needs_review / unknown` to `eligible / policy`. With the link present, opportunity remains `excluded`, while responsibility moves from 11 `unknown` and 1 `policy` to 12 `policy`.
- **H2 — implementation link:** Without the contract, adding the link moves opportunity from 12 `needs_review` to 12 `excluded`; responsibility stays almost entirely `unknown` (11/12). With the contract, the link moves opportunity from 12 `eligible` to 12 `excluded`, while responsibility stays 12 `policy`.
- **H3 — combined evidence:** The combined cell yields `excluded / policy` for all 12 judgments. In this packet, the contract makes the domain rule legible and the implementation link shows the same decision is already represented.

This is the intended orthogonal result: evidence of a rule’s meaning can identify responsibility, while evidence of existing ownership can exclude a duplicate opportunity. The link alone generally did not settle whether the step validity check was domain policy or representation mechanics.

## The one disagreement

In cell 03, one annotator called the step-item predicate `policy` because it sits in `BDDScenarioValuesSpec` and the `BDDPolicy` evaluation path. Two marked `unknown` because the packet does not define `step.valid`. The rubric question exposed here is whether direct placement in a named Specification and its policy composition is enough to infer primary responsibility when the domain validity contract is withheld. Treat this as an adjudication item; do not change the frozen rubric or historical H2 based on this run.

## Evidence quality and limitations

- Five attempts were excluded and preserved under `excluded-attempts/`: four failed exact quote validation; one annotator reported possible login-shell startup. Replacements produced the 12 retained contexts.
- All retained case IDs and task/state/rubric digests match their templates. Every retained annotation has nonempty rationales, allowed labels, and exact source-code evidence quotes on both axes. The two permitted input paths and `other_inputs_read: false` were verified for all retained outputs.
- Two raw outputs used `inputs_read` instead of the requested `input_files` key. Their values still list exactly the assigned files; the raw outputs remain unchanged and the deviation is recorded in the run receipt.
- These are fresh subagent contexts, not human gold labels. The underlying model identity was not exposed or verified; do not report this as Jev/Luna accuracy or statistical significance.
- The four predicates share one Specification lineage, and each annotator saw all four related targets. Balanced assignment prevents an annotator from seeing multiple evidence views of one target, but cross-target carryover remains possible.
- The result is descriptive for this small family. It does not change S/U, metric storage, production prompts, or the prior failed H2 result.

## Next step

Adjudicate the single cell-03 step-item disagreement with a reviewer who sees the frozen rubric and the two rationales, then decide whether the rubric needs a new version before any live Jev/Luna comparison.
