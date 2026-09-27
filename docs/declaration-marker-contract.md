# Declaration marker contract

**Status:** Python, Swift, and Rust forms implemented by counting rule v7.
**Contract version:** `specification-marker/v1`.

## Purpose

The marker is an explicit, type-system-visible declaration by the owner of a
measured codebase: “count this named type as one of my Specification
declarations.” It lets a project opt in when its Specification type does not
inherit from a base class or implement a trait/protocol already recognized by
the scanner.

The marker does not create a Specification, infer intent from a type name, or
claim that every requirement/validator in a framework is a Specification. It
does not add Specification behavior. Its language-native form does have a
small type-system/runtime footprint: Python exposes a class attribute, Swift
adds conformance metadata, and Rust adds a trait implementation that can
participate in trait resolution. Projects must accept that explicit opt-in
cost. A marked declaration remains subject to the same source ownership,
liveness, and uncertainty rules as any other recognized declaration.

## Language-specific marker forms

The semantic contract is shared, while each language uses syntax its parser and
compiler/type checker can see. Version 1 reserves these marker names and forms.
All three language forms are implemented with conservative source-resolution
boundaries.

### Python

Declare a typed class variable directly in the class body:

```python
from typing import ClassVar, Literal

class ResponseSpec(MelleaRequirement):
    __specmetrics_specification__: ClassVar[Literal["specification/v1"]] = (
        "specification/v1"
    )
    ...
```

The scanner recognizes only this exact class-level field name and literal
version. It accepts the shown short `ClassVar`/`Literal` names or both names
qualified by `typing.`; type import aliases are not recognized. A type
checker can validate the literal's type; the field is also
visible in the Python AST. It must not be an instance field or serialized
framework data field. The CI fixture verifies that dataclasses and Pydantic v2
exclude the `ClassVar` marker from fields and serialized dictionaries.
Reflection can still observe the class attribute. Other model frameworks need
their own compatibility tests before being documented as supported.

### Swift

Declare an empty marker protocol in the application module and conform the
project-owned type to it:

```swift
protocol SpecificationMetricV1 {}

struct ResponseSpec: SomeRequirementProtocol, SpecificationMetricV1 {
    ...
}
```

An extension conformance is also accepted as the marker location when the
nominal type is declared in the same source file; the extension itself is not
counted as a Specification. The scanner recognizes only the exact unqualified
protocol name `SpecificationMetricV1`. Swift checks that the conformance is
valid. The protocol has no requirements and adds no callable behavior, but its
conformance metadata can affect generic constraints and runtime conformance
checks. Cross-file nominal-type resolution is not implemented yet, so a marker
extension in another file is not recognized by v5.

### Rust

Declare an empty marker trait in the application crate and implement it for the
project-owned type:

```rust
trait SpecificationMetricV1 {}

struct ResponseSpec {
    ...
}

impl SpecificationMetricV1 for ResponseSpec {}
```

The compiler verifies the trait implementation. The empty trait adds no
runtime data or methods, though the implementation can participate in trait
resolution. Counting rule v7 resolves marker traits and target structs/enums
across conventional Rust crate module trees rooted at `lib.rs`, `main.rs`, or
an auto-discovered binary/example/test/benchmark target.
It accepts `crate::`, `self::`, `super::`, and direct module paths when those
paths resolve to declarations in the same measured crate. A standalone Rust
file without a recognized crate root is treated as its own crate. Custom
`#[path]` mappings, macro-generated modules, `use` aliases, and unresolved or
excluded module files are not resolved or counted; visible marker-shaped
implementations that fail resolution produce a diagnostic. The scanner does
not guess their ownership. Marker implementations are counted once at the
nominal type, and
inherent `impl` blocks for that type are included when excluding its internal
decision sites from `U`.

These forms are intentionally language-specific. The versioned meaning is
`specification/v1`; the scanner recognizes the syntax without requiring a
runtime SpecificationMetrics library. Marker protocols/traits are ordinary
source declarations owned by the application and introduce no package
dependency. Their own definitions are marker infrastructure, not Specification
declarations and do not contribute to `S`.

## Eligible declarations

Version 1 applies to named, project-owned declarations only:

| Language | Eligible declaration |
| --- | --- |
| Python | `class` with the exact typed class variable described above |
| Swift | Project-owned named type conforming to `SpecificationMetricV1` |
| Rust | Project-owned named `struct` or `enum` implementing the local `SpecificationMetricV1` trait |

Protocols, traits as Specification declarations, type aliases, anonymous
expressions, and factory-call sites are outside this marker contract. A Swift
extension may carry the conformance marker for a project-owned nominal type,
but the nominal type remains the declaration being counted. Existing native
Specification recognizers and factory-site rules continue to work
independently. If a declaration is both natively recognized and marked, it is
still one declaration and contributes at most one to `S`.

## What the marker includes in the metric

A valid marker promotes the attached declaration into the scanner's recognized
Specification declaration set, even when it has no recognized base class,
protocol, or trait implementation. It does not mark neighboring declarations,
the containing file, or all instances of the type.

