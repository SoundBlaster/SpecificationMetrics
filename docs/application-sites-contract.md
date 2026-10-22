# Python Specification application diagnostics v1

`application-sites` explains one source-level distinction that raw S/U does not
currently express. Its profile is
`specification-metrics.python-if-applications/v1`. It is advisory, offline,
and has `metric_effect: "none"`. Counting rule v9, fingerprints, registry/store
contracts and all existing `scan`, `measure`, and `collect` outputs stay intact.

```sh
specification-metrics application-sites ../SpecGraph \
  --scope-manifest /path/to/source-roles.toml \
  --output /tmp/application-sites.json
```

The command accepts repeatable `--include` restrictions using the scanner's
existing rules. It reads only the selected application source snapshots. It
never imports or executes Python, calls a model, or reads an excluded dependency
to improve resolution. Include both the application and its policy modules.

## Categories

Each supported candidate containing an examined `.is_satisfied_by(...)` call
receives exactly one category:

| Category | Evidence | Example |
| --- | --- | --- |
| `direct_application` | Every examined call resolves, and the condition consists only of these calls, parentheses, `not`, `and`, and `or` | `if not READY.is_satisfied_by(ctx):` |
| `mixed_expression` | Every examined call resolves, but additional condition syntax remains | `if READY.is_satisfied_by(ctx) and ctx.extra:` |
| `unresolved_call` | At least one receiver cannot be proven in the supported binding subset | `if parameter.is_satisfied_by(ctx):` |

Boolean composition of confirmed applications stays direct. An unresolved call
takes precedence over mixed/direct, while evidence for each call is retained.
Mixed is a syntactic distinction, **not** a finding that the extra expression
is domain policy or should be extracted. Unresolved is uncertainty, not a
negative judgment on the code. No examined call is also not evidence of a new
inline policy.

## Supported binding subset

V1 proves module-level constants created by a direct call to the synchronous
`PredicateSpec` constructor imported from `specification_core`. Constructor
aliases, module aliases, explicit relative imports and static re-exports are
supported. Target evidence contains the factory's path, line, UTF-8 byte column
and constructor. The whole selected-source digest binds that evidence to the
snapshot; the candidate retains its existing fingerprint and anchor.

Explicit submodule imports work with both regular packages (`__init__.py`)
and namespace packages. A submodule file's presence alone does not establish
that it was imported. Package shadowing and ambiguous module paths remain
unresolved.

Same-named local factories do not qualify. Duplicate/reassigned bindings,
wildcards, conditional bindings, cycles, missing or ambiguous source modules,
parse failures, module `__getattr__`, local shadowing, and observed receiver
attribute mutations prevent confirmation. Bindings must textually precede the
expression being resolved. Class-body conditions and `global`/`nonlocal` scopes
are conservatively unresolved. Method bare-name lookup skips the class namespace
and still checks enclosing function bindings. Parameter and local constructor instances, custom
Specification classes, inline constructors and async factories are unresolved.

This is static source binding under ordinary import semantics. It is not a
proof against arbitrary external monkey patching, import hooks, aliases used
to mutate an object, or an incompatible installed library. The report does not
establish that a call executes, is valid at runtime, or fulfills a requirement.

## Syntax and completeness boundaries

Only existing Python `if` candidates (`if_statement`) are analyzed. `elif`,
conditional expressions, comprehension filters, matches, loops, Swift and Rust
are outside this profile. Other discovered candidates contribute to
`unsupported_candidates`; constructs the current scanner does not discover are
not included in that number. In particular, this is not total branch coverage.

Only the condition is examined. Statements in its body are not evidence for
the outer condition. Deferred lambda bodies and comprehensions are not traversed.
Arguments of an application call are not classified: direct means the guard's
Boolean result comes directly from the application, not that constructing its
context contains no other logic. Typed decision APIs such as `.decide(...)`
are outside this profile and do not count as examined application calls.

The counters partition analyzed if candidates:

```text
analyzed_if_candidates = direct_application + mixed_expression
                       + unresolved_call + if_candidates_without_application_call
all discovered candidates = analyzed_if_candidates + unsupported_candidates
```

`provisional` carries the scanner's unresolved source-role/parse/marker status.
A false value means only that those prerequisites are complete; it does not
mean every binding resolved or all syntax is supported. Source/scope digests
must agree before joining this report to primary metrics. The command exits
successfully for advisory unresolved/provisional reports; scan/read errors
still fail normally. There is no new merge gate.

## Why U is unchanged

For `if ctx.ready`, the old measurement can be S=0, U=1. Replacing it with
`READY = PredicateSpec(...)` and `if READY.is_satisfied_by(ctx)` gives S=1, U=1
under counting rule v9. This report adds one `direct_application`, without
subtracting it from U. Implementing the future `uses_specification` exclusion
requires a separately reviewed counting contract, broader binding coverage and
explicit migration of historical comparisons.

See the [frozen SpecGraph pilot](python-application-sites-pilot.md) for measured
source identities, three resolved real applications, and the regression learned
from method/global name lookup.
