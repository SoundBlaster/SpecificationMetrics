# Jev prompt evaluation

This Promptfoo suite compares two versions of the opportunity question against
the same Jev model, candidate state, label set, and concern-kind question:

- `baseline-v1` reflects the current classifier contract in concise form.
- `boundary-test-v2` makes the domain-impact test, boundary ownership, and
  abstention rules explicit. It tests the hypothesis that Jev needs a sharper
  decision procedure, not a larger prompt or more repository context.

The default smoke case is `publication.site.069` from SpecGraph source code.
Its expected labels are a **pilot hypothesis**, not an
independent human-reviewed gold label. The diagnostic proposed `policy` and
identified the site as a possible Specification opportunity; neither result is
formal approval. One case can reveal prompt behavior and probability movement,
but cannot establish classifier accuracy or generalize across code.

The state contains the exact pinned source excerpt, imports and selected
supporting declarations, with previous diagnostic labels excluded. It does not
send the repository or a whole source file. Add cases only with a
documented label source and mark provisional labels explicitly. Keep uncertainty
visible; Jev Choice probabilities are relative to the fixed labels and are not
calibrated confidence.

The [evaluation protocol](methodology.md) defines the objective, annotation,
group splits, paired comparisons and acceptance criteria. The
[SpecGraph corpus](corpus/README.md) adds 60 source-grounded cases in 34 families,
including 15 historical before/after pairs. All corpus annotations remain
unreviewed hypotheses. [Review packet](corpus/review.md) and
[blank review template](corpus/review-template.json) omit proposed labels.
No corpus-wide hosted evaluation has been performed; two providers would make
120 API requests. The default command still sends only the one smoke case.

## Run

Requires Node.js >=22.22.0 and a TypeSafe key. The promptfoo version is pinned in
`package-lock.json`; Jev is pinned to `1.13.0` in the config.

```bash
cd evals/jev-classification
npm ci
export TYPESAFE_API_KEY='…'
npm run eval
```

This sends the checked-in candidate state to TypeSafe Jev. It makes hosted
requests and may incur usage charges. It is deliberately not part of regular
CI and does not run during local validation. The result is written to
`results/latest.json`. The current one-case comparison sends two requests,
one per prompt variant; each request asks both classification questions. The
Promptfoo UI can be opened with:

```bash
npm run view
```

## Offline checks

```bash
python3 validate_cases.py
python3 -m unittest -v test_validate_cases.py
npm run test:offline
npm run validate
```

These checks validate dataset invariants and Promptfoo configuration without a
TypeSafe key or model request.

## Reading results

For each axis, Promptfoo reports whether the returned Choice matches the
case's pilot hypothesis. The assertion score is categorical agreement (1 or 0);
expected-label probability remains in the assertion reason and raw output.
Compare both:

1. whether the selected label changed or matched;
2. how the probability mass over the fixed labels moved.

Do not pick a prompt solely because it raised one expected-label probability
for this one case. Review the full per-label distributions, Jev model/version,
and additional cases with independently reviewed expected labels first.

The experiment changes only the opportunity instructions between providers.
The model version, state, criteria, and concern-kind question stay fixed, so
the comparison isolates one prompt factor. It does not evaluate source-context
size or redaction; those require a separate experiment with the same prompts
and different bounded states.

The first run is summarized in
[`runs/2026-10-04-publication-site-069.md`](runs/2026-10-04-publication-site-069.md).
Its exact original input is archived beside the report. That input contained a
previous `policy` diagnosis; this is label leakage, so the run cannot support an
independent quality claim. The updated source fixture must be treated as a new
input version; the previous output is not a result for it.

The suite uses Promptfoo's documented custom JavaScript provider interface.
The TypeSafe page currently documents a built-in provider, but the pinned npm
release `0.123.1` does not resolve `typesafe:jev-1.13.0`; the direct adapter
keeps this evaluation runnable against that published release. The adapter
uses one HTTP request per case/provider pair, a 30-second timeout, rejects
redirects, caps response size, and does not implement retries. It keeps bounded direct `fetch` for HTTP and stores only validated successful
provider results through Promptfoo's public cache helpers. Identical requests
reuse that cache; `npm run eval:fresh` (or Promptfoo `--no-cache`) forces a fresh
request. The key includes endpoint, model, state, rubric and an opaque credential
partition digest; credentials are not stored in keys or values. Errors and
oversized/malformed responses are never cached. Cached responses are marked
`cached: true` and `responseSource: cache`; their usage metadata describes the
original request, not newly billed tokens. Cache reuse is an evaluation convenience,
not a claim of independent repeated samples or immutable model behavior.

Offline CI includes actual rendering of the checked-in prompt with the pinned
Promptfoo evaluator and a fake provider, plus cache reuse/bypass/error tests.
No live Jev requests are needed. The standard Nunjucks interpolation is
`{{candidate_json}}`; triple-brace Mustache syntax is unsupported here.
# Independent source-reference comparison

