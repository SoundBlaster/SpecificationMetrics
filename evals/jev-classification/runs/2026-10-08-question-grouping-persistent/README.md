# Paired native question-grouping comparison — 2026-10-08 UTC

## Result

Twenty-four verified native API requests completed in 17.108 seconds using the
same reusable HTTPS client. Both arms produced the same labels on all eight
cases for both axes.

| Measure | Joint request (8 calls) | Separate questions (16 calls) |
| --- | --- | --- |
| Opportunity agreement with model reference | 4/8 | 4/8 |
| Eligible recall | 0/3 | 0/3 |
| Eligible precision | 0/1 | 0/1 |
| False exclusions | 3 | 3 |
| Concern-kind agreement | 7/8 | 7/8 |
| Input tokens | 16,468 | 30,288 |
| Output tokens | 742 | 766 |
| Total reported tokens | 17,210 | 31,054 |

Grouping saved 44.6% of reported tokens on this set; it is not a measured dollar
saving because billed costs were not returned. No categorical decision changed.
Probability mass still differed by up to 0.10, and confidence by up to 0.15, so
this does not establish that grouping has no effect on numeric evidence.
Confidence remains uncalibrated; no acceptance threshold was chosen here.

The same three inline policies were excluded and the same already-owned
acceptance-criterion Specification was marked eligible. The historical 7/8
profile result therefore cannot be recovered simply by combining the questions
in this concrete controlled run. Do not generalize a null label difference from
eight purposive examples and one sample per arm to all Jev workloads.

## Frozen comparison

- Same eight cases and independent model reference as PR #25. Not human gold,
  not a fresh holdout; `sg-019` still awaits human adjudication.
- `jev-1.13.0` explicitly requested and returned in both arms.
- Same endpoint, persistent native HTTP transport, headers, code/profile state,
  instructions and criteria. Bodies use sorted keys, compact JSON and UTF-8.
- The sole planned treatment is joint versus separate `questions`. Canonical
  body hashes bind each response to the ordered plan. All attempts reference
  one byte-identical immutable plan via `plan_path`; duplicate contexts are not
  copied into each run directory. Local context/reference
  labels were never included in the model state.
- Seed 20261009 shuffles cases; four start with joint and four with separate;
  axis order alternates. This balances the order schedule, but cannot eliminate
  backend or temporal drift. One observation per arm is not a repeatability or
  immutable-model-checkpoint claim. Provider-side caching is not observable.
- Both arms use one reusable, certificate-verified `HTTPSConnection` client
  instance. No proxy, redirect following, automatic retries or local cache.
- At most 24 attempted calls per run, socket timeout 30 seconds, bounded 1 MiB
  responses. An observed 60,000-token guard is checked after each response; it
  does not enforce dollar spending or bound the tokens in a single call.
- Native response validation rejects duplicate JSON keys, non-finite numbers,
  wrong model/answer/option identities, invalid probability/confidence ranges,
  bad normalization and a selected label that is not a maximum. This dedicated
  evaluation transport does not invoke RustDecision rules and is **not a
  RustJev batch API** or proof of mixed-primitive batching.
- Native labels, including valid `needs_review` and `unknown`, are scored.
  Failed or unattempted answers remain unscored; denominators include all eight
  planned cases per arm. Reports distinguish missing cases from attempted errors.

## Failed preflights retained

Before the full run, three separately archived attempts stopped at the first
TLS/transport failure:

| Attempt | Attempted / planned | Successful calls | Stop |
| --- | --- | --- | --- |
| `../2026-10-08-question-grouping` | 3/24 | 2 | urllib transport error |
| `../2026-10-08-question-grouping-curl` | 5/24 | 4 | curl TLS error 35 |
| `../2026-10-08-question-grouping-pinned` | 3/24 | 2 | curl TLS error 35 |

Only simple mechanical controls completed in these attempts. Their partial
metrics do not support a grouping-quality comparison and are not pooled with the
completed run. No failure was silently converted to a semantic abstention.

Three unauthenticated HEAD checks per resolved address were used to choose a
pinned route, preserving Host/SNI and certificate verification. That attempt
still failed. Switching to a reusable client then allowed the full run to
complete. This is operational evidence for connection reuse in this environment,
not proof of the external TLS failure's root cause or future availability.

Across all four attempts: 35 attempted calls, 32 valid responses, three network
failures, and 62,861 reported tokens. This includes the overhead of operational
preflights. No provider error body, credential value or inferred dollar cost is
stored. The earlier PR #25's sixteen calls are outside these totals.

## Reproduce offline

From `evals/jev-classification`:

```bash
python3 -m unittest -v test_question_grouping.py
python3 question_grouping.py --run runs/2026-10-08-question-grouping-persistent \
  --transport persistent
python3 score_question_grouping.py --run runs/2026-10-08-question-grouping-persistent \
  --output /tmp/question-grouping-rescored.json
```

Dry-run validation and rescoring require neither a credential nor a network
connection. `manifest.json` verifies frozen input digests and records producer
and analysis implementation digests; `receipt.json` and `responses.jsonl` retain
execution evidence. The scorer preserves partial coverage and tests exact
reproduction of the completed and stopped reports.

A new live run requires a new directory/manifest, a private `COREINFRA_API_KEY`
and explicit `--live`. Existing recorded results cannot be overwritten. Do not
repeat the completed run to search for more favorable labels.

## Next factor

A separately budgeted paired experiment should compare historical insertion
order with canonical key order in the model's JSON state, retaining endpoint,
model, reusable transport, question grouping, prompts and semantic state content.
The historical JavaScript transport preserved insertion order and Rust sorts
object keys. This is a testable remaining difference, **not an established
explanation**. Do not tune the rubric or select thresholds on these eight cases
while diagnosing transport/context effects.
