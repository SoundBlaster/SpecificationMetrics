# Contrastive live results — 2026-10-13

## Outcome and scope

**Partial run: 42/48 requests sent, 41 native-valid answers, one native-invalid
answer, six proven unattempted requests. No TLS retries or ambiguous POSTs.**

The frozen runner stopped after Jev returned a concern-kind probability sum of
**0.99**, violating the preregistered normalized-distribution contract. It did
not reach an attempt cap or fail TLS. The full two-repeat study is operationally
incomplete. No additional inference, label repair, renormalization, reference
change, registry disposition or S/U write followed the stop.

Execution took **76.014121 seconds**, 2026-10-13 **01:40:31–01:41:47 MSK**
(2026-10-12 22:40:31–22:41:47 UTC). The
[receipt](receipt.json), [attempt ledger](attempts.jsonl),
[raw responses](responses.jsonl), [native validation](native-validation.json)
and [offline score](score.json) preserve the original 48-request denominator.
The manifest SHA-256 remains
`f972782f137f1e99ab910a7db378e0a9a0720d0a99d3d5cc4a6d96c8192959ce`.

These are four **authored development pairs**, with an independent model
reference and integrator review. They are not human gold, natural-code holdout
examples or production classifier accuracy. Findings below are relative to the
unchanged reference/profile.

## H1/H2/H3: the complete first repeat

Both providers returned all 12 native-valid answers in repeat one. This permits
scoped evaluation of that repeat; it does not complete a hypothesis requiring
success in **both** repeats.

| Endpoint, repeat one only | Jev | Luna |
|---|---:|---:|
| H1: full pairs correct on both axes; requires 4/4 | **4/4 — met** | **3/4 — failed** |
| Full-context opportunity agreement | 8/8 | 7/8 |
| Full-context concern-kind agreement | 8/8 | 8/8 |
| Eligible policy recall | 4/4 | 4/4 |
| Mechanics false positives relative to reference | 0/4 | 1/4 |
| H2: withheld controls return `needs_review / unknown`; requires 4/4 | **1/4 — failed** | **3/4 — failed** |
| H3 secondary: both option-probability deltas positive; requires at least 3/4 | **4/4 — met** | **4/4 — met** |

### H1: role distinction works on these explicit contexts, with one false positive

All four policy members were selected as `eligible / policy` by both providers.
Both recognized the repair-reference rule in pair 01, where the preceding
historical-expression study had a shared false exclusion. The tasks/corpora have
changed, so this is **not** a matched before/after accuracy improvement or proof
of a prompt fix.

The only first-repeat full-context disagreement is Luna's **case-10 / pair-02
mechanics**: the guard in `render_text` avoids repeated CRLF normalization and
preserves the requested representation. The explicit contract says that the
function accepts or rejects no document. Reference: `excluded / mechanics`.
Luna: `eligible / mechanics`, repeated unchanged on the second attempt at this
same state in repeat two.

Its opportunity distribution is eligible **0.51**, excluded **0.46**,
needs_review **0.03**; native confidence **0.27**. Concern kind is mechanics
**0.49** versus policy **0.48**. This is a close decision, not grounds for choosing
a fallback threshold from this one example. The response has no explanatory
rationale, so we cannot establish why the model chose it. Confusing a stable
representation contract with a product policy is a hypothesis for future tests.
Do not collapse the two classifier axes or automatically rewrite this answer
from its concern-kind label.

### H2: eligibility abstention does not imply responsibility abstention

Every withheld control, including all four in each provider's second repeat,
returned **opportunity=`needs_review`**: 16/16 observed control answers. Thus no
withheld control was excluded or promoted to eligible in this run.

However, the joint H2 criterion also requires `concern_kind=unknown`. Models
often guessed a responsibility from the expression despite absent input meanings
and effects:

| Withheld expression family | Jev repeat 1 | Jev repeat 2 | Luna repeat 1 | Luna repeat 2 |
|---|---|---|---|---|
| 01: nonempty/all membership | policy | unknown | unknown | unknown |
| 02: readiness/mode guard | mechanics | mechanics | unknown | unknown |
| 03: fields, grants and digest | policy | policy | policy | policy |
| 04: fallback value | unknown | unknown | unknown | unknown |

Joint H2 counts: Jev **1/4 → 2/4**, Luna **3/4 → 3/4**. All withheld answers are
available and native-valid; these errors are observed, not caused by missing
requests. The stronger H2 claim fails in every repeat. Repeat-two whole-provider
operational prerequisites are still incomplete.

Family 03's names such as `commit` and `digest` carry semantic hints. This can
motivate a best guess, but the reference and rubric require unknown when missing
meanings/effects are material. The evidence supports an axis-specific abstention
gap on these controls; it does not prove hidden model reasoning, a universal
inability to detect missing context, or that lexical hints are the cause.

### H3: direction can be correct while the selected label is wrong

The first-repeat deltas are **policy member minus mechanical member**, compared
within each provider, using the original native option probabilities:

