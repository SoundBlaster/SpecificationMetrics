# SpecificationCore intent-profile ablation — 2026-10-05

## Question

Does giving Jev the project's explicit SpecificationCore intent change its
classification of source sites, while the prompt, candidate code, model,
ownership evidence, and sample remain fixed?

## Frozen treatment

The only treatment is the `architecture_profile` context field. Its exact
content and SHA-256 are recorded in `study.json`. Arm `code` is the existing
code-only input. Arm `code_plus_architecture_profile` is that same JSON state
plus the profile. Both arms use the unchanged `baseline-v1` prompt and model
alias. Each arm is repeated twice, without cache replay, in alternating order.
The run receipt records each exact context hash and raw provider response.

## Pre-registered directional checks

- At least one pre-profile eligible policy should move from non-eligible to
  eligible in both repeats.
- Already-owned Specification cases `sg-018` and `sg-020` should remain
  excluded; profile context is not ownership proof.
- Mechanical controls `sg-031`, `sg-032`, and `sg-034` should remain excluded.
- All other movements and agreement with earlier labels are reported per case.

## Evidence limits

The inherited labels were produced before this profile existed. They answer the
previous opportunity question and are not human-adjudicated. Agreement against
them is a sensitivity diagnostic, not accuracy. This purposive eight-case
sample is not representative and is not a new holdout. Two repeats only show
consistency on these cases. A positive result would justify fresh independent
annotation under the new goal, not production rollout by itself.

## Reproduction

```bash
python3 evals/jev-classification/global_goal_ablation.py score \
  --study evals/jev-classification/runs/2026-10-05-intent-profile-ablation/study.json \
  --run evals/jev-classification/runs/2026-10-05-intent-profile-ablation/run-1/run.json \
  --output evals/jev-classification/runs/2026-10-05-intent-profile-ablation/summary-final.json
```

To plan, run `node evals/jev-classification/run_global_goal_ablation.mjs
--study <study.json>`; it makes no hosted requests. Hosted runs require
`TYPESAFE_API_KEY` and both `--allow-hosted` and a fresh output directory.
Never overwrite a prior receipt.

## Results

The run completed all 32 requests with no provider/contract errors and no
abstentions. Labels were identical between both repeats within each arm.
API-reported token usage was 62,108 total; no monetary cost is inferred.
Following review, the scorer was tightened so promotions require a valid
non-eligible baseline label and every mechanical control must explicitly be
`excluded`. The raw run is unchanged; `summary-final.json` is recomputed with
those stricter checks. The prior report is retained as `summary-pre-review.json`.

| Observation | Code only | Code + intent profile |
| --- | ---: | ---: |
| Agreement with inherited opportunity labels | 4/8 | 7/8 |
| Eligible-policy recall against inherited labels | 1/3 | 2/3 |
| Already-owned false positives | 2 | 0 |
| Mechanical false positives | 0 | 0 |

The profile promoted `sg-033` (workspace allocation) from `excluded` to
`eligible` in both repeats. It changed `sg-018` and `sg-020`, both already
expressed with Specifications, from `eligible` to `excluded` in both repeats.
All three mechanical controls stayed excluded. The same candidate remains
disputed: `sg-019` is `eligible` in the inherited annotation but remains
`excluded` under both arms. Its implementation was classified as mechanics by
Jev, while the prior reviewer called it policy. This should be adjudicated
under the new project goal before turning the profile into production policy.

These results support the profile as a useful context signal on these selected
examples. They do not establish accuracy: all inherited labels predate the
profile, are model-authored, and are not an independent gold set for the new
goal. The measured agreement gain is sensitivity evidence only.
