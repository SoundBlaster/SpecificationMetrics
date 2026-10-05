# Jev independent machine-reference comparison — 2026-10-05

## Result

Six prompt variants were screened against an isolated model reviewer's source
annotations. **No improvement over baseline was demonstrated.** Neither
finalist meets the preliminary discovery targets. This is machine-reference
agreement on selected examples, not measured human accuracy or production
prevalence.

| Development prompt | Eligible recall | Eligible precision | False exclusions | Abstention |
| --- | ---: | ---: | ---: | ---: |
| baseline-v1 | 3/4 (75%) | 3/4 (75%) | 1 | 0% |
| boundary-test-v2 | 1/4 (25%) | 1/1 (100%) | 3 | 0% |
| singleton-v1 | 3/4 (75%) | 3/5 (60%) | 1 | 0% |
| owned-rule-v1 | 3/4 (75%) | 3/5 (60%) | 1 | 0% |
| mechanical-boundary-v1 | 3/4 (75%) | 3/4 (75%) | 1 | 0% |
| bounded-evidence-v1 | 3/4 (75%) | 3/4 (75%) | 1 | 0% |

All variants used the same 12 sites in 12 development families (4 eligible,
6 excluded, 2 needs_review). The deterministic tie-break selected
`bounded-evidence-v1`; selection does not mean it outperformed baseline.

| Holdout prompt | Eligible recall | Eligible precision | False exclusions | Abstention |
| --- | ---: | ---: | ---: | ---: |
| baseline-v1 | 1/2 (50%) | 1/2 (50%) | 1 | 0% |
| bounded-evidence-v1 | 1/2 (50%) | 1/2 (50%) | 1 | 0% |

Holdout contains 10 sites in 9 unseen families: 2 eligible and 8 excluded.
Both variants made identical label decisions. Concern-kind agreement was 10/10
on policy/mechanics, but there were no variant/unknown reference cases.
The paired eligible-recall delta interval is [0, 0] because decisions are
identical on these examples; it does not establish population equivalence.

## Concrete failure modes

- `sg-033`: both finalists call the workspace-allocation guard `policy` but
  `excluded`. The reference identifies the six-condition authority binding as
  eligible. A high policy probability (0.98) does not imply a remaining
  opportunity label. This is disagreement about adoption suitability, not
  failure to recognize authority policy.
- `sg-018`: an existing `FirstMatch` of named `PredicateSpec` branches is
  classified eligible/policy instead of excluded/policy. This would overcount
  remaining opportunities unless existing ownership is supplied reliably.
- `sg-019` on development: acceptance-criterion coverage/recovery is excluded
  although the reviewer identifies a durable coverage rule inside the loop.
- Both ambiguous development references receive non-abstained
  labels. Merely adding abstention wording did not elicit `needs_review` here.

These are hypotheses about failure causes, inferred from source and disagreements;
Jev Choice returns no explanation. The reviewer itself may be wrong. Evaluate
these exact sites with human/second-reviewer adjudication before rewriting the
rubric or treating labels as ground truth.

## Evidence

- 60 independent machine annotations: 21 eligible, 33 excluded, 6 needs_review.
- No prior proposed labels or Jev answers were shown to the isolated subagent.
  No human adjudication was performed. Blindness is an explicit review record,
  not a technical guarantee against pretraining knowledge or shared model biases.
- 72 fresh development + 20 fresh holdout requests: **92 total**, no retries,
  no cached replies and no provider/contract errors.
- Requested/returned model: `jev-1.13.0`; immutable model revision unavailable.
- API-reported usage: 135,932 development + 35,770 holdout = **171,702 tokens**.
  No monetary cost estimate is inferred from this count.
- Exact prompts, raw provider answers/probabilities/usage, selected IDs and input
  digests are in `development.json`, `holdout.json` and `finalists.json`.
  Compact receipts omit repeated source contexts; their hashes bind to the frozen
  corpus contexts. Local full-run digests are retained for provenance.
- The annotation, split and targets were frozen before hosted calls; finalist
  configurations were frozen before holdout. Family splits were label-independent.
- Nine offline Node tests and thirteen Python unit tests passed; corpus
  validation covered 61 cases. Source extraction matched pinned SpecGraph Git
  objects. CI does not make hosted calls.
- Provider/contract failures are excluded from the label confusion matrix and
  reported separately; failed calls cannot receive credit for a `needs_review`
  or `unknown` reference. Coverage uses all requested cases as its denominator.

## Next experiment

Do not install either prompt as an automatic exclusion gate. First adjudicate
the false exclusion, already-owned false positive and mixed-scope cases. Then
test one context factor on development: an explicit, source-grounded ownership
fact and the exact decision boundary, with no expected label. Existing inventory
evidence must be distinguished from candidate model conclusions. Retain the
same opportunity/concern-kind definitions. Collect a new holdout with more
eligible families and ambiguous/variant examples before confirmation.
