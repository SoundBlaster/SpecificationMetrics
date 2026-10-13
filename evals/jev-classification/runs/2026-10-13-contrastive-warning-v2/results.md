# Contrastive v2 live results — 2026-10-13

## Outcome

**Completed: 48/48 accepted responses, no rejected responses, no mass warnings,
no TLS retries or ambiguous POSTs.** Execution took **83.803806 seconds**, from
**08:24:50 to 08:26:14 MSK** (05:24:50–05:26:14 UTC).

This is the explicitly authorized v2 experiment frozen on `d501926`, with
manifest SHA-256
`38725a1507a6f443dcd7169e39d742ce9e958b699e67dad4a3eca4df8e20b678`.
The [receipt](receipt.json), [attempt ledger](attempts.jsonl),
[raw responses](responses.jsonl), [native replay](native-validation.json),
[score](score.json) and [accounting/comparison](analysis-summary.json) preserve
the full 48-request denominator and provenance.

The reference is an independently annotated, integrator-reviewed **model
reference for four authored development pairs and four withheld controls**.
These are not human gold, twelve natural production targets or a population
sample. Two repeats do not create eight independent code families.

## H1/H2/H3

Every provider/repeat has all 12 planned usable cases. Counts below are for
repeat 1 → repeat 2, against the unchanged reference.

| Endpoint | Jev `jev-1.13.0` | Luna `gpt-6-luna` |
|---|---|---|
| H1: opposed full-context pairs correct on both axes, requires 4/4 each repeat | **4/4 → 4/4; supported on this set** | **3/4 → 3/4; failed** |
| Full-context opportunity labels | 8/8 → 8/8 | 7/8 → 7/8 |
| Full-context concern-kind labels | 8/8 → 8/8 | 8/8 → 8/8 |
| Eligible policy recall | 4/4 → 4/4 | 4/4 → 4/4 |
| Mechanical opportunity false positives | 0/4 → 0/4 | 1/4 → 1/4 |
| H2: withheld controls select `needs_review / unknown`, requires 4/4 each repeat | **2/4 → 1/4; failed** | **3/4 → 3/4; failed** |
| H3: directional pairs, requires at least 3/4 each repeat | **4/4 → 4/4; supported with sensitivity bounds** | **4/4 → 4/4; supported on raw probabilities** |
| Categorical repeat stability, zero changes required | **1 change / 24 paired axes; failed** | **0 changes / 24 paired axes; observed criterion met** |

H1 is now evaluable in both repeats for Jev, whereas the v1 study's second
repeat was incomplete. This supports the bounded claim that Jev distinguishes
these four explicit architectural roles. It does not establish production
classifier accuracy or superiority across naturally occurring code.

### Luna's repeated full-context error

The sole full-context error remains **case-10 / pair-02 mechanics**: the CRLF
normalization guard in `render_text`. The authored contract says it accepts or
rejects no document; the reference is `excluded / mechanics`. Luna returns
`eligible / mechanics` in both repeats.

Opportunity probabilities are eligible **0.51**, excluded **0.46**,
needs_review **0.03**, with native confidence **0.27**. Concern kind is mechanics
**0.49** versus policy **0.48**, native confidence **0.32**. These match the
previous run's observed answer. A low-confidence fallback might be useful, but
no threshold was selected here and the second axis was not used to rewrite the
first. The raw answer contains no explanation of the model's reasoning.

## H2: uncertainty is still axis-specific

Every withheld case selects **opportunity=`needs_review`**: all **16/16**
observed control responses across the two providers and repeats. The joint H2
failure comes from guessing `concern_kind` instead of selecting `unknown`.

| Withheld family | Jev repeat 1 | Jev repeat 2 | Luna repeat 1 | Luna repeat 2 |
|---|---|---|---|---|
| 01: nonempty/all membership, case-03 | unknown | policy | unknown | unknown |
| 02: readiness/mode guard, case-09 | mechanics | mechanics | unknown | unknown |
| 03: fields/grants/digest, case-02 | policy | policy | policy | policy |
| 04: fallback value, case-06 | unknown | unknown | unknown | unknown |

The fields/grants/digest expression attracts a policy label from both models
despite withheld input meanings and downstream effects. Lexical names may
provide a cue; that is a hypothesis, not an identified cause. Missing-context
reference/rubric interpretation remains a separate evaluation concern.

Jev's only repeat label change is case-03's responsibility:
`unknown → policy`. Its first concern distribution has unknown **0.43** and
policy **0.41**; repeat two has policy **0.42** and unknown **0.38**. This is an
observed close boundary. Jev's maximum within-run probability difference is
**0.09**, and native confidence difference **0.13**. All full-context labels are
stable. The failure of the zero-change criterion is localized to a withheld
responsibility judgment, not widespread instability.

## H3: context sensitivity without a rounding-dependent sign

