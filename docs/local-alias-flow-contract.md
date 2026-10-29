# Bounded local-alias flow: proposed contract v1

Status: **implemented as an opt-in profile**. Contract date: 2026-10-26.
This document specifies the opt-in `python-decision-flow-alias-v1` profile
with report identity `specification-metrics.python-decision-flow-alias/v1`.
The existing profile remains available separately.
The separate [Python reference model](../evals/local-alias-reference-v1/README.md)
is implemented and checked against the frozen matrix.

The implemented [decision-flow v1](decision-flow-contract.md) stays unchanged.
Its alias barriers, existing status/reason/stop anchors, frozen assessments,
call inventory and IDs remain valid. Raw S/U, counting rule v9, reviewed
exclusions and collection/storage contracts are outside this proposal.

## Question and unit

For one recognized FirstMatch call with an immediate identifier binding, does
the **first encountered subsequent if-condition in the same supported block**
read that origin through supported local name copies?

Keep one row per original call binding. Aliases do not create Specifications,
origins or extra `examined_bindings` rows. Analyze each origin independently;
an alias created before that origin is not recovered. Reuse the existing
receiver, source/scope completeness, function/loop-body and enum checks.
Unsupported scopes and global/nonlocal directives in the containing function
remain unresolved. No branch joins, loop exits/backedges or cross-iteration
state, escapes, interprocedural analysis or runtime execution are added.
Inherited gate reasons include `global_or_nonlocal_scope` for those directives
and `straight_line_function_body_required` for origins nested inside an if.

The claim is a source-level read dependency, conditional on reaching the
condition. It does not establish branch truth, reachability, safe evaluation,
matching success, body output, requirement coverage or program equivalence.

## Abstract value and names

For each row create one symbolic origin token `o`, tied to that row's
snapshot-bound `application_id`. It is an analysis identity, not a runtime
object address. Keep the origin projection `p` as `raw`, `value` or `matched`.

Maintain a finite map `E` over a name-history set `H`:

| State | Meaning |
| --- | --- |
| `Origin(o, p)` | Name retains the original result/projection |
| `Other` | Name was replaced with a supported primitive literal |
| `Deleted` | Name was deleted after a supported binding |

Initially `H = {d}` and `E[d] = Origin(o, p)` for the immediate binding `d`.
`H` also retains names introduced by supported copies from names already in
`H`, even after rebinding/deletion or copying an `Other` value. An untracked
name has no inferred value; never treat it as `Other` by default.
States describe definition provenance, not equal runtime values. Assigning a
literal yields Other even when that literal could equal the original output.

Copy/rebind/delete transitions operate on **name bindings**. No transition
asserts immutability of the underlying result or its payload. Object writes,
calls and unsupported effects stop analysis instead of being approximated.

## Transitions in the same block

Process following sibling nodes in source order. Evaluate the RHS abstract
state before updating the LHS, including self-copies. All assignment targets
below must be single plain local identifiers without value annotations.

| Next statement | Required state | Transition / outcome |
| --- | --- | --- |
| `x = y` | `y in H`, `E[y]` is Origin or Other | Add `x` to H; copy E[y] to E[x] |
| `x = x` | Same bound-source requirement | Preserve its state; retain the event |
| `x = y` | `y in H`, E[y] is Deleted | unresolved / `alias_copy_source_deleted` |
| `x = y` | y is untracked | unresolved / `intervening_expression_barrier` |
| `x = literal` | x in H | E[x] becomes Other; other names retain their states |
| `x = literal` | x not in H | Ignore this unrelated primitive assignment |
| `del x` | x in H, E[x] is Origin or Other | E[x] becomes Deleted; keep x in H |
| `del x` | x untracked or already Deleted | unresolved / `deletion_state_unproven` |
| `x: T` | Plain local identifier, no RHS | No state change; annotation is not evaluated |
| Comment or `pass` | Within resource bound | No state change |
| Attribute/subscript write/delete or augmented assignment | Any | unresolved / `object_mutation_barrier` |
| Projected copy `x = y.value` / `.matched`, destructuring, chaining, walrus, annotated assignment with RHS | Any | unresolved / `intervening_expression_barrier` |
| Call, other unsupported expression | Any | unresolved / `intervening_expression_barrier` |
| Return/raise/assert, definition/closure, nested control-flow statement | Any | unresolved / `control_flow_or_effect_barrier` |

`literal` means exactly the primitive-literal syntax accepted by implemented
flow v1; do not add containers, f-strings or expressions under this name.
Calls are barriers even after all known names have lost the origin. A later
decision call is another row's origin, not permission to cross the call here.
The initial origin itself continues to use the existing inventory/origin gate;
the narrower assignment rules above apply to subsequent propagation steps.

Do not stop at the first rebind/delete of the original name: another name may
still hold Origin. Do not scan a branch body or proceed beyond the first if.

## Classifying the first if

First identify a single reference in the existing supported condition grammar:
parentheses/negation and the accepted literal or verified enum comparisons.
The reference name must belong to H. An unrelated name/if, Boolean combination,
unsupported projection/comparison or extra read yields unresolved /
`condition_or_control_flow_unsupported`; never skip it to find a later match.

