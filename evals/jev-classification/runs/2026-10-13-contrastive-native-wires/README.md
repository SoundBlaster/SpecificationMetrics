# Frozen contrastive native study — 2026-10-13

## Current state

**48 native requests are frozen and validated offline. Live inference has not
started. No provider scores, actual token usage, dollar cost or S/U changes.**

The [manifest](manifest.json) binds the unchanged
[reviewed reference](../2026-10-13-contrastive-preparation/reference-review.json),
raw independent annotations, exact packet, logical schedule, criteria, and
producer/decoder/scorer hashes. The reference remains a model annotation of
authored development scenarios, not human gold. Its 12/12 agreement with author
hypotheses does not measure Jev or Luna accuracy.

The original preparation plan/template/receipt are historical pre-annotation
snapshots. The review records their subsequent acceptance; this separate native
manifest records completion of the wire-freezing stage. No historical artifact
or raw label was overwritten. Manifest `status` describes the freeze snapshot;
after execution the run-local receipt/ledger describe what actually happened.

## Design and budget

- Four pairs, each with opposed full-context mechanics and policy members sharing
  identical target expression bytes; four additional unique withheld controls.
- 12 states × 2 providers × 2 repeats = **48 logical requests**.
- Jev `jev-1.13.0` at CoreInfra `/typesafe/api/v1/systemone`; Luna `gpt-6-luna`
  at `/openai/api/v1/decisions`, on the verified HTTPS origin.
- Same canonical UTF-8 state text and question rubric in both APIs. Different
  native envelopes; no pair/case identifiers, reference labels, author proposals,
  annotation instructions or preceding answers enter the provider payload.
- Each case's provider order reverses on repeat two; case orders and all wire
  bytes are fixed before inference. Both axes are Choice questions per request.
- At most **3 attempts per request / 144 attempts total**, including the first
  attempts. This also bounds potentially billable POSTs, **not dollars**.
  Pricing, failed-call billing and remaining credential balance are unknown.

The runner reuses the strict native decoder and TLS retry transport. It has its
own fixed 48-request contract because changing the older 32-request runner would
invalidate that study's frozen producer digests. No old runner or saved result
was modified.

## Offline reproduction

From `evals/jev-classification`:

```sh
python3 contrastive_decision_study.py
python3 -m unittest -v test_contrastive_decision_study.py test_score_contrastive_decisions.py
```

Default execution validates reference readiness, preparation replay, exact wire
bytes and all implementation/input hashes. It reads no credential, creates no
attempt/output artifacts and sends no requests. CI runs only this mode and mock
tests. The [local validation receipt](offline-validation.json) records the 100
passing focused checks and pinned historical source replay. It is offline
evidence, not a provider result or CI status.
`--prepare --run <new-directory>` exclusively creates a new manifest;
the checked-in run is already prepared. Never regenerate a manifest after
inference to make changed inputs or implementation appear to match.

## Separate live execution

Live execution remains the next **separately requested** experiment. This
preparation does not authorize it. The explicit command, after the bounded run
is requested and a credential is available, is:

```sh
python3 contrastive_decision_study.py --live
```

The runner reserves the worst-case attempt budget, verifies frozen inputs before
each request, creates an exclusive run lock/attempt ledger, and fsyncs events
before POSTs. It refuses any run with existing output evidence. It retries only
the previously frozen transport conditions, using identical bytes; certificate,
HTTP and native-contract failures are not silently retried. It stops on a final
transport/decode/native failure, preserving the original denominator of 48.

Outputs are run-local `attempts.jsonl`, `responses.jsonl`, `receipt.json`.
They retain timestamps, returned native bodies/usage, error classes, request/wire
identities, attempts and ambiguous POSTs. Arbitrary HTTP error bodies and
credentials are not retained. Interruption produces an incomplete receipt when
possible; a crash without one leaves execution status unknown. Missing result
rows alone never prove that inference was not sent. Do not resume or overwrite
the directory: a further attempt needs a new recorded run and explicit budget.

## Offline scoring after execution

```sh
python3 contrastive_decision_study.py --inspect-results
python3 score_contrastive_decisions.py --output runs/2026-10-13-contrastive-native-wires/score.json
```

The scorer binds the exact response/attempt/receipt/manifest and reference/review
hashes, decodes raw responses again, and refuses stale or contradictory evidence.
It never sends requests, repairs labels or applies the ownership gate.

| Endpoint | Fixed criterion, per provider and repeat |
|---|---|
| H1: distinguish complete roles | All 4/4 full pairs correct on both axes; show 4-case eligible recall and 4-case mechanics false positives |
| H2: abstain without context | All 4/4 unique withheld controls return `needs_review / unknown` |
| H3: directional probabilities, secondary | Both P(eligible) and P(policy) are strictly larger for the policy member in at least 3/4 pairs; ties fail |
| Repeat stability, separate | 24/24 paired case/axis answers available per provider, no categorical disagreement |

Reports contain both members and the withheld control of every family, per-axis
confusion on the eight full-context cases, numeric variation, missing/invalid
responses, and uncertainty. No primary pooled 12-case accuracy hides role or
abstention errors. H1/H2/H3 are independent claims, not one combined success score.

`criterion_met` records the observed endpoint arithmetic. `supported` additionally
requires all 12 cases in that provider/repeat to be usable and a complete
attempt ledger. A native-valid result following an ambiguous POST remains visible
but cannot support the completed-test claim. This strict diagnostic convention
does not assert that a duplicate execution necessarily changed the answer.
Missing, invalid and ambiguous outcomes never become semantic `needs_review` and
never shrink planned denominators. A whole-study completion claim additionally
requires all 48 unambiguous native-valid results and a completed receipt.

## Limits and next step

Four authored development pairs with explicit contracts and explicit withheld
context are easier than recovering intent from an arbitrary repository. Code
names, types, contract prose and effects change together, so a successful pair
contrast cannot identify which context component mattered. The reference is one
fresh model annotation plus nonblind integrator review. Two repeats do not
establish statistical superiority, calibrated confidence or generalization.

**Next step:** run the frozen 48-request experiment when explicitly requested,
then publish raw outcomes and score all preregistered endpoints once. Preserve
failed hypotheses; no production defaults, registry dispositions or S/U writes.
