# Expression-fit rubric v2: evidence of a decision's role

**Status: reviewable proposal; not evaluated or activated in production.**

Machine-readable questions: [expression-fit-v2.json](rubrics/expression-fit-v2.json).
The previous expression rubric is `v1-diagnostic`; this proposal is **v2**.
The architecture profile retains its separate version 2. Wire labels and the
production candidate-classification contract remain unchanged.

## Why this revision exists

The [two independent annotation rounds](runs/2026-10-13-balanced-context-reference/README.md)
agreed on both axes for 14/18 states. Path declaration/bundle answers reversed
on unchanged evidence; an isolated permission test varied on opportunity, and
gate precedence varied between policy and variant behavior. These observations
show annotation instability. They do not establish a provider's internal cause.

The earlier rubric named categories but left their boundaries implicit. V2
requires an evidence-backed account of the exact decision's role and supplies
tie rules. This is a proposed prevention, **not a demonstrated semantic fix**.

## E1. Find the semantic decision before assigning labels

Describe the target using three questions:

1. **Subject:** which value, entity or domain fact is being assessed?
2. **Alternatives:** what does this exact expression distinguish?
3. **Role:** what does that distinction decide here, according to supplied
   code or a declared contract?

For example, `gate != "none"` has alternatives active gate / no active gate.
A containing branch can establish its role as giving gate handling precedence
over ordinary refinement. A different use could merely choose an icon. The
operator and variable name do not settle that role.

Cite a decision witness: the target plus a relevant branch, return contract,
typed domain contract or requirement. **Pure specifications need no side effect.**
A declared predicate contract can be enough; the classifier need not observe a
writer executing or a filesystem being accessed. Do not demand every caller
when the decision is already established by supplied evidence.

Supporting fragments explain the target. They do not expand it. Do not replace
a boolean predicate with a later switch, an entire function or a more convenient
subexpression. Judge a selected assembly as a whole.

Decision witnesses are independent-annotation/reviewer evidence. Jev's fixed
Choice result does not supply that explanation; adapters must not manufacture
a provider rationale from its label or confidence.

## E2. Separate domain constraints from representation mechanics

| Question answered | Primary responsibility |
|---|---|
| Is this representation well formed, normalized or convertible into facts? | mechanics |
| Does this entity/reference/action satisfy a declared domain constraint? | policy |
| Both interpretations remain materially plausible and the role is missing | unknown |

An error or rejection proves that input is rejected; it does not alone prove
why that rejection belongs to domain policy or mechanics. A parser can enforce
policy, and a function named `safe_*` can implement ordinary technical checks.

For paths, look for the actual contract. A stated restriction on permitted
artifact references can establish policy even if enforcement is purely lexical.
A suffix or spelling normalization with no distinct domain decision can be
mechanics. A helper combining traversal restrictions and normalization, without
a settled contract or consumer role, may remain ambiguous. Do not invent a
confinement root or assume generic path validation is automatically policy.

Use the supplied contract's meaning. A name or generic description such as
"validates the manifest" does not establish which kind of validity is intended.

## E3. Distinguish obligation/permission from variant implementation

| Selected decision | Primary responsibility |
|---|---|
| Whether domain work is allowed or required | policy |
| Which domain obligation must be handled first | policy |
| How an already established activity is implemented for a domain variant | variant_behavior |
| Which parser handles an external token to produce typed facts | mechanics |

The active-gate predicate can establish lifecycle precedence. The subsequent
`GATE_ACTIONS[gate]` can select a specific handler. They are distinct targets.
An enum or sentinel test is not automatically variant behavior. Conversely,
being implemented in a domain module does not turn every variant dispatch into
policy. If a mixed target has no established primary contract, retain `unknown`.

## E4. Suitability requires a demonstrated decision role

`eligible` needs a stable domain or domain behavior-selection contract that
benefits from a named, addressable, observable Specification. One use is enough.
Immediate LOC/CC reduction, duplication, a global registry and executed effects
are not prerequisites. Eligibility does not prescribe one Specification per
branch or rule out placing behavior behind a protocol.

A permission-sounding key may suggest an authority topic. It does not alone
show whether a site defines a permission rule, adapts a previously computed
verdict or reports metadata. If that distinction changes suitability and is
unresolved, choose `needs_review`. Concern kind can still be settled if a
supplied semantic contract establishes the primary responsibility. Otherwise
retain `unknown` for that axis too.

`excluded` requires affirmative mechanics or existing-ownership evidence.
Failure to find policy evidence is not itself an exclusion. This prevents a
missing-context case from silently disappearing from consideration.

