# Contrastive live study v2 — 2026-10-13

## Current result

**Completed 48/48 accepted responses in 83.80 seconds, with no warnings,
rejections, retries or ambiguous POSTs.** Jev satisfies H1 on all four pairs in
both repeats; Luna satisfies three of four. Both fail joint withheld-context
H2 and satisfy H3; Jev's H3 includes precision sensitivity bounds. See the
[results and interpretation](results.md), [raw score](score.json),
[receipt](receipt.json) and [analysis summary](analysis-summary.json).

## Preparation

The user explicitly requested this new 48-query Jev/Luna run after merging
the [v2 runner](../../contrastive-mass-warning-v2.md). The manifest was frozen
offline on source commit `d5019263590e8ef4311b98bda952f749bf863c97`.

- Study: `contrastive_mechanics_policy_native/v2`.
- Acceptance policy: `jev-choice-mass-warning/v1`.
- Manifest SHA-256: `38725a1507a6f443dcd7169e39d742ce9e958b699e67dad4a3eca4df8e20b678`.
- Four authored mechanics/policy pairs and four withheld controls, two providers,
  two repeats: 48 planned logical requests, at most 144 attempts/potentially
  billable POSTs. Attempt count is not a dollar ceiling.
- Same reviewed model reference and exact wire bytes as the v1 study; no author
  proposals, reference labels or case/pair IDs enter provider state/questions.
- Jev `jev-1.13.0` and Luna `gpt-6-luna`, through their pinned CoreInfra endpoints.

This is a separate experiment, not a continuation of the spent v1 directory.
The [preflight record](preflight.json) describes preparation; the run-local
receipt and durable attempt ledger describe execution. No S/U metrics change.

## Offline replay

From `evals/jev-classification`:

```sh
python3 contrastive_decision_study_v2.py --run runs/2026-10-13-contrastive-warning-v2
python3 contrastive_decision_study_v2.py --inspect-results --run runs/2026-10-13-contrastive-warning-v2
python3 score_contrastive_decisions_v2.py --run runs/2026-10-13-contrastive-warning-v2 --output <new-score.json>
```

These modes do not read credentials or send requests. Output paths for the scorer
must be new. Never re-execute or overwrite a spent run directory.
