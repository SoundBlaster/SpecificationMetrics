# Matched expression provider wires — 2026-10-12

## Status

**Live run completed. 32/32 responses are native-valid; both providers fail the preregistered semantic criterion against the model reference.**

Preparation and validation were offline. Explicitly authorized inference ran on
2026-10-12 from 20:36:33.656772 to 20:37:35.173377 UTC (61.52 seconds).

The frozen `manifest.json` contains 32 logical requests: eight independently
annotated development expressions × Jev/Luna × two repeats. The retry budget
reserves at most 96 attempts (three per logical request), including potentially
ambiguous repeated POSTs. This is a maximum attempt count, not a dollar estimate.
The prior one-request Luna smoke is a separate experiment.

## Matching and isolation

Both APIs receive the exact same canonical UTF-8 JSON state text. Jev uses
`state` and a question map; Luna uses `input` and a question array. Question
instructions, labels and descriptions match exactly. Axes and choices are
sorted; each case's provider order reverses on its second repeat, and alternates
between successive cases. This is deterministic counterbalancing, not randomization.

The shared state retains the SpecificationCore architecture profile, exact target
and bounded source fragments. Canonical state and rubric hashes are frozen per
request. Author proposals, annotation labels, source-mapping judgments, request
IDs and the annotation instruction requesting prose citations are not added to
model inputs. The model questions remain those of the fresh expression rubric.
Using canonical JSON text in both APIs is a deliberate new serialization regime;
results must not be attributed to context alone or pooled with historical runs.

Reference/review/packet and comparison-plan hashes are frozen alongside transport
and analysis producer digests. Validation rebuilds every wire from those inputs
and refuses changed data, code, credentials-in-URL, model, endpoint or budget.
No API key is stored in the manifest. Live execution reads only `COREINFRA_API_KEY`.

## Native acceptance

`decision_choice_contract.py` accepts exactly the two requested Choice answers,
with the expected model and rubric labels, finite probabilities/confidence,
complete normalized distributions and a selected maximum (ties allowed).
Luna's named answer/probability arrays are decoded separately from Jev's maps.
Duplicates, refusals, missing options, NaN/infinity and numeric-label coercion
are rejected. No repair, rounding, missing-value defaults or inferred labels.
Provider-native confidence remains uncalibrated and is not compared as a shared
probability of correctness.

Native invalidity is an operational/protocol result, not a semantic `needs_review`
label. Offline inspection preserves the denominator of 32 planned requests,
missing rows, transport failures and invalid native responses. It whitelists
normalized answer fields and does not write S/U or score classifier quality.
A successful HTTP/JSON response alone is not accepted as a classification.

## Commands

Run from `evals/jev-classification`:

```sh
# Offline: verifies exact inputs/producers/wires; no provider calls.
python3 matched_expression_plan.py --run runs/2026-10-12-matched-expression-wires

# Explicit live execution of the frozen bounded plan; never rerun/overwrite.
python3 matched_expression_plan.py --run runs/2026-10-12-matched-expression-wires --live

# Offline native acceptance after live execution; no semantic scoring.
python3 matched_expression_plan.py --run runs/2026-10-12-matched-expression-wires --inspect-results
```

Live transport stops at its first non-JSON success/failure boundary according to
the existing transport runner. Native refusals or malformed answer payloads are
retained and classified during offline inspection; they do not trigger retries.
Transport socket timeout is not a whole-study deadline. Interrupted or partial
runs remain separate evidence, never silently replaced by another invocation.

## Verification and next step

Focused tests cover both native encodings, shared data/rubric equivalence, reversed
provider order, invalid probability/identity/type cases, stale manifests/results,
and preservation of missing/failed response rows. 50 focused tests passed before
publication. No Rust implementation or production defaults changed.

Next: execute this exact bounded plan once, inspect native acceptance, then score
each provider/repeat against the same frozen model reference. Keep raw results and
offline ownership-gate composition separate. The preregistered success criteria
remain in the [comparison plan](../2026-10-12-expression-reference/comparison-plan.json).
This small development set is not human gold or evidence of generalization.

## PR review correction: missing result is not an unattempted request

