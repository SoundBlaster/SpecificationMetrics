# Matched-rubric diagnostic · 2026-10-10

## Question and preregistered decision

Does aligning the Jev task with the independent annotation task improve
opportunity classification **without introducing new owned or mechanics false
positives**? The frozen manifest requires opportunity agreement and eligible
recall to improve in both fresh repeats, with no newly positive controls.

**Result: the full hypothesis is not supported.** Recall improved from 0/3 to
2/3, but an additional already-owned rule became eligible. No production
classifier, prompt, registry, liveness or S/U snapshot was changed.

The directory date uses the user's Europe/Moscow date. Raw receipt timestamps
are UTC: the live run occurred 2026-10-09 21:39 UTC, already October 10 in Moscow.

## Frozen inputs and independent reference

`rubric.json` contains the aligned Choice questions and criteria. Its intent:

- One use is enough for a stable product/domain rule to benefit from a named,
  addressable, observable Specification.
- For a mixed target site, consider whether it contains a distinct product
  decision; supporting declarations are evidence, not separate candidates.
- Mechanics means no distinct product decision. Product integrity/authority
  validation may still implement policy.
- Existing ownership requires explicit evidence for this same rule. Imports
  and ordinary helper names alone are insufficient evidence.

A fresh no-history reference agent read only an isolated copy of
`reference-packet.json`: exactly the aligned questions and the same bounded
state objects. No prior labels, source candidate IDs, historical roles or Jev
outputs were supplied in its brief. Opaque case IDs map to source candidates in
`reference-mapping.json`. The states retain their existing opaque candidate IDs
and visible source paths; recognition of source code or shared model bias cannot
be ruled out. The agent had read-only access and was instructed not to read
other files, browse, use credentials or delegate.

`annotations.json` was frozen before live Jev inference. All eight categorical
references agree with the earlier model annotation. The independent agent's
actual model identity was not exposed by the spawn result; no model override
was supplied. Its task and isolation settings are recorded rather than an
invented model identifier. This annotation involved **fresh agent inference**;
it is not human-approved gold. The eight examples remain diagnostic development
cases, not a new-family holdout.

## Paired comparison

32 requests: eight cases, baseline/aligned wording, two repeats. Both arms use
`jev-1.13.0`, the CoreInfra endpoint, joint Choice questions, identical state
objects, canonical serialization, the same root/question ordering and a pooled
HTTPS client. Four cases per repeat are baseline-first and four aligned-first;
the second repeat reverses each pair. Exact request strings and digests are in
`plan.json`; validation rejects unplanned context or reference-task changes.

The aligned arm changes several rubric clauses together. It tests a composite
task-alignment intervention, not the independent causal effect of `reusable`,
mechanics qualification, mixed-site scope or ownership wording. The baseline
is judged against the aligned reference deliberately: that makes the task
alignment mismatch visible and is not a claim that baseline was evaluated
against its own independently matched task.

## Results

The categorical results below are identical in **both** fresh repeats; counts
are shown per eight-case arm rather than pooling dependent repeats.

| Measurement | Baseline | Aligned |
|---|---:|---:|
| Opportunity agreement with aligned model reference | 4/8 | 5/8 |
| Eligible recall | 0/3 | 2/3 |
| Eligible precision | 0/1 | 2/4 |
| Reference-eligible predicted excluded | 3 | 1 |
| Owned controls incorrectly eligible | 1/2 | 2/2 |
| Mechanics controls incorrectly eligible | 0/3 | 0/3 |
| Concern-kind agreement | 7/8 | 8/8 |

| Case | Reference opportunity | Baseline opportunity | Aligned opportunity |
|---|---|---|---|
| sg-017: pre-SIB state policy | eligible | excluded | eligible |
| sg-019: AC coverage / mixed repair function | eligible | excluded | excluded |
| sg-018: pre-SIB FirstMatch | excluded | excluded | eligible |
| sg-033: workspace allocation binding | eligible | excluded | eligible |
| sg-031: dict adaptation | excluded | excluded | excluded |
| sg-032: text normalization | excluded | excluded | excluded |
| sg-020: AC repair FirstMatch | excluded | eligible | eligible |
| sg-034: slug normalization | excluded | excluded | excluded |

sg-019 concern kind changes from mechanics to policy, while opportunity remains
excluded. This demonstrates why the two axes must stay separate.

**32/32** requests succeeded in **29.304 seconds**, including TLS preflights.
The first unauthenticated TLS preflight failed with SSLEOFError; the second
succeeded. No credential or HTTP inference was sent during those preflights.
There were **zero inference retries**, **71,176 reported tokens**, and no
operationally failed model responses. Reported token counts are not actual
billed dollars or remaining credential balance.

Baseline reported 32,936 input and 1,484 output tokens across both repeats;
aligned reported 35,288 input and 1,468 output tokens. The predeclared limit was
32 inference calls and 90,000 observed tokens, checked after each response.
The provider key spending cap is separate. Responses are capped at 1 MiB,
redirects are not followed, and the socket timeout is 30 seconds, not an
absolute whole-run deadline. The sender refuses to overwrite recorded runs.

A local preparation failed before producer metadata was available, so an
initial attempted launch exited before any HTTP/TLS activity. It produced no
inference receipts or responses; after the offline checks passed, the one live
run above was executed. There was no hidden live retry.

## Interpretation and next step

1. Task alignment recovered two intended candidates and improved kind
   recognition on this diagnostic set. It did not merely call all mechanics
   eligible; all three mechanical controls remain excluded.
2. Ownership became worse despite clearer ownership instructions. A combined
   question still mixes architectural suitability with whether a rule remains
   unowned. Static ownership evidence should constrain the latter; Choice
   output alone must not change the denominator or registry.
3. The predeclared no-new-false-positive criterion failed in both repeats.
   Do not deploy this prompt as an unqualified improvement or tune it further
   until these findings disappear. Keep this negative result visible.
4. New reference labels match the prior labels, reducing concern that the
   measured gains arose only from relabeling these cases. It does not establish
   human gold or remove shared model bias.
5. Next evaluate a **formal ownership filter followed by semantic suitability**,
   with separate provenance for the formal proof and AI suggestion. Verify the
   same target-to-Specification relation rather than neighboring imports.
   Keep sg-019 as an unresolved granularity case for human adjudication and a
   separately versioned predicate-target study. Any production-quality claim
   needs new families and adjudicated references.

No filtered counterfactual is presented as a measured classifier result here.
This experiment did not invoke the production Rust CLI or RustDecision router;
it is a bounded native API diagnostic, not consuming-client integration proof.
See the [cumulative insights](../../insights.md).

## Offline reproduction and artifacts

From `evals/jev-classification`:

```bash
python3 rubric_alignment.py --run runs/2026-10-10-rubric-alignment
python3 -m unittest -v test_rubric_alignment.py
python3 score_rubric_alignment.py --run runs/2026-10-10-rubric-alignment --output /tmp/aligned-rubric-summary.json
```

These commands need no keys or inference. CI uses only offline validation.
`summary.json` binds the complete analysis implementation (wrapper, metrics,
validator and parser dependencies) and all input/output artifacts. Operational
failures and unattempted cases remain unscored with planned denominators; a
partial run cannot support or refute the full paired success criterion.
