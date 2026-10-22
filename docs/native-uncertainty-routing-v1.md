# Native uncertainty routing · v1

Status: **implemented for offline shadow evaluation; not active in the live runner**.
Policy: `specmetrics.native-uncertainty-shadow/v1`.
Provider profile: `jev-coreinfra / jev-1.13.0`, current pinned SDK 0.9.0.

## Intent and authority

Use inexpensive System One classification first. Send a valid but unresolved or
ambiguous proposal to an independent ordinary Luna review. Preserve unresolved
review outcomes explicitly for a human. Neither stage accepts facts, creates a
Specification, changes S/U or obtains publication authority.

The PR714 live pilot exposed a routing gap: categorical consistency alone can
retain a proposal whose selected category is only a plurality. This contract
adds a distribution-based review signal. The original pilot, router v1, frozen
inputs and spent dispatch reservation remain unchanged. This version is a
**post-observation design**, not a preregistered successful experiment.

## Three different meanings of confidence

| Field | Meaning for this policy |
| --- | --- |
| `evidence_confidence=supported/limited/insufficient` | A categorical judgment about supplied evidence, evaluated by the existing router. |
| Native `confidence` | Provider-reported scalar, preserved in diagnostics; no assumed calibration or numeric cutoff. |
| Native `probabilities` | Reported category masses used to test concentration. Not probabilities that the code assessment is correct. |

These fields must not substitute for each other. A `supported` label does not
override a diffuse distribution. A concentrated distribution does not establish
source sufficiency, ownership, semantic truth or correctness of the model.

## Input contract

- An immutable source-bound task with repository, revision, target interval,
  source/question digests, rubric, category version, intended action and required
  axes. Reuse the existing categorical binder and original missing premises.
- The exact saved response bytes, HTTP status and expected native model/profile.
  Parse with the current SDK and existing replay bridge before evaluating this
  policy. Invalid source binding is rejected before policy evaluation.
- Catalog coverage, finite values, probability mass and model identity must pass
  the existing SDK/bridge contracts. Do not normalize, repair, retry or replace
  malformed metadata. A missing/invalid/failed capture is incomplete analysis.
- This consumer supports native Jev only. Reject ordinary-model profiles rather
  than synthesizing distributions or treating missing metadata as certainty.
  Adding another model/profile requires its own explicit qualification.

Receipt hashes establish local integrity, not authenticated remote execution.

## Relevant axes

Always inspect `concern_kind` **and** `evidence_confidence`, plus every axis named
in `binding.required_axes`. Also inspect `ownership` for `reuse_specification`
and `exclude_owned`; inspect `tool_responsibility` for `delegate_tool`.

For `assess_role`, unknown ownership/tool responsibility is allowed unless the
binding explicitly requires those axes. It does not establish absence or allow
creation. Creation still requires all existing checked-evidence and authority
premises; this policy adds no new permission. Additional action-specific required
axes extend this set and cannot remove the two core axes.

## Strict-majority rule

For each relevant axis, let `c` be the returned category, and let `p(k)` be each
reported category mass, including `unknown` when present:

```text
selected_mass    = p(c)
alternative_mass = sum(p(k) for every k != c)
strict_majority  = selected_mass > alternative_mass
needs_review    = any relevant axis lacks strict_majority
```

Compare decimal representations of the SDK-projected numbers. Do not renormalize
the distribution, drop `unknown`, substitute the largest category, or aggregate
unrelated axes into an average. A tie goes to review. With unit mass this means
strictly more than 50%; the formula remains explicit for SDK-accepted rounding.

This is a conservative **routing convention**: the selected answer must outweigh
all alternatives together to bypass this signal. Its boundary follows from that
convention, not a fitted threshold from four examples. It does not claim optimal
cost, calibrated confidence, or adequate uncertainty detection. A confidently
wrong majority still passes; low native scalar confidence alone is not handled
by v1. Measure that residual separately before introducing another signal.

## Ordered decision table

