# Matched expression provider wires — 2026-10-12

## Status

**Prepared and validated offline. No inference performed.**

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
