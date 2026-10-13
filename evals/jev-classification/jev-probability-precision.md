# Jev probability precision: a warning, not a study-wide stop

Date: 2026-10-13. Scope: the saved contrastive development run; no new inference.
This is a post-results diagnosis and a proposed next-version acceptance policy,
not an amendment to the frozen experiment.

## Conclusion

The observed total of **0.99 is a small probability-mass discrepancy with no
observed classification consequence**. It is one percentage point of total
mass, not an estimate that Jev makes 1% classification errors. Stopping the
entire study on this discrepancy was disproportionate to its effect on our
label-based questions.

The strict runner followed its frozen rule correctly. The rule itself assumed
more numerical precision than the provider's current schema promises. Preserve
that historical result and use a bounded warning policy in the next version.
Provider confirmation of the exact rounding mechanism is useful, but need not
block this local compatibility decision.

## Primary sources

Checked on 2026-10-12 UTC / 2026-10-13 MSK:

| Source | Evidence | Limit |
|---|---|---|
| [Choice guide](https://docs.typesafe.ai/primitives/choice) and [HTTP reference](https://docs.typesafe.ai/api) | Describe the selected option as the maximum and the distribution total as one. | Do not define a rounding tolerance. |
| [Official SDK response schema](https://docs.typesafe.ai/sdk/python/api/types/responses) | Describes the total as approximately one. | Does not quantify the approximation. |
| [Live OpenAPI](https://api.typesafe.ai/openapi.json), `ChoiceAnswer.probabilities` | Also describes an approximate total. API schema version observed: `0.2.0`; response SHA-256 `a191f8a7df6bd6fedced8120dd0fd106f88575d1d1c8360d08900a6c7c0360d5`. | No documented decimal precision or serialization mechanism. |
| [SDK issue #15](https://github.com/typesafe-ai/typesafe-sdk-python/issues/15) | An integration author reports near-tie winner inconsistencies and one 0.99 total for `jev-1.13.0`. A [project contributor acknowledges an API issue](https://github.com/typesafe-ai/typesafe-sdk-python/issues/15#issuecomment-5838757287). | The acknowledgement concerns the reported consistency problem; it does not explain our specific response. |

This supports a bounded compatibility allowance, but does not establish that
Jev independently rounds all values to two decimals, or whether CoreInfra
changes them. No direct-versus-proxy experiment was performed here.

## Saved-answer survey and sensitivity

[The analysis artifact](runs/2026-10-13-contrastive-native-wires/probability-precision-analysis.json)
binds the calculations to the original manifest, responses, ledger, receipt,
strict validation and score via SHA-256. Each provider returned 21 responses,
each with two distributions:

| Check | Jev | Luna |
|---|---:|---:|
| Distributions inspected | 42 | 42 |
| Exact decimal total of one | 41 | 42 |
| Exact decimal total of 0.99 | 1 | 0 |
| Values outside the numerical hundredth grid | 0 | 0 |
| Selected option below the returned maximum | 0 | 0 |

These counts describe an early-stopped sample, not an incident-rate estimate.
The grid observation concerns numerical values, not trailing zeros in original
HTTP JSON. Decimal arithmetic confirms the discrepancy is not binary summation
noise. The affected `r2-case-10-jev-coreinfra / concern_kind` answer is:

```json
{"mechanics": 0.93, "policy": 0.02, "unknown": 0.0, "variant_behavior": 0.04}
```

The selected label is `mechanics`, with a **0.89 margin** over the runner-up.
Under nearest-hundredth rounding, the selected option is at least 0.925 and the
runner-up at most 0.045: a margin of at least 0.88. This is a sensitivity bound,
not reconstructed hidden model output.

Rescaling by the total, only as an arithmetic counterfactual, turns 0.93 into
approximately 0.939394. The largest change is **0.009394**, or **0.9394 percentage
points**. A positive common scale cannot change the ranking. No stored
probability or native confidence was changed.

### Effect on the hypotheses

- **H1, labels:** the rejected raw answer agrees with the reference on both
  axes (`excluded / mechanics`). A post-hoc label-only reading makes Jev repeat
  two's observed complete pairs **2 correct / 2 available**, instead of the
  strict report's **1 correct / 1 available**. The planned denominator remains
  four pairs, with two still unavailable. Repeat one is unchanged.
- **H2, withheld controls:** unchanged. All controls were already strict-valid;
  Jev's joint counts remain **1/4 then 2/4**, Luna's **3/4 then 3/4**. A mass
  tolerance does not fix responsibility guesses when context is withheld.
- **H3, direction:** every observed complete pair has positive deltas on both
  axes, including the additional Jev pair. Rescaling keeps those signs. Under
  assumed nearest-hundredth rounding, use `[max(0,p-.005), min(1,p+.005)]` for
  each value and subtract opposite endpoints. Every available delta remains
  positive. This checks direction, not probability calibration.
- **Completion:** six requests were never sent. This analysis cannot supply
  their answers or confirm the full two-repeat hypotheses.

The [original strict score](runs/2026-10-13-contrastive-native-wires/score.json)
and its 41-valid/1-invalid counts remain authoritative for protocol v1. The
separate artifact is explicitly post-hoc sensitivity analysis.

## Concrete policy for the next experiment

Use a versioned `jev-choice-mass-warning/v1` compatibility policy, initially
limited to **`jev-1.13.0` Choice questions with three or four options**. This is
a local allowance, not a claimed provider guarantee. Keep Luna's policy separate.

| Condition | Next-version behavior |
|---|---|
| Expected model/question/option identities; finite numerical probabilities and confidence in `[0,1]`; selected option is a maximum; mass within existing `1e-6` tolerance | Accept normally. |
| All structural/range/winner checks pass; absolute mass error is at most `0.01`, outside `1e-6` | Accept raw selected labels with `probability_mass_deviation` warning. Record total, residual and policy version. Continue the run. |
| Mass error exceeds `0.01`, missing/extra option, non-finite/range-invalid value, unknown selected label, or selected option below the maximum | Mark the affected result unavailable and preserve evidence. Do not infer a replacement label or retry for a preferred answer. |
| Run integrity/identity failure or exhausted attempt budget | Stop under the existing integrity/budget policy. |

Use decimal arithmetic or a separately specified machine-rounding allowance at
the `0.01` boundary: binary `1 - 0.99` must not accidentally reject it. Test both
`0.99` and `1.01`, plus just-outside values. The fixed bound does not grow with
option count; wider taxonomies need a separate policy.

Use accepted **raw labels** for H1/H2 and keep native confidence untouched. H3
must identify warned distributions and show raw deltas plus sensitivity bounds.
When a comparison changes sign within assumed precision, mark it unresolved.
Normalization is unnecessary here and should not silently boost a value across
a downstream threshold.

A numerical warning should neither trigger a TLS retry nor terminate the study.
Separate answer rejection from study-wide interruption and preserve unaffected
evidence. The next runner must record per-result errors and completion separately
from full usable coverage, so continuing after a rejected result does not imply
all hypothesis prerequisites were met.

## Follow-through

The [v2 runner and scorer](contrastive-mass-warning-v2.md) now implement the
warning policy, boundary checks, result-rejection/stop distinction and H3
sensitivity reporting. Freeze a new v2 manifest before further inference.
The diagnosis and v2 implementation change no frozen v1 decoder/runner/manifest/
reference/score, production classifier, library contract or S/U metric.

The locally inspected Jev4Mellea `results.py` also checks sums strictly (absolute
tolerance `1e-3` for Choice and Score) and can reject this numerical shape.
Handle that separately. A Choice mass allowance does not automatically define
Score expectation consistency or Noul behavior.
