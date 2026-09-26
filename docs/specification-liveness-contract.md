# Specification liveness contract

This contract defines liveness classification for named Specification
declarations. Counting rule v3 implements a conservative subset for Python;
Swift and Rust are retained as `unknown` pending language-specific analyzers.

## Unit and source boundary

The unit is one recognized named Specification declaration, identified by a
resolved symbol within a language module or crate. Anonymous factory sites
such as `PredicateSpec { ... }` remain counted at their source location; this
contract does not try to prove that their containing function executes.

Only runtime uses from the measured `application` source set establish a use.
References that occur only in tests, examples, generated files, vendored
frameworks, or explicitly excluded files do not keep an application
Specification live. The use search crosses files only when imports and module
ownership resolve to the declaration.

## Status rules

Each named declaration receives exactly one status:

| Status | Rule | Effect on `S / U` |
| --- | --- | --- |
| `live` | At least one resolved runtime use, including construction, passing the value to a Specification evaluator/combinator, runtime `isinstance`/`issubclass` checks, class patterns, or an explicit runtime registry/factory value. | Count the declaration in `S`. |
| `dead` | No resolved runtime use, the complete owning module/target is in scope, the symbol is not externally visible, and no unresolved dynamic lookup could refer to it. | Exclude the declaration from `S`. Its internal decision sites remain excluded from `U`. |
| `unknown` | Visibility, source completeness, symbol resolution, reflection, dynamic lookup, macros, or another supported uncertainty prevents proving either status. | Keep the declaration in `S` conservatively and mark the report provisional until reviewed. |

Text in comments and strings, type-only annotations, and references that only
declare the Specification itself are not runtime uses. A test-only reference
does not change a `dead` result. A statically registered factory is a runtime
use even when a later dispatcher selects it by a dynamic key. A dynamic lookup
with no complete, resolvable registry makes every plausible target `unknown`;
it never proves a target dead.

The closed-world boundary must be explicit and complete for the owning
Python package, Swift target, or Rust crate. A source-role manifest alone does
not prove that external consumers are absent. Public or exported declarations
remain `unknown` unless the measurement explicitly establishes a closed-world
boundary for them. Parse errors, unresolved imports, or unassigned source files
that could contain uses also force `unknown`.

## Language-specific evidence

| Language | Named declaration | Resolved runtime use | Externally visible or dynamic cases |
| --- | --- | --- | --- |
| Python | A class recognized through a Specification base class. | Resolve imports/aliases across the measured package; count construction or passing the class/instance to a known evaluator, combinator, or explicit registry. | A non-private importable class, a package export such as `__all__`, `getattr`/`globals` lookup, or unresolved plugin loading is `unknown` unless closed-world evidence resolves it. |
| Swift | A class or struct conforming to a recognized Specification protocol. | Resolve module symbols; count construction, passing the value to evaluation/composition, or a statically declared registry factory. | `public`/`open` API, Objective-C runtime name lookup, incomplete target membership, or unresolved registration is `unknown` unless closed-world evidence resolves it. |
| Rust | A type with a recognized Specification trait implementation. | Resolve crate/module paths; count value construction, passing the value to evaluation/composition, or an explicit static factory registration. | Public library API, incomplete crate/target membership, unresolved macro-generated registration, or runtime plugin lookup is `unknown` unless closed-world evidence resolves it. |

## Report and fixture requirements

Reports should expose live, dead, and unknown declaration counts separately,
along with the affected symbols and evidence. `S` is the number of live plus
unknown declarations; only confirmed dead declarations are removed. Any
unknown liveness result makes the ratio provisional. Keep existing decision
candidate accounting intact: branches inside every recognized Specification
body, including a dead one, remain outside `U`.

The current Python implementation recognizes named classes, `from` imports,
aliased and unaliased module imports, and static `from`-import re-export chains
within the measured source set. It counts constructor calls, a bounded list of
Specification consumers, runtime class checks and patterns, static registry
values, and explicit registration calls. Public names,
shadowed or conflicting bindings, unresolved same-name imports, wildcard
imports, dynamic lookups, parse/scope-incomplete scans, and declarations outside
an explicit closed-world manifest remain `unknown`. Assignment-based exports
and dynamic `__getattr__` re-exports are not resolved; a module-level
`__getattr__` hook or computed `__all__` keeps potentially affected
declarations `unknown`. Cyclic re-export resolution is also `unknown`.
Language-specific Swift/Rust resolution is not implemented. These cases must
not be inferred `dead`.

The versioned acceptance corpus is under
[`tests/fixtures/liveness/v1`](../tests/fixtures/liveness/v1). Its
`cases.json` records the expected status and source files for Python, Swift,
and Rust examples of cross-file use, module aliases, import-based re-exports,
runtime class checks and patterns, static type registries, dynamic exports,
cyclic re-exports, unreferenced private declarations, exported/public
declarations, unresolved dynamic lookup, and explicit runtime registration.
Python cases are exercised by the current test suite. Swift and
Rust fixture expectations describe the target contract; the current scanner
reports those declarations as `unknown` until their analyzers are implemented.
The bounded real-package audit and its limits are recorded in
[`python-liveness-real-package-audit.md`](python-liveness-real-package-audit.md).
