# Jev/Luna agreement with the Sol top line

This is a new comparison contract, pinned before observing the 16 provider
responses. It consumes the source-checked 24-context Sol 6.1 Medium cohort and
the original paired preparation without modifying either. Sol is a model-specific
comparator, not independently established semantic truth or an upper bound.

## Matched run

- Exactly four targets × two evidence views × two providers = 16 logical calls.
- Jev `jev-1.13.0` through CoreInfra SystemOne and Luna Decision `gpt-6-luna`
  through CoreInfra Decisions, with the existing frozen native request bytes.
- Four categorical questions per request: role, evidence support, ownership and
  tool responsibility. The same state/profile/question definitions are supplied
  to both providers. No Sol outputs or annotation labels enter provider inputs.
- Reserve the existing maximum of 48 network attempts, at most three per request,
  only for the protocol's transient TLS/incomplete-body failures. Native or
  semantic disagreement does not trigger another inference attempt.

## Fixed measurements

For each provider: 8 planned responses, 32 all-axis slots and 16 primary-axis
slots (`concern_kind`, `ownership`). Per arm: four responses, 16 all-axis slots.
Report exact categorical agreement, individual mismatches, conflicts, native
contract failures and coverage separately. Unknown-to-unknown is agreement,
not proof of absence. Missing/invalid rows retain the planned denominators and
prevent complete-cohort comparison; they do not become wrong domain labels.

Report retrieval-minus-baseline agreement counts only when both arms have all
native-valid observations. This is descriptive, not a causal retrieval effect:
the four-target control cohort has a known baseline-sufficiency ceiling. Native
confidence values are not treated as calibrated probabilities of correctness.

The comparison verifies its frozen contract, Sol completion receipt and top-line
hash before execution/scoring. It uses the real local transport inspector,
including exact response bodies and retry ledger. On incomplete runs it retains
the captured-prefix row count separately; the existing complete-only inspector
cannot certify that prefix, so no unverified prefix is silently scored. Full
partial-prefix verification remains the separate #75 review issue.

Scoring v1's H1/H2 contracts remain unchanged and unqualified. This consumer
reports **agreement with Sol**, not semantic accuracy, accepted domain facts,
recommendations or SpecificationMetrics changes. Disagreements must be inspected
against the exact supplied view; Sol's answer alone does not prove an error.

## Execution and replay

From `evals/jev-classification`, use the repository virtual environment and
verified TB5 cache environment. The already authorized live run uses:

```bash
../../.venv/bin/python sol_top_line_comparison_v1.py --verify-contract
../../.venv/bin/python sol_top_line_comparison_v1.py --stage runs/2026-10-18-jev-luna-sol-comparison-v1
../../.venv/bin/python sol_top_line_comparison_v1.py --execute runs/2026-10-18-jev-luna-sol-comparison-v1 --live
../../.venv/bin/python sol_top_line_comparison_v1.py --score runs/2026-10-18-jev-luna-sol-comparison-v1 --output runs/2026-10-18-jev-luna-sol-comparison-v1/comparison.json
```

Never rerun/overwrite an existing live directory. Verification, unit fixtures
and scoring are offline; only explicit `--execute ... --live` accesses the key
and sends inference requests. Do not automatically re-execute these instructions
while reading this document.
