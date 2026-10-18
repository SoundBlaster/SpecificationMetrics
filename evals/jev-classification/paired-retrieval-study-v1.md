# Paired retrieval / no-retrieval study v1

## Question and current status

Does source retrieval help Jev and Luna Decision establish unresolved facts about
a SpecGraph decision, without inventing Specification ownership from similarity?
This is an evaluation of **evidence supply**, with fixed questions and architecture
intent. It is not a comparison of refactoring styles or an automatic acceptance
gate. S/U and source code are unchanged.

The first cohort is a small operational/development pilot: four targets, two
evidence views, two providers = **16 logical requests / at most 48 network
attempts**, including the initial attempt. No hosted request is part of
preparation. References, adjudication and semantic scores remain pending.
Four correlated targets cannot establish generalization or a 1% error rate.

## Frozen design

Source: `0al-spec/SpecGraph` at full commit
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`. Five selected production files are
indexed; this is not a whole-repository or intent-document search. The cohort
and exact natural-language queries are in `paired_retrieval_study_v1.py`.

| Case | Target | Selection purpose, not a reference label |
|---|---|---|
| R01 | `subject_workspace_allocation_spec.py::WORKSPACE_ALLOCATION_SPEC` | Already explicit declaration; evidence sufficiency control |
| R02 | `subject_source_write.py::_check_transition` | Multi-condition transition logic; nearby but potentially different rules |
| R03 | `subject_source_write.py::parse_write_authorization` | Representation boundary mentioning domain authority |
| R04 | `product_workspace_next_moves_support.py::safe_workspace_path` | Small path decision whose semantic role needs evidence |

The fifth/supplementary sources include reviewed-record and transition-approval
Specifications. These are candidates, never assigned same-decision ownership in
advance. R01's own declaration is excluded from retrieval hits but remains in
the target in both arms. Consequently R01 cannot demonstrate discovering a
previously hidden counterpart. This cohort does not guarantee a positive case
for ownership gain; if adjudication finds none, that endpoint is underpowered
and a new, preregistered cohort is needed, not a claim that retrieval is useless.

Within each pair, the target, architecture profile, query, accepted facts,
evaluation scope, index identity and all four questions are identical. The only
model-state difference is `retrieved_context`: empty in baseline, bounded ranked
source hits in retrieval. Both provider states use the exact same canonical
JSON. There are no extra instructions in the treatment arm.

- Encoder: existing pinned local EmbeddingGemma 2, revision
  `914f7f89142e33e77833254d9c9b90c3cef7303b`, 768 dimensions, normalized cosine.
- Top 5, up to 8,192 context bytes and 16,384 state bytes. Whole hits that exceed
  a limit are omitted and named; source is never silently truncated.
- No YAML Intent/proposal documents are supplied. An unresolved domain intent
  remains unresolved; code similarity must not stand in for authored Intent.
- Four axes: concern kind, ordinal evidence support, ownership, tool
  responsibility. `unknown` is permitted; `absent_in_scope` is not available.
- Jev `jev-1.13.0` and Luna `gpt-6-luna` use their existing distinct native APIs.
- One observation per case/provider/arm; no repeatability estimate. Arm and
  provider order reverse on alternating targets, balancing first positions.
  Runs are serial; order balancing reduces one confound without eliminating it.
- No prompt tuning or case replacement after observing these responses. A
  subsequent repair needs a new version/run and preserves this evidence.

### Prepared artifact, 2026-10-18

[`runs/2026-10-18-paired-retrieval-preparation-v1`](runs/2026-10-18-paired-retrieval-preparation-v1)
contains 51 JSON files (794,498 bytes): eight preparation bundles, eight blank
annotation views, the integrator mapping, manifest and final study receipt.
Local preparation used the actual pinned model on MPS with model downloads
disabled. Fifteen document inputs were encoded on the first refresh; all three
subsequent refreshes encoded zero. Four query embeddings were computed locally.

| Case | Retrieved documents | Context UTF-8 bytes | Whole top-5 hits omitted for budget |
|---|---:|---:|---|
| R01 | 4 | 6,965 | `subject_source_write.py::parse_write_request` |
| R02 | 5 | 6,580 | None |
| R03 | 5 | 8,074 | None |
| R04 | 4 | 7,753 | `product_workspace_next_moves_support.py::path_matches_root` |

The frozen input verifier and offline execution staging passed. Seventy-five
focused index/context/adapter/study/transport regression tests passed with
warnings treated as errors. Hosted requests: **0**. These are preparation and
software verification results, not measured H1/H2/H3 provider outcomes.

## Independent references before scoring

`blind/<view-id>/packet.json` contains one supplied evidence view.
`annotation-template.json` is blank and marked pending. Its author does not get
model answers, the selection-purpose table above, expected labels or
`reference-index.json`. The latter is integrator-only mapping, **not gold**.
The presence of source hits can reveal evidence mode: this is label/model-output
blinding, not treatment blinding.

1. Deliver only one packet/template per fresh annotation context. Never show
   baseline and retrieval of the same target to one annotator. Fresh contexts
   also prevent the shared R02/R03 file from leaking between those cases.
2. Record each view's justified categories, rationale, exact source locators and
   unresolved questions. `unknown`/insufficient support is not automatically an
   error. Do not infer an absent specification from missing retrieved hits.
3. Save completed annotations separately; do not fill or overwrite the frozen
   templates. Before opening model results, adjudicate disagreements with exact
   source witnesses. Compare whether the evidence views actually establish the
   same decision, rather than resolving by majority vote.
4. Produce a versioned reference with both view-conditioned acceptable answers
   and canonical source-supported facts where determinable. Missing Intent or
   tool configuration can keep a fact unresolved. Record adjudication identity,
   input/view hashes and rationale. Do not manufacture categorical gold for it.

Independent annotation has **not run**. There is no scoring command or claimed
accuracy in this preparation PR. The next reference/scoring change must freeze
the adjudicated reference and its scoring rules before a live run is interpreted.

## Hypotheses and reporting contract

Report Jev and Luna separately, with one row per pair, raw category/probability
retention and exact transport linkage. The unit is a **target/provider pair**;
axes within one response are not independent samples. Keep counts and denominators
visible, including unresolved and invalid observations.

| Hypothesis | Observable result after reference freeze | Evidence against it |
|---|---|---|
| H1: additional evidence helps | Retrieval increases source-supported correct non-unknown role/ownership resolutions on adjudicable pairs; show gains and losses separately | No net gain or more losses; zero applicable pairs means inconclusive |
| H2: retrieval does not create false ownership | No newly unsupported `existing_specification`/`simple_composition` assertions; show each false claim with sources | Any newly unsupported ownership assertion fails this pilot's no-regression criterion |
| H3: the integration is usable | 16 traceable responses; exact identity, complete ledgers, no native-contract invalidity, no ambiguous POSTs | Incomplete/invalid/ambiguous evidence fails operational eligibility; retain it, never score as a wrong domain label |

For H1 report `(correct supported resolutions retrieval - baseline) / adjudicable
pairs`, together with raw n/N, both arms' view-conditioned correctness and
gains/losses. An appropriate baseline abstention can be correct while retrieval
adds a new justified fact. These are different outcomes, not contradictory
scores. Role support must agree with role; an adapter consistency failure stays
visible even if one axis agrees with reference. Provider confidence is not
calibrated evidence strength. Latency/request count and retry ambiguity are
operational measures, not semantic quality. No statistical or production-level
success claim follows from this development cohort.

## Transport chain and failure handling

```text
immutable Git scope -> refreshed local index -> two frozen evidence views
 -> exact per-provider wire + manifest -> durable attempt ledger
 -> raw successful response bytes + receipt + execution binding
 -> transport inspector -> native adapter -> proposed facts (never accepted)
 -> independent reference comparison (pending)
