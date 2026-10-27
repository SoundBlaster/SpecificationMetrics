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

An origin must be a direct statement in a function/method body or in the body
of an enclosing `for`/`while` loop. Nested loops are supported when every
enclosing block between the origin and its function is a loop body. The read
must be in the same block after the assignment; there is no loop-back, exit,
loop-else or cross-iteration inference:

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
literals. A binary `==`, `!=`, `is` or `is not` comparison can also use a verified
same-module enum member as described below. Plain MatchResult truthiness is
unresolved. Calls, Boolean combinations,
walrus assignments, aliases, additional names and custom transformations in the
condition are unresolved. No semantic equivalence or path feasibility is proved.

Comments, pass and unrelated primitive-literal assignments may intervene.
Local identifier annotations without a value may also intervene: they do not
evaluate the annotation or overwrite the binding. An annotation with a value
is still an assignment. Annotation-only attribute/subscript targets remain
unresolved because evaluating the target may have effects.
Writes/deletion of the tracked name or its attributes/subscripts invalidate the
origin. An intervening call, alias assignment, return/raise, definition, loop,
try/with/match, unsupported mutation or unrelated if stops analysis explicitly.
An intervening `assert` also stops with `unresolved`, even when it checks the
tracked result: assertion success is not a supported if-candidate link. Do not
inspect either branch body or continue beyond that first if.

Inventory and supported flow origins are separate. A call/projection used as an
immediate assignment RHS with an identifier target contributes a binding row,
including module/class-body assignments, assignments nested under control flow,
and global/nonlocal bindings. Module/class bodies, global/nonlocal bindings and
origins nested under unsupported control flow (such as an `if` or `try`) produce
`unresolved`; they are not omitted from the binding inventory. Only the direct
function/loop-body subset above can establish a supported flow link. Scope
directives are checked over the entire containing function body, including
directives outside the origin's loop.

Without such an identifier target, there is no binding row: destructuring or
attribute/subscript assignment targets, argument/return consumption and a call
embedded in a conditional-expression RHS remain in `applications` only. For
other unsupported assignment shapes (including chained assignments), retain an
`unresolved` row when the call inventory supplies an immediate identifier
binding; otherwise retain only the call. Inventory presence is not proof of
supported scope. No CFG joins, alias propagation, closure/interprocedural
analysis, runtime execution, external frame mutation, tracing hooks or
concurrency proof.

## Verified same-module enum comparisons

```python
from enum import Enum

class Disposition(Enum):
    IGNORE = "ignore"
    ADD = "add"

def repair(nodes):
    for node in nodes:
        decision = REPAIR_RULE.decide(node)
        if decision.value == Disposition.ADD:
            apply(node)
```

Require one undecorated, module-level class in the current source file, defined
before the comparison, with exactly one verified `enum.Enum` base. Direct
`from enum import Enum` aliases and `import enum` module aliases are supported.
The class body may contain comments, docstrings, pass and unique, ordinary
member assignments to primitive literals. The requested member must exist.
Reject leading-underscore control names, annotations, decorators, methods,
custom/multiple bases, `auto()`, dynamic values, imported enum classes, class
aliases and other shapes outside this subset.

Do not infer enum identity from capitalization or attribute spelling. Reject
lexical shadowing, ambiguous/rebound class or base names, selected local modules
named `enum`, and observed attribute/subscript writes or `setattr`/`delattr`
mutations. Arbitrary external monkey-patching/import hooks remain outside the
static assumptions, as for factory resolution. Ordering, membership and chained
comparisons with enum members remain unresolved. This establishes local source
read provenance, not runtime type compatibility, execution or branch feasibility.

New linked branches retain optional evidence:

- `enum_member`: class/member names and their 1-based source anchors, in the
  binding's source file.
- `loop_anchors`: enclosing loop anchors, innermost first. This describes the
  syntactic iteration context, not iterations observed at runtime.

Absent evidence fields are omitted, preserving the original direct-function
link shape. Call inventory/IDs, preceding profiles, raw S/U and counting rule
remain unchanged. The [extension replay](../evals/python-decision-flow-v1/extensions/loop-enum-2026-10-23/README.md)
records the expected two-case improvement without rewriting frozen v1 labels.

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

### Review finding: annotation is not reassignment

The initial version incorrectly reported `value: str` as
`binding_reassigned_or_mutated`. A four-case diagnostic reproduced the error
alongside correct reassignment, call-barrier and unrelated-literal outcomes;
an isolated Python check confirmed that the annotation preserves the value.
The fix distinguishes annotation-only syntax before write invalidation.
Regression `annotation_only_locals_preserve_values_but_assignment_and_effectful_targets_do_not`
covers tracked/unrelated local annotations, unevaluated annotation expressions,
actual annotated assignment and effectful annotation targets. This corrects a
false negative; the original frozen pilot result is unchanged.

### Real-project corpus

The separate [real-source corpus](../evals/python-decision-flow-v1/README.md)
contains 29 unmodified examples from five projects, including other-API controls
and ordinary-code analogues. Its author labels were frozen before replay.
Agreement with the current bounded contract is reported separately from semantic
consumption and unsupported real usage; it does not establish population
precision/recall or authorize U exclusions.

### Proposed alias extension

The separate [bounded local-alias contract](local-alias-flow-contract.md)
proposes a new opt-in profile and authored acceptance matrix. It tracks value
provenance through name copies and distinguishes rebinding/deleting one name
from changing its other aliases. It is not implemented; this v1 profile keeps
its existing alias barrier and all historical outcomes unchanged.
