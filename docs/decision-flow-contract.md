# Local FirstMatch result-to-branch evidence v1

```sh
specification-metrics application-sites PYTHON_IMPORT_ROOT \
  --profile python-decision-flow-v1 --scope-manifest scope.toml --output flow.json
```

Profile: `specification-metrics.python-decision-flow/v1`. Advisory, offline,
`metric_effect: "none"`. Raw S/U, counting rule v9, registry/collection/store
contracts and the two preceding application-site profiles remain unchanged.

## Evidence and unit

The `applications` field contains the unchanged
`python-decision-applications/v1` report, including source/scope digests,
provisional state, parser/role issues, factory anchors and snapshot-bound call
IDs. Flow rows reference those IDs; they do not invent a new accepted fact.

`examined_bindings` counts calls whose immediate result/projection is assigned
to a single identifier. It does not count all calls or all variables. Each row
has exactly one status:

| Status | Meaning |
| --- | --- |
| `linked` | Supported straight-line syntax reads this definition in the next supported if-condition. |
| `not_linked` | The definition was overwritten/deleted/mutated before a supported branch, or the supported scan reached scope end. Not evidence of dead code/specifications. |
| `unresolved` | Receiver binding, scope, condition or intervening effects/control flow exceed the supported analysis. |

```text
examined_bindings = linked_bindings + not_linked_bindings + unresolved_bindings
```

A linked row records the condition anchor/text, actual result projection and
the scanner's existing if-candidate fingerprint. Join only under matching source
and scope digests. `stop` records the first branch or barrier; reasons explain
why analysis ended. This does not reduce U or establish that an entire condition,
branch body or requirement is implemented by a Specification.

## Supported straight-line subset

An origin must be a direct statement in a function/method body:

```python
error = POLICY.decide(ctx).value
if error:
    findings.append(error)

decision = POLICY.decide(ctx)
if not decision.matched:
    return
```

Track an immediate `.value`/`.matched` binding or a raw MatchResult later read
through exactly one `.value`/`.matched` access. Supported conditions are that
single reference, parentheses/`not`, or one such reference compared with primitive
literals. Plain MatchResult truthiness is unresolved. Calls, Boolean combinations,
walrus assignments, aliases, additional names and custom transformations in the
condition are unresolved. No semantic equivalence or path feasibility is proved.

Comments, pass and unrelated primitive-literal assignments may intervene.
Writes/deletion of the tracked name or its attributes/subscripts invalidate the
origin. An intervening call, alias assignment, return/raise, definition, loop,
try/with/match, unsupported mutation or unrelated if stops analysis explicitly.
Do not inspect either branch body or continue beyond that first if.

Only direct function-body assignments qualify: module/class-body definitions,
assignments nested under control flow, chained/destructuring assignments and
global/nonlocal bindings are unresolved or outside the immediate-identifier
inventory. No CFG joins, alias propagation, closure/interprocedural analysis,
runtime execution, external frame mutation, tracing hooks or concurrency proof.

## Frozen SpecGraph #787 pilot

Revision `59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe`, 27 Python files, explicit
`tools` import root, same manifest as the
[FirstMatch application pilot](firstmatch-application-pilot.md):

```text
source_digest: 298755afd8a37fc2c9e0771254a3e15c1ff03afb820095d75c86e0bbc8041d87
scope_digest:  62ddbbda5e48f7dca782fb30f078b8774c2cc1de898d4b4ed0ec65d08636fc54
```

Of the three inventoried calls, one has a supported immediate identifier
binding. It links `BINDING_ERROR_SPEC.decide(...).value`, assigned at
`traceability/publication.py:238`, to `if binding_error` at **246:5**.
Scanner fingerprint:
`python:traceability/publication.py:if:42757840404af310:1`.

Result: **1 examined binding, 1 linked, 0 unresolved, 0 not linked**.
The call passed directly as an argument has no identifier origin; the call in
the conditional expression remains outside this straight-line binding subset.
They remain visible in `applications`: 2 direct consumptions, 1 mixed, 0 unresolved.
Raw S/U remains **23/89**. No coverage percentage or execution claim is derived.

## Validation

Tests cover primitive/negated/comparison guards, raw MatchResult projections,
overwrites (including a newer decision), deletion/mutation, side-effect/control
barriers, aliases, closure definitions, nested/module/global scopes, unresolved
receivers and absent supported consumers. CLI regression verifies the scanner
fingerprint and byte-identical measurement/preceding-profile outputs.