| Priority | Condition | Shadow route | Status |
| --- | --- | --- | --- |
| 1 | Original analysis incomplete, or required native metadata unavailable | `stop_incomplete` | `analysis_incomplete` |
| 2 | Existing semantic/evidence rules select review | `ordinary_review` | `needs_review` |
| 3 | Any relevant axis lacks strict majority | `ordinary_review` | `needs_review` |
| fallback | No condition above | `retain_proposal` | `proposed_not_accepted` |

The executable decision uses `FirstMatch` with `IncompleteCaptureSpec`,
`ExistingReviewSpec` and `NoStrictMajoritySpec`, each in a separate file. Traces
preserve priority and skipped branches. Operational failure cannot trigger a
paid semantic fallback. Strong masses cannot cancel an existing review or
missing-premise finding. Routing is monotone relative to the original policy:
it can add review or stop incomplete analysis, never weaken an existing route.

## Luna review and unresolved outcomes

The shadow consumer does not prepare requests for its newly selected reviews or
send any requests. Replaying the existing bridge can construct an unexecuted
baseline review request; this is reported separately from shadow preparation.
A future versioned execution adapter must use the existing independent rich-review contract:

1. Prepare from the **same bound source/intent/proposal/spec context**; omit Jev
   labels, distributions and confidence from the independent review prompt.
2. Freeze the request, budget and transport limits before explicitly authorized
   dispatch. The original PR714 lease is spent; unused conditional slots cannot
   be retroactively consumed by this new policy.
3. Validate capture identity, source citations and rich-review schema with the
   existing inspector. A second label-only answer is not a rich review.
4. Preserve `needs_review` on material disagreement, insufficient evidence or
   unresolved interpretation. A failed/unrun review remains explicitly incomplete
   or unrun under that inspector; do not present it as resolved. Do not recurse.
5. A resolved review remains an unaccepted proposal. Display original category,
   review category, selection reason, missing evidence and explicit unresolved
   status in the eventual review report. Human acceptance remains separate.

## Validation and activation

Boundary tests cover exact ties, plurality, strict majority, ambiguity on the
evidence axis despite a strong role, irrelevant versus explicitly required axes,
original-review precedence, malformed metadata and incomplete-response priority.
Fresh synthetic tests establish the rule implementation, not classification
quality. Guard network access during tests.

The replay consumer verifies the original PR714 result inventory with its frozen
local-runtime verifier, reparses all four saved captures, and records the old and
shadow routes separately. It does not modify originals, execute Luna, spend
inference budget or count hypothetical reviews as real calls. The original
runtime qualification limitation remains: this real-capture comparison is not
claimed portable across Python builds/hosts. CI runs synthetic policy checks.

From `evals/jev-classification` in the repository environment:

```sh
../../.venv/bin/python -B -W error -m unittest -v test_native_uncertainty_v1.py
../../.venv/bin/python -B replay_native_uncertainty_v1.py
```

Activation is a separate integration change after contract review. Required
evidence: preserved original outputs; no degradation of invalid-response handling;
additional review count and reason per case; no new write/acceptance authority.
Semantic quality, review usefulness, latency and cost require a separately
authorized evaluation on independent cases. The four observed cases cannot
calibrate confidence or establish a quality improvement.

## Observed offline comparison

| Case | Selected role mass / other mass | Evidence category mass / other mass | Original route | Shadow route |
| --- | --- | --- | --- | --- |
| D01 | 0.43 / 0.57 | 0.53 / 0.47 | retain | review |
| D02 | 0.43 / 0.57 | 0.56 / 0.44 | retain | review |
| D03 | 0.48 / 0.52 | 0.47 / 0.53 | retain | review |
| D04 | 0.96 / 0.04 | 0.58 / 0.42 | retain | retain |

The shadow selects **three additional hypothetical reviews**; actual new calls
are **zero**. Their accuracy, usefulness and cost are unknown. D04's evidence
scalar confidence is only 0.37 despite a majority; retaining it illustrates the
explicit difference between this concentration rule and a scalar-confidence
threshold. The [separate comparison artifacts](../evals/jev-classification/runs/2026-10-19-native-uncertainty-shadow-v1/README.md)
preserve response identities, exact decimal masses, original routes and traces.
