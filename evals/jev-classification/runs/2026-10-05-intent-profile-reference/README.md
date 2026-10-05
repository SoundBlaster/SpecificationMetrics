# Independent reference for the SpecificationCore intent profile

## Question

Under SpecificationCore's stated system-wide intent, which of the eight source
sites used in the intent-profile ablation are remaining opportunities for
named Specifications, and what kind of concern does each site express?

The target is architectural fit for a Specification, not whether the current
code is correct or whether a refactor preserves behavior. A stable rule can
qualify with one use. Branch count, lines of code, and cyclomatic complexity
are not success criteria. Technical mechanics remain procedural when they do
not contain a separate product decision. Explicitly visible existing ownership
excludes a site from the remaining-opportunity count.

## Blind packet

`packet.json` contains the versioned project profile, label definitions,
review instructions, and eight bounded source contexts. It uses fresh opaque
case IDs and a shuffled order. It omits the prior labels, source candidate IDs,
family IDs, historical roles, and Jev responses. `manifest.json` records the
packet, source-study, and profile digests. The private case mapping is kept
outside the repository in the ignored `evals/jev-classification/results/`
directory and is not part of this packet.

The isolated reviewer was instructed to use only `packet.json` and returned
one label per case with source-based evidence and any missing context. No
hosted Jev calls were made by this annotation step. The raw labels are frozen
in `annotations.json`; `mapping.json` was opened only after those labels were
returned. `comparison.json` contains the per-arm confusion matrices and
per-case results, bound to the exact annotation and Jev run digests.

## Result

On these same eight cases, the code-only Jev arm agreed with the independent
reference on 4/8 opportunity labels; adding the intent profile agreed on 7/8.
Eligible recall moved from 1/3 to 2/3, precision from 1/3 to 2/2, and false
exclusions from 2 to 1. Both repeats produced identical labels. The profile
arm corrected the two already-owned Specification false positives and promoted
the workspace-allocation rule, matching the reference. It still missed the
acceptance-criteria coverage rule (`sg-019`).

Concern kind agreed on 7/8 cases in both arms. The remaining disagreement is
`sg-019`: the independent reviewer called it policy, while Jev called it
mechanics. That case needs human adjudication before changing the rubric.
These measurements are a promising directional result for the context profile,
but eight purposive examples and one model annotator cannot establish accuracy
or generalization.

## Scoring plan

After the labels are frozen, compare them with both Jev arms from
`2026-10-05-intent-profile-ablation`:

- Opportunity: eligible recall is primary; also report precision, false
  exclusions, coverage, per-case disagreements, and the raw confusion matrix.
- Concern kind: report per-case agreement and the confusion matrix separately.
- Compare the code-only and profile arms on the same cases. Treat any
  `needs_review` reference as an explicit abstention, not as a negative label.
- Show raw denominators and avoid population claims or significance claims; the
  eight examples were purposively selected for a diagnostic ablation.

## Evidence limits

This is one independent **model annotation**, not human-approved gold. The
annotator was not given Jev outputs or prior labels, but shared model biases,
pretraining knowledge, or recognition of visible source code cannot be ruled
out. The sample is small and purposive, and it was used in the Jev ablation;
this is not a fresh holdout or an estimate of project-wide prevalence. Any
disagreements that would affect the design should be adjudicated by a human
before changing a production classifier or metric.

## Status

Independent model annotation and descriptive comparison are complete. Human
adjudication of `sg-019` and broader evaluation on new families remain open.
