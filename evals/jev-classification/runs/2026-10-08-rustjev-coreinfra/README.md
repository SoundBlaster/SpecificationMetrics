# RustJev / CoreInfra diagnostic evaluation — 2026-10-08 UTC

## Result

The merged Rust adapter successfully completed 16 fresh requests in 11.967 s,
but opportunity classification regressed against the earlier recorded run on
these eight examples. No further hosted calls or prompt tuning were performed.

| Measure | Current RustJev / CoreInfra | Historical profile arm |
| --- | --- | --- |
| Opportunity agreement with model reference | 4/8 | 7/8 |
| Eligible recall | 0/3 | 2/3 |
| Eligible precision | 0/1 | 2/2 |
| False exclusions | 3 | 1 |
| Already-owned sites wrongly proposed | 1/2 | 0/2 |
| Mechanical controls correctly excluded | 3/3 | 3/3 |
| Concern-kind agreement | 7/8 | 7/8 |
| Operational / validation errors | 0/16 requests | 0 |

All sixteen results were `Accepted` by the provider-neutral core using default
policy: no minimum probability, no minimum confidence, no fallback. Here
`Accepted` means a structurally and numerically valid answer mapped to a typed
label, **not** a correct semantic judgment or sufficient classifier confidence.
Selected opportunity probability ranged from 0.43 to 1.0; provider confidence
ranged from 0.14 to 1.0. Those values are diagnostics, not calibrated reliability.

## Case-level opportunity results

| Site | Independent model reference | Current Jev | Interpretation |
| --- | --- | --- | --- |
| sg-017: procedural pre-SIB gate | eligible | excluded | missed policy |
| sg-018: named pre-SIB decision | excluded | excluded | already-owned control retained |
| sg-019: acceptance-criteria coverage | eligible | excluded | missed policy; kind also differs |
| sg-020: named acceptance-criterion repair | excluded | eligible | already-owned false positive |
| sg-031: `_dict` | excluded | excluded | mechanical control retained |
| sg-032: `_text` | excluded | excluded | mechanical control retained |
| sg-033: workspace-allocation authorization | eligible | excluded | missed policy |
| sg-034: `_slug` | excluded | excluded | mechanical control retained |

For sg-017 and sg-033, Jev called the logic `policy` but rejected it as an
opportunity. This is a suitability/ownership issue, rather than a failure to
recognize any policy. For sg-020 the supplied code visibly uses a named
`FirstMatch` decision, so model suitability is unsuitable as the only ownership
filter. Static ownership proof should precede model scoring of remaining sites;
this run deliberately assessed the classifier itself without silently applying
that filter.

## Protocol and provenance

- Eight fixed purposive cases from the existing goal-profile diagnostic study.
- Reference: frozen independent **model** annotations under SpecificationCore
  intent profile v2; not human-adjudicated gold, not a fresh holdout.
- Local instructions, criteria and bounded code/profile objects reused unchanged.
  No labels, annotation evidence, family IDs, or historical predictions included
  in model input. `requests.json` contains only opaque IDs, source/profile state,
  instructions and criteria.
- Opportunity and concern kind sent separately through RustJev: 8 × 2 = 16
  potentially billable requests, no cache and no automatic retries.
- Requested `jev-latest`; all returned `jev-1.13.0`.
- Adapter `67cc832f0cafc57788f3a2e8dd20978b1c94dca6`; core
  `ce6665ab6c4c85e68b8596c92ede009fc8fc7f45`; git pins and transitive dependencies
  frozen in the separate driver's `Cargo.lock`.
- Explicit JSON state encoding, total request timeout 30 s, connect timeout 10 s;
  no redirects, automatic retry or model escalation.
- 30,288 input and 766 output tokens. Response metadata supplies no billed dollar
  amount, so this report does not infer spending from token counts. The key has
  an externally configured spending limit. Its value is absent from artifacts.
- The driver caps the plan at sixteen calls and stops after operational failure
  or reaching the observed 40,000-token guard. Token guard is checked after a
  response and cannot cap a single call or dollar spending. The next step does
  not execute automatically.
- `manifest.json` binds request data, profile, reference, mapping, historical
  artifacts, driver source, Cargo manifest/lock and scorer via SHA-256.
  Input digests are verified when rescoring; implementation digests describe
  the code used for this run and do not require future compatible scorers to
  have identical source bytes. Check out this report PR revision to reproduce
  the exact implementation. `receipt.json` records execution; `responses.jsonl` preserves sanitized native
  evidence and terminal outcomes; `summary.json` stores offline scores.

## Comparison limits

The historical direct-TypeSafe study used both questions in one request. This
run used CoreInfra, separate questions, the current `jev-latest` alias and a new
execution date. Rust serialization also canonicalizes JSON object keys, unlike
the historical JavaScript serialization. Model version strings are not immutable
checkpoint identifiers. Therefore the lower score **does not establish that
CoreInfra, RustJev, question splitting, or key order caused the regression**.
It establishes that this concrete integration/configuration should not currently
make autonomous candidate exclusions or authorize changes to S/U metrics.

No repeated sample was used and no prompt was selected on these outcomes.
Eight purposive sites cannot estimate project-wide prevalence, classifier
accuracy, calibration, or generalization. Eligibility/precision numbers describe
agreement with one model reviewer; `sg-019` still awaits human adjudication.
Missing/provider-failed/core-abstained results remain unscored and visible in the
planned denominator; valid `needs_review`/`unknown` labels remain semantic labels.

## Reproduce offline

From `evals/jev-classification` (Python commands use only the standard library):

```bash
cargo fmt --check --manifest-path rust-driver/Cargo.toml
cargo test --locked --manifest-path rust-driver/Cargo.toml
cargo clippy --locked --manifest-path rust-driver/Cargo.toml --all-targets -- -D warnings
cargo run --locked --manifest-path rust-driver/Cargo.toml -- \
  --validate runs/2026-10-08-rustjev-coreinfra/requests.json
python3 -m unittest -v test_score_rustjev.py
python3 score_rustjev.py --run runs/2026-10-08-rustjev-coreinfra \
  --output /tmp/rustjev-rescored.json
```

These commands do not send inference requests. Building may fetch pinned Git
and Cargo dependencies. The separate driver keeps evaluation tooling out of the
production scanner dependencies.

## Explicitly authorized fresh live run

Set `COREINFRA_API_KEY` privately and supply the full `JEV_ENDPOINT`; do not
record either credential value or a provider error body. Do not overwrite the
recorded responses. Each new run needs a new directory and provenance receipt.

```bash
cargo run --locked --manifest-path rust-driver/Cargo.toml -- \
  --live runs/2026-10-08-rustjev-coreinfra/requests.json
```

The `--live` switch authorizes up to 16 potentially billable requests.

## Next experiment

Before changing the prompt or selecting thresholds, run a separately budgeted,
paired comparison of question grouping on this same endpoint/model/context:
separate axes versus a native two-question request. Keep serialized state,
criterion order and model fixed; retain ownership controls and low-confidence
policies. This requires a separate direct evaluation transport because RustJev
currently exposes a single-question API. It must not be presented as a RustJev
batch feature or isolated evidence about the proxy. Human-adjudicate unresolved
reference disagreements before claiming classifier accuracy.