The v2 Jev criterion uses raw policy-minus-mechanics probabilities and requires
both lower bounds to remain positive when each returned probability is allowed
an assumed nearest-hundredth interval. The assumption is explicit in the frozen
v2 manifest; it is not a provider precision guarantee.

| Pair | Jev ΔP(eligible), repeats 1 / 2 | Jev ΔP(policy), repeats 1 / 2 | Luna ΔP(eligible), both repeats | Luna ΔP(policy), both repeats |
|---|---|---|---:|---:|
| 01 | +0.55 / +0.57 | +0.59 / +0.59 | +0.36 | +0.32 |
| 02 | +0.77 / +0.81 | +0.98 / +0.98 | +0.46 | +0.50 |
| 03 | +0.73 / +0.66 | +0.87 / +0.82 | +0.78 | +0.65 |
| 04 | +0.75 / +0.76 | +0.86 / +0.85 | +0.86 | +0.82 |

All Jev lower bounds are positive; the minimum across both axes/repeats is
**+0.540**. No raw-positive pair becomes unresolved. Luna retains its unchanged
raw-probability criterion. Both meet H3, while Luna still fails H1: a directional
shift between two contexts is not absolute classification correctness.

The pair members differ together in names, types, contracts and effects. Equal
target bytes control the computation, not the individual contextual components.
Do not infer which component caused the model's prediction, or compare native
probability/confidence magnitudes as calibrated cross-provider quality.

## What the warning policy did and did not demonstrate

The mass allowance was **not activated**: zero live warnings. All 48 Jev
distributions are within the original strict tolerance (maximum decimal
residual from decoded values **1e-16**); all 48 Luna distributions total one.
The saved raw Jev value `0.5599999999999999` is retained unchanged.

Thus this run shows the v2 pipeline can finish with strict-valid responses. It
does not measure the warning path's live frequency or prove that the new policy
caused completion. V1's 0.99 failure simply did not recur in this sample. Boundary
and saved-failure tests remain the evidence that v2 handles that shape with a
warning. No provider serialization fix or universal numerical reliability is
established.

## Comparison with the prior run

The exact 48-request catalog and reviewed input digests are identical across
v1 and v2. Compare only the **21 shared raw responses per provider**, including
the v1 sum-only-invalid answer, while preserving each study's own score and
completion status.

- **Luna:** all 42 shared axis answers have identical labels, option probabilities
  and native confidence. Within v2 both repeats also match exactly on all
  24 paired axes. This is observed repeat consistency, not proof of caching,
  deterministic inference or statistically independent repeated samples.
- **Jev:** two of 42 shared axis labels differ, both case-03 concern kind: v1
  had `policy → unknown`, v2 `unknown → policy`. Shared numeric differences reach
  **0.08** for option probability and **0.10** for native confidence. Full-context
  labels match across all shared cases.
- V2 adds the six previously unsent results, covering both providers for queue
  policy, display mechanics and row-marker mechanics in repeat two. No old or
  new responses were stitched into a synthetic completed v1 experiment.

Neither the prompt, reference nor provider-visible wire changed. These are
repeated observations under different acceptance/scoring versions, not evidence
that the numerical warning policy improved model semantics.

## Accounting

| Measure | Result |
|---|---:|
| Planned/sent/accepted responses | 48 / 48 / 48 |
| Network attempts / potentially billable POSTs | 48 / 48 |
| Warnings / rejected responses | 0 / 0 |
| Retries / ambiguous POSTs | 0 / 0 |
| Missing/unattempted/unknown-execution results | 0 / 0 / 0 |
| Jev reported input / output tokens, 24 responses | 30,184 / 2,204 |
| Luna reported input / output tokens, 24 responses | 25,716 / 0 |

Reported usage is not billed cost. Actual dollars and remaining credential
balance are unknown. Analysis sent no additional inference requests.

## Decision and next experiment

1. **Keep Jev as an optional candidate recommendation source.** On these explicit
   contexts it satisfies the role distinction and directional criteria in both
   repeats, with no mechanical false positives relative to this reference.
2. **Keep uncertainty per axis.** Eligibility abstention works on these controls,
   but responsibility abstention and Jev's zero-change criterion fail. Do not
   auto-apply a guessed responsibility or translate it into S/U changes.
3. **Next:** prepare new naturally occurring SpecGraph examples that test whether
   input meanings and effects are sufficient to classify responsibility. Obtain
   an independent target-specific reference. If testing an explicit context
   evidence gate, report its effect separately from raw Jev/Luna output.
4. **Do not tune a fallback threshold on these errors and call it confirmation.**
   Further inference needs a separately frozen corpus/hypothesis/budget. The
   warning policy remains bounded; no larger tolerance or new retry behavior
   was selected after this run.

No production classifier defaults, library contracts, reviewed registry entries
or S/U metrics were changed by this experiment.