A process can stop after a POST and before saving its response. Inspection now
reports missing result rows separately from requests known to have started but
lacking results. A request is called unattempted only when the final receipt
confirms a complete attempt ledger, matches this manifest hash, and agrees with
ledger attempt/request counts. Otherwise an absent ledger event leaves attempt
status unknown. No automatic rerun is inferred from any missing row.

The manifest was re-frozen after this code correction while the study still had
no attempts, responses or receipt. The preceding manifest remains in Git history;
no hosted-run artifacts or historical experiment producer hashes were modified.

## Live comparison results

| Metric, per repeat | Jev repeat 1 | Jev repeat 2 | Luna repeat 1 | Luna repeat 2 |
|---|---:|---:|---:|---:|
| Native-valid / planned | 8/8 | 8/8 | 8/8 | 8/8 |
| Opportunity agreement | 5/8 | 5/8 | 5/8 | 5/8 |
| Concern-kind agreement | 7/8 | 7/8 | 6/8 | 6/8 |
| Eligible recall | 2/3 | 2/3 | 2/3 | 2/3 |
| False positives: excluded policy compositions | 2/2 | 2/2 | 2/2 | 2/2 |
| False positives: mechanics controls | 0/3 | 0/3 | 0/3 | 0/3 |
| Full preregistered repeat criterion | fail | fail | fail | fail |

Both providers are categorically stable across the two repeats (16/16 paired axis
answers available per provider; zero label disagreements). Jev's maximum numeric
variation is 0.09 native confidence and 0.07 option probability; Luna's observed
variation is zero. Two repeats do not establish general determinism or reliability.

### Where the labels disagree with the reference

- `expression-02` and `expression-04`: both providers return eligible/policy for
  already-composed Specification controls; reference opportunity is excluded.
- `expression-03`: both return excluded/mechanics; reference is eligible/policy.
- `expression-01`: Luna returns eligible/mechanics; reference is eligible/policy.
  Jev returns eligible/policy.
- `expression-05`, `expression-06`, `expression-08`: both correctly match the
  mechanics exclusions. Both also match `expression-07` as eligible/policy.

The strong criterion was at least 7/8 agreement on each axis, recovery of all three
eligible cases, no false positives on the excluded controls and stable repeated
labels. Both providers fail it. The error pattern suggests existing Specification
construction should be formally routed before semantic classification; it does
not prove a cause for the remaining false exclusion. No formal ownership gate
was applied in this report and raw predictions have not been rewritten.

### Transport and usage

All 32 logical requests completed with HTTP 200/native JSON: 32 network attempts,
32 potentially billable POSTs, no retries, no missing results, no ambiguous POSTs.
Requested/returned models are `jev-1.13.0` and `gpt-6-luna`.

| Provider | Reported input tokens | Reported output tokens |
|---|---:|---:|
| Jev | 25,066 | 1,472 |
| Luna | 21,518 | 0 |

Token accounting is provider-reported and may differ between native APIs. It is
not a dollar-cost comparison; actual billed amounts and key balance are unknown.

### Evidence and offline replay

- `attempts.jsonl`, `responses.jsonl`, `receipt.json`: original transport evidence.
- `native-validation.json`: normalized acceptance and preserved request status.
- `raw-provider-score.json`: per-provider/repeat confusion matrices, control
  strata, recall, repeated-label comparisons and evidence/scorer hashes.
- `score_matched_expressions.py`: offline scorer; the existing model reference
  and frozen criteria were used without new labels or threshold tuning.

```sh
# Use a NEW output path: the scorer refuses to overwrite an existing report.
python3 score_matched_expressions.py --run runs/2026-10-12-matched-expression-wires --output /tmp/matched-expression-score-replay.json
```

The saved report is reproduced by a CI regression without network calls. This is
a small development set with a model-authored reference, not human gold, held-out
performance or evidence that one provider is generally better. The state/profile
and serialization differ from historical whole-function studies; there is no
missing-context ablation, so context causality is not measured. No S/U updates.

**Next step:** inspect `expression-03`'s code/context/reference to distinguish a
reference disagreement from a missed domain rule, and separately replay the
existing formal construction proof for `expression-02`/`expression-04`. Preserve
the raw 5/8 results; do not retune prompts until this diagnostic is understood.