## E5. Same-decision ownership is a separate question

An explicit Specification declaration together with an evaluation path for this
same decision supports `excluded` as a *new opportunity*. Its responsibility can
remain `policy`. An import, naming suffix, another rule in the file or an
ordinary helper is insufficient ownership evidence.

Unknown ownership does not automatically force an otherwise clear fit suggestion
to `needs_review`, and it must never be represented as proved ownership.
Suggestions remain separate from the formal ownership analysis and reviewed
S/U state. The classifier does not certify canonical accounting from a limited
view of a source file.

## E6. Abstain for a material missing fact, independently on each axis

An uncertainty is material when identifying the missing fact explains how the
plausible labels differ. "The contract deciding whether this is representation
validation or reference admissibility is absent" is specific. "There might be
unshown code somewhere" is not enough to reject a clear local formatting rule.

The axes need not abstain together. Policy versus variant ambiguity can leave
opportunity clearly eligible. Explicit ownership can settle exclusion even when
primary responsibility remains mixed. Retain nonmaterial uncertainties alongside
clear labels; do not equate them with classification failure.

## Authored boundary illustrations

These are **author hypotheses illustrating the proposed definitions**, not
independent labels, real-source gold or inputs to blind annotation. No expected
v2 labels have been assigned to the eighteen source states.

| Supplied evidence | Proposed opportunity / concern kind | Reason |
|---|---|---|
| Serializer checks a trailing newline and appends it | excluded / mechanics | Complete local formatting role |
| Contract forbids absolute and parent-traversing artifact references; a pure predicate tests that contract | eligible / policy | Explicit domain admissibility; no file access required |
| Same path-shaped predicate, generic unsafe message, no settled semantic contract | needs_review / unknown | Rejection alone does not settle the role |
| Permission-sounding dictionary key with no defined meaning or use | needs_review / unknown | A topic clue does not establish the site's decision role |
| Typed contract defines an authority verdict, but the selected test's consuming role is absent | needs_review / policy | Responsibility established; fit still ambiguous |
| Contract directs unresolved blockers to be handled before routine refinement | eligible / policy | Lifecycle precedence |
| Contract chooses a platform-specific implementation of an already selected domain activity | eligible / variant_behavior | Stable domain behavior-selection contract; refactor form is separate |
| Decoder chooses integer or string parsing from an external tag | excluded / mechanics | Syntax adaptation, despite variant-shaped control flow |
| The same pure domain rule has an explicit Specification and evaluation path | excluded / policy | Already represented; responsibility unchanged |

The typed-verdict illustration does not imply that every observed metadata
adapter is policy. A supplied adaptation-only role can instead establish
mechanics. Judge the exact role rather than attaching a permanent category to a
field name across all uses.

## Plan for validation

1. Review the definitions and boundary illustrations as an architectural
   convention. Keep this proposal separate from raw historical annotation.
2. Prepare a NEW balanced reference with the same eighteen source states and
   architecture profile, replacing only the question rubric. Labels start blank.
   Give fresh contexts one view per target and two cases per evidence mode.
   Do not expose these authored examples, prior answers or the disputed mapping.
3. Obtain two fresh judgments per state under v2 (six balanced contexts, 36 case
   annotations). Review disagreements without forced consensus. Compare against
   v1 descriptively; changed annotators/batches prevent a causal improvement
   claim. A causal rubric comparison needs a concurrent balanced v1 arm.
4. Report per-axis and joint agreement, decisive coverage, abstention counts,
   case-specific missing facts, and ownership mistakes separately. Stable
   abstention on genuinely ambiguous inputs is useful but is not increased
   ability to identify rules. Lower disagreement achieved by abstaining on clear
   formatting, declared domain contracts and explicit ownership is a failure.
5. Freeze a provider-scoring reference and bounded provider protocol only after
   review. Keep raw provider classification and any formal evidence gate as
   distinct arms. New Jev/Luna calls require explicit authorization.

### Prevent rubric identity from disappearing

The existing `state_sha256` binds source/context/profile, while questions live
outside that state. A v2 rubric can therefore retain every state hash and still
define a different classification task. A future comparison must bind both
state and rubric/questions, including annotation instructions where applicable,
in a **task digest**. Never call v1/v2 a same-input repeat solely because their
state hashes match. Include these identities in the new annotation template,
reference review, cache identity and scoring manifest.

This PR prepares definitions and a validation plan. It does not create new
annotation packets, labels, provider requests or cache entries, activate a new
classifier default, or rewrite any historical run.
