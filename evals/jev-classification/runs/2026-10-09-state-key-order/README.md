# Paired state key-order diagnostic · 2026-10-09

## Question and frozen protocol

Does restoring historical state-object insertion order recover the earlier
intent-profile classifications? Do predictions remain unchanged for equivalent
JSON objects serialized in different key orders?

The frozen eight SpecGraph cases, architecture profile, two joint Choice
questions, root envelope order (`model`, `questions`, `state`), question key order,
minified whitespace, explicit `jev-1.13.0`, CoreInfra endpoint and reusable HTTPS
client are fixed. Only recursive object-key order inside `state` varies:
historical insertion order versus canonical sorted order. Four cases are
insertion-first and four canonical-first, with one fresh response per arm.
The plan stores exact UTF-8 wire strings and SHA-256 digests. Validation verifies
semantic equality, equal byte lengths, distinct state ordering, and the frozen
historical insertion representation; the sender uses those bytes directly.

## Observations

| Measurement | Insertion order | Canonical order |
|---|---:|---:|
| Successful / planned requests | 8/8 | 8/8 |
| Opportunity agreement with model reference | 3/8 | 4/8 |
| Eligible recall | 0/3 | 0/3 |
| Concern-kind agreement | 7/8 | 7/8 |
| Input tokens reported | 16,468 | 16,468 |
| Output tokens reported | 740 | 742 |

All 16 responses completed in **12.003 seconds**, including one successful
unauthenticated TLS preflight. No inference retries occurred. Total reported
usage is **34,418 tokens**; this is not a dollar charge or remaining balance.
The token guard is checked after each response, not a pre-billing cost bound;
the provider key has a separate spending cap. All returned model identifiers
were `jev-1.13.0`; an identifier does not prove an immutable checkpoint.

Opportunity labels differ on **sg-018**, the already-owned pre-SIB FirstMatch:
`eligible` for insertion and `excluded` for canonical. The independent reference
is `excluded`. The other already-owned example, **sg-020**, remains incorrectly
`eligible` under both arms. All three reference-eligible procedural examples
remain `excluded`. Concern-kind labels do not change. The largest paired
per-label probability change is **0.17**, and confidence change **0.25**.
Neither number is calibrated correctness or a threshold recommendation.

## Interpretation and limits

1. Restoring insertion order **did not recover historical 7/8 agreement**.
   State sorting alone is therefore not a demonstrated explanation for that
   historical difference. Earlier provider, envelope/question ordering and date
   differences remain unisolated.
2. A semantics-preserving transformation failed observed label invariance on
   one pair. With one sample per arm and no same-byte repeated control, we cannot
   separate ordering effects from ordinary sampling or backend variability.
   This is a robustness warning, not proof of deterministic order causality.
3. Static ownership evidence should remove proven existing Specifications from
   the remaining-opportunity pool before semantic evaluation. AI classification
   cannot establish ownership or authorize registry/S/U changes.
4. Recognizing `policy` does not imply recognizing an opportunity. The two axes
   remain separate, and typed/numeric response acceptance does not establish
   semantic correctness.
5. Eight purposive diagnostic cases and one blinded model annotator are not
   human-approved gold or an independent holdout. The disputed `sg-019`
   policy/mechanics boundary still needs human adjudication. No project-wide
   accuracy, statistical significance or production readiness is established.

No production prompt, confidence threshold, classifier routing, registry or
metric count changed. No extra paid repetition was made to select a favorable
result. See the [insight ledger](../../insights.md) for cumulative conclusions.

## Artifacts and offline reproduction

- `manifest.json`: fixed protocol, input and implementation digests.
- `plan.json`: exact request bytes and planned pairing.
- `responses.jsonl`: sanitized validated answers and wire receipts.
- `receipt.json`: attempts, stop/completion state, timing and reported usage.
- `summary.json`: reference agreement and paired numerical differences.

From `evals/jev-classification`:

```bash
python3 state_key_order.py --run runs/2026-10-09-state-key-order
python3 -m unittest -v test_state_key_order.py
python3 score_state_key_order.py --run runs/2026-10-09-state-key-order --output /tmp/state-order-summary.json
```

These commands are offline. The scorer refuses to overwrite its output. The
live sender requires explicit `--live` and `COREINFRA_API_KEY`, refuses to
repeat a directory with receipts, stops on the first operational error, caps
responses at 1 MiB and uses a 30-second socket timeout. That timeout is not a
hard total-run deadline. CI validates the frozen plan and report without keys
or inference. Operational errors and unattempted cases remain unscored with
planned denominators; partial runs cannot claim full label invariance.
