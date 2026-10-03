# Jev prompt evaluation

This Promptfoo suite compares two versions of the opportunity question against
the same Jev model, candidate state, label set, and concern-kind question:

- `baseline-v1` reflects the current classifier contract in concise form.
- `boundary-test-v2` makes the domain-impact test, boundary ownership, and
  abstention rules explicit. It tests the hypothesis that Jev needs a sharper
  decision procedure, not a larger prompt or more repository context.

The only checked-in case is `publication.site.069` from the SpecGraph
publication diagnostic. Its expected labels are a **pilot hypothesis**, not an
independent human-reviewed gold label. The diagnostic proposed `policy` and
identified the site as a possible Specification opportunity; neither result is
formal approval. One case can reveal prompt behavior and probability movement,
but cannot establish classifier accuracy or generalize across code.

The state is a compact, reviewed summary of that source site. It does not
include the repository or send a whole source file. Add cases only with a
documented label source and mark provisional labels explicitly. Keep uncertainty
visible; Jev Choice probabilities are relative to the fixed labels and are not
calibrated confidence.

## Run

Requires Node.js and a TypeSafe key. The promptfoo version is pinned in
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

Use `npm run eval:fresh` when explicitly requesting a fresh comparison that
bypasses Promptfoo's response cache. Do not use it in automated retries.

## Offline checks

```bash
python3 validate_cases.py
npm run test:offline
npm run validate
```

These checks validate dataset invariants and Promptfoo configuration without a
TypeSafe key or model request.

## Reading results

For each axis, Promptfoo reports whether the returned Choice matches the
case's pilot hypothesis. The assertion score is the probability Jev assigned
to that expected label. Compare both:

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

The suite uses Promptfoo's documented custom JavaScript provider interface.
The TypeSafe page currently documents a built-in provider, but the pinned npm
release `0.123.1` does not resolve `typesafe:jev-1.13.0`; the direct adapter
keeps this evaluation runnable against that published release. The adapter
uses one HTTP request per case/provider pair, a 30-second timeout, rejects
redirects, caps response size, and does not implement retries. Promptfoo's
response cache remains available unless `eval:fresh` is selected.
