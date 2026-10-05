# GPT-6 Luna reasoning-effort comparison

## Question

Does `medium` reasoning effort produce better independent decisions than
`low` on cases where Jev reported low confidence?

## Method

The selection rule was fixed before running Codex: include a case if any Jev
`opportunity` or `concern_kind` confidence was below `0.50` in either arm or
repeat. It selected five of the eight ablation cases: `sg-017`, `sg-018`,
`sg-019`, `sg-020`, and `sg-033`. TypeSafe documents lower confidence as a
signal for review; `0.50` is our operational cutoff, not a calibrated error
probability or a provider-recommended threshold.

Both runs used the same shuffled packet, rubric, output schema, and exact
prompt. Each was a fresh, ephemeral Codex CLI process using `gpt-6-luna`, with
read-only sandboxing and no repository supplied as its workspace. The prior
independent reference labels and Jev outputs were not in either prompt. The
outputs were frozen before the case mapping was opened.

## Results

| Measure vs independent model reference | Luna Low | Luna Medium |
| --- | ---: | ---: |
| Opportunity agreement | 3/5 | 2/5 |
| Eligible recall | 3/3 | 2/3 |
| Eligible precision | 3/5 | 2/4 |
| False exclusions | 0 | 1 |
| Concern-kind agreement | 5/5 | 3/5 |

Medium changed the opportunity decision only on `sg-019`, from eligible to
excluded. That matches Jev's mechanics interpretation, but conflicts with the
independent reference's policy/eligible label. Medium also changed concern
kind on `sg-018` and `sg-019`. Both efforts called the already-owned
Specification cases `sg-018` and `sg-020` eligible, despite the rubric's
ownership exclusion. This suggests the ownership evidence/rubric is the more
useful target for improvement than simply raising reasoning effort.

Low agrees with the independent reference on more labels in this five-case
subset, but this does **not** show that Low is generally better: there was one
run per effort, the reference is another model rather than human-adjudicated
gold, and the cases were selected because Jev confidence was low. The results
do not generalize to the remaining candidates.

Codex reported 27,408 tokens used for Low and 27,383 for Medium. Those nearly
equal counts from one short run each are not a cost or efficiency comparison.

## Artifacts

- `packet.json`, `prompt.txt`, and `output-schema.json` freeze the inputs.
- `low.json` and `medium.json` preserve the raw final annotations.
- `mapping.json` links the opaque cases after both runs were frozen.
- `comparison.json` records per-case labels, Jev confidence values, confusion
  matrices, and provenance. `manifest.json` records hashes and invocations.

## Limits

This is a small diagnostic, not an effort-setting benchmark. Confidence-based
selection is conditional and can produce a harder sample than ordinary use.
The next useful improvement is to strengthen the prompt's treatment of visible
Specification ownership and adjudicate `sg-019` before drawing conclusions
about model settings.
