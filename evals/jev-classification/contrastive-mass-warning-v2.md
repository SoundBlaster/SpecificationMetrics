# Contrastive runner v2: bounded Jev probability warnings

Implemented policy: `jev-choice-mass-warning/v1`.
Study version: `contrastive_mechanics_policy_native/v2`.

The [precision investigation](jev-probability-precision.md) showed that one
observed 0.99 total had no classification consequence. V2 makes this a visible
warning instead of interrupting the semantic experiment.

The subsequent [authorized live study](runs/2026-10-13-contrastive-warning-v2/results.md)
completed 48/48 accepted responses. No warning was triggered in that sample;
the saved v1 failure and mock/boundary tests remain the evidence for that path.
Results, limits and hypothesis outcomes are recorded separately from the
implementation contract below.

## Acceptance

Only Jev `jev-1.13.0` Choice distributions with **three or four options** receive
the allowance. Every expected option must be present exactly once; probabilities
and confidence must be finite numbers in `[0,1]`; the returned choice must be a
returned maximum. Booleans, strings, missing options and non-maximum selections
remain invalid. Other models, option counts and Luna retain strict mass checks.

Arithmetic uses `Decimal(str(decoded_number))`, explicitly operating on the
decoded returned values. It does not reconstruct precision lost before the
response reached our decoder.

| Absolute difference from one | Result |
|---|---|
| At most `0.000001` | Accept without a numerical warning. |
| Above `0.000001`, at most `0.01`, within the Jev scope | Accept with `probability_mass_deviation`. Both `0.99` and `1.01` are included. |
| Above `0.01`, or outside scope and strict tolerance | Reject the whole result as unavailable; continue the schedule. |

Each warning retains its axis, total, residual, allowance and policy version.
Raw labels, probabilities and native confidence are preserved. No normalization,
confidence recomputation, inferred label or numerical retry occurs.

## Lifecycle and reports

`responses.jsonl` retains the provider response and the decoder's validation
metadata. Offline inspection recomputes the validation from the raw response and
rejects contradictory saved warnings or errors. Receipt counts are verified
against those results and the durable attempt ledger.

- A numerical warning is a usable accepted response.
- A structural/numerical answer failure is unavailable; remaining scheduled
  requests continue. The error receives a fixed rejection code, not arbitrary
  provider-controlled error text.
- Wrong returned model or question identities stop the run. Final transport,
  JSON decoding and HTTP failures retain the existing stop behavior.
- `receipt.completed` / `execution_complete` mean all 48 result rows completed
  without a fatal interruption. They do **not** mean 48 usable predictions.
- `operationally_complete` additionally requires 48 accepted, unambiguous
  responses. Missing/rejected/ambiguous results keep the original denominator.
- An interrupted or spent directory cannot be resumed or overwritten. A missing
  response alone never proves an unsent request.

H1/H2 use raw selected labels. Jev H3 reports the raw deltas and conservative
nearest-hundredth sensitivity intervals. A positive delta only counts as positive
H3 evidence when its lower bound is also positive on both axes. An interval
touching zero is unresolved. This is a frozen local sensitivity assumption,
not a verified Jev rounding guarantee. Luna's H3 computation is unchanged.

Both old and new runners share the same reviewed corpus and wire construction.
The v2 manifest changes the acceptance policy and H3 criterion explicitly and
binds all producer/decoder/scorer hashes. It is a new protocol version, not a
rescored claim about the incomplete v1 live study. No S/U writes occur.

## Offline operation

From `evals/jev-classification`:

```sh
python3 contrastive_decision_study_v2.py
python3 -m unittest -v test_choice_mass_warning.py test_contrastive_mass_warning.py test_contrastive_live_replay.py
```

The default CLI validates inputs and reports the policy and 48/144 request/attempt
budget. It reads no key, creates no files, sends no requests and explicitly
reports `manifest_frozen: false`.

To freeze an actual run offline, choose a **new, absent** directory:

```sh
python3 contrastive_decision_study_v2.py --prepare --run runs/2026-10-13-contrastive-warning-v2
python3 contrastive_decision_study_v2.py --run runs/2026-10-13-contrastive-warning-v2
```

Preparation freezes exact request bytes, producer/input hashes and the policy.
The second command only validates that manifest. Preparation refuses an existing
directory. Subsequent code/input changes require a new freeze before inference.

Live execution requires a separate explicit `--live --run <new-frozen-run>`
invocation and an authorized credential/budget: 48 logical requests and at most
144 attempts/potentially billable POSTs. No live invocation was made when
implementing v2. Attempt count is not a dollar ceiling.

After a run, replay and score without inference:

```sh
python3 contrastive_decision_study_v2.py --inspect-results --run <v2-run>
python3 score_contrastive_decisions_v2.py --run <v2-run> --output <new-score.json>
```

The scorer refuses an existing output path. V1 directories are rejected by the
v2 manifest validator, and the old runner cannot read v2 evidence. The original
decoder/runner/scorer and saved v1 live results remain byte-for-byte unchanged;
the v1 replay test verifies the historical reports still reproduce.

The v2 lifecycle verifier intentionally retains the v1 ledger validation rules
alongside the new completion semantics; changing frozen v1 producer bytes to
extract a common implementation would invalidate historical manifest replay.
Wire construction, reviewed-reference loading, transport, unit-number checks
and the core semantic summary are reused directly.