The [independent experiment protocol](independent-experiment.md) adds blinded
model annotation, complete family splits, six fixed prompt variants, separate
confirmation and offline report scoring. The [recorded run](runs/2026-10-05-independent-reference/README.md)
made 92 fresh Jev requests. No improvement over baseline was demonstrated;
references are model annotations, not human-approved gold. This does not change
the original source corpus hypotheses or authorize automatic exclusions.

The follow-up [context ablation](runs/2026-10-05-context-ablation/README.md)
holds the prompt fixed and compares code, source task evidence and structural
implementation facts on eight diagnostic examples, with two fresh repeats.
It includes an explicit input correction and a separate static-filter view;
it is development evidence, not a new confirmation holdout.

The [SpecificationCore intent-profile ablation](runs/2026-10-05-intent-profile-ablation/README.md)
tests a different context factor: the same eight cases with and without a
versioned description of the project's global architecture goal. The prompt and
code state otherwise remain fixed. The result supports adding project intent as
an explicit classifier input on these examples, but inherited pre-profile labels
are not gold for the new goal.

## RustJev / proxy diagnostic evaluation

The [recorded RustJev / CoreInfra run](runs/2026-10-08-rustjev-coreinfra/README.md)
uses the frozen eight-case independent intent-profile model reference. Sixteen
single-question calls passed transport/core validation, but opportunity agreement
was 4/8 and eligible recall 0/3. Historical profile agreement was 7/8; provider,
question grouping, serialization and date differ, so the cause remains unproven.
The separate git-pinned `rust-driver` and `score_rustjev.py` preserve reproducible
inputs and offline scoring. No production classifier, registry disposition, S/U
count or confidence threshold was changed.

## Paired question grouping

The [native paired comparison](runs/2026-10-08-question-grouping-persistent/README.md)
held transport, endpoint, explicit model, canonical state and prompts fixed.
Joint and separate questions agreed on all labels: both scored 4/8 opportunity
and 7/8 concern-kind agreement. Joint requests used 44.6% fewer reported tokens
but numeric probability/confidence differences remain. Three operationally
stopped attempts are preserved separately. This diagnostic is not a RustJev
batch feature or a basis for autonomous exclusion.

## State key order and cumulative insights

The [exact-wire key-order comparison](runs/2026-10-09-state-key-order/README.md)
kept JSON semantics fixed but observed one changed opportunity label. Historical
insertion order scored 3/8 versus canonical 4/8; neither recovered earlier 7/8.
One response per arm cannot isolate ordering from baseline model variability.
All findings and their limits are collected in the [insight ledger](insights.md).
The frozen plan, receipts and report are validated offline in CI.

## Same-byte repeat controls

[Two fresh repeat rounds](runs/2026-10-09-repeat-controls/README.md) completed
32 requests. Labels stayed unchanged both across identical wires and key-order
arms, while probability/confidence varied. The earlier label flip did not
reproduce; opportunity agreement remains 4/8 and eligible recall 0/3.
`score_repeat_controls.py` reproduces the comparisons without inference.

## Eligibility diagnosis and brainstorm

[Three Astra Medium brainstorms](runs/2026-10-09-eligibility-diagnosis/README.md)
identify a verified task-phrasing difference between Jev and its model reference,
a mixed-function decision-boundary problem, and untested ownership/provider
hypotheses. Three fresh `gpt-6-astra` agents generated these hypotheses; no new
Jev inference or provider calls were made for this diagnosis. The report separates verified facts from
possible causes and proposes matched-task evaluation before prompt tuning.

## Matched-rubric comparison

The [aligned-rubric diagnostic](runs/2026-10-10-rubric-alignment/README.md)
used a fresh isolated reference agent and 32 paired Jev requests. Both repeats
improved eligible recall from 0/3 to 2/3 and concern-kind agreement to 8/8,
but owned false positives increased from one to two. The preregistered full
success criterion failed. Production prompts and metrics remain unchanged.

## Source-bound construction gate

The [offline composition replay](runs/2026-10-10-ownership-gate/README.md)
checks pinned source and resolved constructor imports before semantic routing.
It excludes two existing constructions, raising aligned opportunity agreement
from 5/8 to 7/8 without new inference. Six unknown sites retain recorded answers.
An actual Rust scanner audit also exposes different evaluation/discovery units
and missing outer `FirstMatch.with_fallback` recognition. This is bounded
diagnostic evidence, not a change to production ownership or S/U.

## Explicit target alignment

The [eight-case Rust export](runs/2026-10-10-decision-targets/README.md)
binds one explicitly selected expression per development case to exact source
bytes. Four targets match legacy scanner anchors; four have no such candidate.
No old semantic labels were copied and no inference ran. The next comparison
needs fresh target-specific annotations and bounded helper/data context.