For an Origin state, apply the original projection rules: a raw MatchResult
needs exactly one `.value` or `.matched` projection; a value/matched origin
uses the name directly. Copies preserve p. Raw MatchResult truthiness and
projecting an already projected origin remain unsupported.

For Other/Deleted states, identify the reference using the origin's permitted
projection shape, then report the lost dependency. This does not claim the
literal/deleted value supports that attribute access or evaluates safely.

| Consumer reference state | Status | Reason |
| --- | --- | --- |
| Origin(o, p), valid projection | linked | `local_alias_read` |
| Other | not_linked | `branch_reference_rebound` |
| Deleted | not_linked | `branch_reference_deleted` |
| No valid supported reference in H | unresolved | `condition_or_control_flow_unsupported` |
| Supported block ends before an if/barrier | not_linked | `no_supported_branch_before_scope_end` |

For every first-if outcome, `stop` is that if's anchor. Negative outcomes do
not contain linked-branch evidence. For a barrier, `stop` is the barrier node.
For scope end, `stop` is null. Therefore this new profile intentionally differs
from v1's immediate rebind/delete stops and reasons, including when no alias
exists. The old profile must keep its behavior unchanged.

`not_linked` is relative to this origin and selected next branch. An original
value may remain available through another name. Deleted-name reads can fail
if reached; neither negative outcome is a proof of safe execution or dead code.

## Bounds and precedence

Proposed defaults: at most **8 historical tracked names**, including the
original, and **64 following named sibling nodes**, including comments/pass
and the terminal if/barrier. The origin and blank lines are not counted.
Overwriting a name does not free its history slot. Self-copy uses no new slot.

Before processing a node, stop if it would be node 65: unresolved /
`statement_limit`. Before adding a ninth name, stop at that copy: unresolved /
`alias_name_limit`; do not apply it. Reaching an if at node 64 is allowed.
These are deterministic support bounds, not measured performance guarantees;
changing them requires a versioned contract update. Smaller fixture limits may
be injected only by the future test harness, not an implied CLI feature.

Precedence: existing parse/receiver/scope gates; node limit; syntax/effect and
bound-source checks; new-name limit; transition or terminal if classification.
Default unmatched syntax always abstains. The three status counters must
partition the unchanged immediate-binding inventory, including unresolved
resource/scope cases; never omit rows to improve a ratio.

## Evidence required from the future profile

Retain existing source/scope digests, call ID/path/anchor, binding variable,
origin projection and completeness information. Linked branches retain the
condition, projection, candidate fingerprint and enum/loop evidence.

Add an `alias_flow` evidence object with:

- Contract version, effective bounds and one symbolic origin token.
- Ordered source events for the supported copy/rebind/delete operations,
  their anchors, source/target names and touched before/after abstract states.
- The terminal reference name/state/projection when a supported if is reached.
- On a bound/barrier, the exact stop node and reason; the rejected operation
  must not appear as an applied transition.

This is a static derivation, not an execution trace. Branch-body uses are
outside it. A consumer must not infer an entire if/body is implemented by the
Specification. Join evidence only under matching source/scope digests; source
case IDs, not snapshot application IDs, pair transformed source revisions.

## Acceptance matrix and known examples

[local-alias-flow-cases.json](local-alias-flow-cases.json) is a **proposed test
matrix**, not analyzer output or an independent gold set. It contains authored
unit fragments plus new-profile expectations for the 12 frozen
[source-backed alias variants](../evals/python-decision-flow-v1/counterfactuals/alias-v1/README.md).
The existing corpus labels/assessments remain frozen and still describe v1.

For the source-backed variants, the future profile must produce:

| Variant, three families each | Proposed result |
| --- | --- |
| Alias copy | 3 linked |
| Original local name rebound after copy | 3 linked |
| Alias rebound before guard | 3 not linked |
| Alias deleted before guard | 3 not linked |

All 12 remain unresolved in the earlier flow v1. The alias profile returns the
outcomes above. Positive means only selected-condition dependency.
For publication, rebinding `binding_error` can preserve its alias guard while
changing the message read from the original name inside the body.

Before implementation is accepted:

1. Review the transitions, outcome/stop semantics and proposed bounds.
2. Implement a bounded reference state model and validate the authored matrix,
   including exact-limit/overflow, self-copy and read-after-delete cases.
3. Add the Rust opt-in profile and compare it with the reviewed model; keep
   implemented v1 and preceding profiles byte-identical for the same inputs.
4. Replay the frozen real/counterfactual datasets under each explicitly named
   profile. Record new expectations/assessments separately; check call inventory
   stability and the status partition. Alias count never inflates bindings.
5. Retain all body-output, unsafe-evaluation and unknown-effect limitations.
   No automatic U exclusion or review enforcement follows from this pilot.

The initial document validation checked JSON structure, IDs, anchors and frozen
source correspondence. The separate reference implementation now matches all
47 unit cases and the 12 source-backed alias expectations, with three linked
real controls. It records supplied factory/enum preconditions explicitly.
The Rust profile matches those 47 frozen unit expectations and the 15 source
outcomes (three controls and twelve synthetic variants) of the Python reference.
The `scope.global` unit supplies the reference's explicit recognized-origin
precondition in the test harness; the production resolver may decline it earlier.
No totality or population-accuracy proof follows.