| Pair | Jev ΔP(eligible) | Jev ΔP(policy) | Luna ΔP(eligible) | Luna ΔP(policy) |
|---|---:|---:|---:|---:|
| 01 | +0.55 | +0.59 | +0.36 | +0.32 |
| 02 | +0.75 | +0.97 | +0.46 | +0.50 |
| 03 | +0.76 | +0.91 | +0.78 | +0.65 |
| 04 | +0.76 | +0.90 | +0.86 | +0.82 |

Both meet H3's secondary criterion in repeat one. Yet Luna labels the mechanical
member of pair 02 eligible at P=0.51 while the policy member is eligible at
P=0.97. A positive delta is evidence of directional context sensitivity, **not**
correct absolute classification or calibrated confidence.

Full-context members differ together in names, types, contracts and effects.
Identical target bytes control the selected computation, but do not isolate
which part of the context mattered. Do not compare probability magnitudes
between providers as calibrated measures of superiority.

## The incomplete second repeat

| Measure | Jev | Luna |
|---|---:|---:|
| Usable cases / planned | 8/12 | 9/12 |
| Complete full pairs available | 1/4 | 2/4 |
| Jointly correct full pairs / original denominator | 1/4 | 1/4 |
| Jointly correct withheld controls | 2/4 | 3/4 |
| H3 directional pairs / original denominator | 1/4 | 2/4 |

Jev's other three pairs are unavailable because of an invalid or missing member;
these are **not three measured semantic misclassifications**. Luna has one known
pair error (the same normalization guard) and two unavailable pairs. H1/H3
cannot be confirmed across both repeats. Missing/invalid cases do not shrink
the denominator or turn into `needs_review`.

Repeat comparison covers Jev **16/24 case-axis pairs**, with one concern-kind
change (case-03, withheld family 01: policy → unknown). Maximum native confidence
and option-probability differences are **0.13** and **0.08**. Luna covers
**18/24 case-axis pairs**, with identical observed labels, probabilities and
confidence. Neither meets the planned full repeat-stability claim. This does
not establish provider caching or determinism.

## Native failure and accounting

Request **`r2-case-10-jev-coreinfra`** returned `jev-1.13.0`, HTTP 200, two Choice
answers, expected options and an argmax-selected label. Its concern-kind
probabilities were:

```json
{"mechanics": 0.93, "policy": 0.02, "unknown": 0.0, "variant_behavior": 0.04}
```

The sum is **0.99**, outside the frozen absolute tolerance `1e-6`. Its opportunity
axis sums to 1, but the strict **whole native response** is rejected. Its raw
labels remain inspectable; they are not scored as accepted predictions.

[The offline contract diagnosis](native-contract-diagnosis.json) records that
rounding every number to the nearest 0.01 would allow an underlying sum between
0.975 and 1.010, including 1. This is numerical compatibility with a rounding
hypothesis, **not verified provider rounding behavior or a documented API
guarantee**. A defect in model generation or gateway serialization is also
possible. No decoder, tolerance, manifest or reference was changed after results.

| Accounting | Recorded |
|---|---:|
| Planned logical requests | 48 |
| Sent requests / attempts / potentially billable POSTs | 42 / 42 / 42 |
| Strict native-valid / native-invalid | 41 / 1 |
| Unattempted / unknown execution status | 6 / 0 |
| Retries / ambiguous POSTs | 0 / 0 |
| Jev reported input / output tokens, 21 responses | 26,271 / 1,926 |
| Luna reported input / output tokens, 21 responses | 22,364 / 0 |

[Usage accounting](usage-summary.json) includes the native-invalid response.
Reported usage is not billed cost. Actual dollars and remaining credential
balance are unknown.

Unattempted requests are both providers for case-08 (queue policy), case-12
(display mechanics) and case-04 (row-marker mechanics), all in repeat two.
No request from that set was sent after the failure.

## What this changes and the next experiment

1. **Useful development evidence:** complete explicit context supports the
   intended role distinction, especially in Jev's complete first repeat, and
   both providers show the expected directional signal there.
2. **Known limits:** Luna has a repeated mechanical opportunity false positive
   relative to this model reference; both providers fail joint abstention, and
   the native-contract issue prevents a complete two-repeat test.
3. **Next step before more inference:** investigate the probability representation
   contract using the saved response and provider contract evidence. If a
   rounding policy is justified, specify/test it in a new version with its own
   acceptance rules and frozen wires. Preserve this strict run as partial.
   A separately identified bounded run can then test that version; do not resume
   this directory or combine partial arms as if they were one completed run.
4. **Later semantic confirmation:** use new naturally occurring code families and
   separately adjudicated missing-context controls. Keep per-axis abstention,
   full-pair accuracy and directional probabilities separate; choose any fallback
   policy on a held-out evaluation, not by rescuing these observed errors.

No production defaults, automatic exclusions, registry writes or S/U changes
are justified by this diagnostic alone.