The declaration contributes once to `S`, subject to liveness:

- `live`: count it in `S` when the language analyzer resolves at least one
  runtime use under the existing liveness contract;
- `dead`: omit it from `S` only when the existing closed-world and visibility
  rules prove it dead;
- `unknown`: retain it in `S` and make the report provisional when uses,
  visibility, reflection, imports, or source completeness cannot be resolved.

The marked declaration's syntax subtree is treated like any other recognized
Specification subtree. Decision candidates inside it do not contribute to `U`.
A decision outside the marked declaration remains a candidate unless a separate
implemented rule classifies it otherwise. The marker itself is not runtime-use
evidence and does not prove that a declaration is live.

Liveness uses the existing language-specific evidence and symbol resolution:
resolved construction, passing a type/value to a recognized evaluator or
combinator, supported runtime type checks, and explicit runtime registration.
Type-only references, comments, strings, and the marker are not runtime uses.
Aliases and re-exports count only when the relevant language analyzer resolves
them. An unresolved dynamic lookup remains `unknown`, never `dead`.

## Ownership and third-party frameworks

Only declarations in the measurement's `application` source role contribute to
the metric. The marker field, protocol conformance, or trait implementation
must also be present in the measured `application` source set. Marker forms in
test, framework, generated, vendored, or excluded paths do not add to `S` or
remove decisions from `U`. For Rust, the scanner resolves marker traits,
target types, and associated inherent `impl` blocks across recognized
crate/module paths in the measured source set. Files that cannot be mapped into
a crate remain unresolved.

Consequently, importing `mellea.Requirement` and putting a similarly named
field on the import does not turn that external declaration into an
application-owned Specification. A project can mark its own named
wrapper/subclass when that type is the reusable Specification boundary it
intends to measure. If it uses an external type directly and has no local
declaration, version 1 counts no local Specification for it. Swift retroactive
conformance and Rust implementations of a local marker trait for foreign types
are outside this contract; use a project-owned wrapper instead. A future
manifest that maps imported external symbols to local metric declarations
would be a separate adapter contract; it is not implied by this marker.

The wrapper is an application design choice, not a required metrics shim. Use
one only when the project wants a local type boundary for the external
requirement. The marker alone adds no requirement/composition behavior.

Version 1 does not use macros. Python decorators execute at import time, while
Swift/Rust macro expansion adds language-toolchain-specific build machinery and
can obscure the source declaration the analyzer needs to resolve. A future
macro may generate one of these same marker forms, but the scanner must still
validate the expanded language-level declaration and type identity.

The author who adds a marker owns the semantic assertion. The tool reports the
marker and resolved declaration as evidence but does not validate whether the
type is cohesive, reused well, or architecturally a good Specification. Those
questions are outside this metric.

## Diagnostics and deterministic behavior

- One marker conformance/field identifies at most one declaration.
- Multiple accepted marker forms for one declaration still produce one `S`
  entry.
- An invalid Python marker type/value, unresolved Swift conformance, unresolved
  Rust trait implementation, or unsupported marker version produces a
  diagnostic and does not mark a declaration. If this occurs in an
  `application` file, the measurement is provisional.
- A marker declaration or conformance in a file without an assigned source
  role cannot affect `S` or `U`; normal scope rules still determine whether
  the complete report is provisional.
- Marker recognition is deterministic and requires no model inference.
- Reports identify the marker version, source path, qualified symbol when
  resolvable, marker location, and liveness evidence. They do not treat a
  marker declaration as proof of liveness.

Enabling marker recognition changes the counting semantics. Python support
introduced counting rule v4, Swift support increments it to v5, Rust markers
increment it to v6, and Rust crate/module resolution increments it to v7.
Historical snapshots retain the rule version
under which they were produced and are not recalculated in place.

## Acceptance coverage

Versioned implementation fixtures should cover at least:

1. a marked local type without a previously recognized Specification
   base/trait/protocol is discovered in each supported language;
2. native recognition plus a marker counts the declaration once;
3. a live marked type resolves a runtime use across files and aliases where
   that language analyzer supports them;
4. a private unused marked type is dead only with complete closed-world
   evidence, while a public or unresolved type remains unknown;
5. decisions inside a marked type are removed from `U`, while an adjacent
   decision remains in `U`;
6. marker fields/conformances/implementations in
   test/framework/generated/excluded paths do not affect the application
   metric;
7. malformed or wrong-version Python markers and Swift/Rust conformances that
   do not resolve to the reserved interface yield deterministic diagnostics;
8. adding a marker to an import without a local type declaration does not
   count the imported external type.

The Rust scanner tests cover Python, Swift, and Rust marker discovery,
deduplication with native recognition, internal decision exclusion, and marker
diagnostics, including cross-file `crate::` paths, inline modules, `super::`,
native-conformance deduplication, and unknown custom `#[path]` ownership.
Python and Rust liveness tests remain conservative; Swift liveness remains
`unknown`. Runtime fixtures verify Python `ClassVar` behavior, and CI typechecks
the Rust marker fixture with `rustc`.