```

`stage` validates without reading a key or sending. Execution needs a separate
explicit authorization for this frozen budget and an explicit `--live` flag.
Only then does the existing runner read `COREINFRA_API_KEY` from its process.
The wrapper retains exact successful JSON response bytes, their hashes and
the unchanged source/runtime inventory; it never prints or stores the key.
HTTP errors retain transport metadata instead of arbitrary error bodies.

Retries keep the exact wire: at most 3 attempts with 1/2-second backoffs for the
existing narrowly classified transient TLS/incomplete-body failures. Certificate
verification remains enabled. There is no semantic re-asking or retry for bad
labels, invalid JSON, HTTP errors or identity errors. A wrong model/question
identity stops the run. After a possibly sent POST, retries can duplicate provider
execution/billing; the ledger and receipt keep this ambiguity explicitly. A
crash/interrupt leaves an incomplete receipt and unknown ambiguity, not zero.

The inspector requires exact schedule, wire hashes, event order, attempts,
counters, receipt completeness, captured-body/JSON identity and producer binding
before emitting pairs. It records execution and analysis runtimes separately so
offline replay on a different host is explicit. Native invalidity, consistency
conflict and semantic correctness remain separate dimensions. An arbitrary
same-model JSON file cannot establish a transport-verified pair by itself.

`transport_verified=true` means **local manifest/ledger/receipt/body consistency**,
not a provider signature, trusted request echo or remote attestation. Local
checksums cannot defend against an operator fabricating an entire consistent
run. Incomplete runs yield no complete-pair report; their raw artifacts remain
available for diagnosis. Existing adapter reports retain their original
`transport_verified=false` unless produced through this inspector.

## Commands

Use the policy environment for verification/execution and the existing embedding
environment only for preparation. Apply the host's external build/cache routing
for local model/tests/stores. No model download is needed.

```bash
cd evals/jev-classification
# Offline: verify the checked-in preparation; no Git checkout/model/key needed.
../../.venv/bin/python paired_retrieval_study_v1.py \
  --verify runs/2026-10-18-paired-retrieval-preparation-v1

# Offline: create a new execution directory, validate its bounded schedule.
../../.venv/bin/python paired_retrieval_study_v1.py \
  --verify runs/2026-10-18-paired-retrieval-preparation-v1 --stage /path/to/new-run

# Only after separate explicit live authorization for 16 requests / <=48 attempts:
../../.venv/bin/python paired_retrieval_execution_v1.py \
  --preparation runs/2026-10-18-paired-retrieval-preparation-v1 \
  --run /path/to/new-run --live

# Local inspection, exclusive new report path. No semantic scoring yet.
../../.venv/bin/python verify_paired_retrieval_transport_v1.py \
  --preparation runs/2026-10-18-paired-retrieval-preparation-v1 \
  --run /path/to/new-run --output /path/to/new-report.json
```

Preparation is append-only: use `--prepare <new-directory> --repo <SpecGraph>
--store <external-sqlite> --model-path <existing-pinned-snapshot>` to make a new
cohort artifact with local inference. Neither preparation nor execution overwrites
an existing run. CI runs deterministic synthetic transport regressions and
verifies frozen inputs, with no key, network inference or model loading.
