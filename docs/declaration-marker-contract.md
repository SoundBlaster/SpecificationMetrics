# Declaration marker contract

**Status:** proposed contract, not implemented by the scanner.
**Contract version:** `specification-marker/v1`.

## Purpose

The marker is an explicit source-level declaration by the owner of a measured
codebase: “count this named type as one of my Specification declarations.” It
lets a project opt in when its Specification type does not inherit from a base
class or implement a trait/protocol recognized by the scanner.

The marker does not create a Specification, infer intent from a type name, or
claim that every requirement/validator in a framework is a Specification. It
does not change program behavior. A marked declaration is still subject to the
same source ownership, liveness, and uncertainty rules as any other recognized
declaration.

## Source spelling and attachment

Version 1 uses a standalone comment immediately attached to a named type
declaration:

```python
# specmetrics: specification/v1
class ResponseSpec(MelleaRequirement):
    ...
```

```swift
// specmetrics: specification/v1
struct ResponseSpec: SomeRequirementProtocol {
    ...
}
```

```rust
// specmetrics: specification/v1
struct ResponseSpec {
    ...
}
```

The marker applies to the next named type declaration in the same source file
when only whitespace, comments, and that declaration's language attributes or
decorators intervene. Any other declaration or executable statement breaks the
attachment. The scanner must associate the marker through syntax/token
structure, not by guessing from a nearby type name.

The marker is a comment, so it introduces no runtime dependency, decorator
execution, generated code, or serialized metadata. The spelling is exact and
case-sensitive. A marker with an unsupported version, a dangling marker, or a
marker attached to an unsupported syntax node is reported as a marker issue; it
must not silently mark another declaration. An unresolved marker in an
`application` file makes the measurement provisional because an intended
declaration may be missing from `S`.

## Eligible declarations

Version 1 applies to named, project-owned declarations only:

| Language | Eligible declaration |
| --- | --- |
| Python | `class` declaration |
| Swift | Named `class`, `struct`, `enum`, or `actor` declaration |
| Rust | Named `struct` or `enum` declaration |

Protocols, traits, type aliases, extensions, anonymous expressions, and
factory-call sites are outside this marker contract. Existing native
Specification recognizers and factory-site rules continue to work independently.
If a declaration is both natively recognized and marked, it is still one
declaration and contributes at most one to `S`.

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
the metric. Markers in test, framework, generated, vendored, or excluded paths
do not add to `S` or remove decisions from `U`.

Consequently, importing `mellea.Requirement` and placing a marker beside the
import does not turn that external declaration into an application-owned
Specification. A project can mark its own named wrapper/subclass when that type
is the reusable Specification boundary it intends to measure. If it uses an
external type directly and has no local declaration, version 1 counts no local
Specification for it. A future manifest that maps imported external symbols to
local metric declarations would be a separate adapter contract; it is not
implied by this marker.

The author who adds a marker owns the semantic assertion. The tool reports the
marker and resolved declaration as evidence but does not validate whether the
type is cohesive, reused well, or architecturally a good Specification. Those
questions are outside this metric.

## Diagnostics and deterministic behavior

- One valid marker attaches to at most one declaration.
- Duplicate markers for one declaration produce a diagnostic; they do not
  multiply `S`.
- Unsupported, malformed, or dangling markers produce a diagnostic and do not
  mark a declaration. In an `application` file, that diagnostic makes the
  measurement provisional.
- A marker in a file without an assigned source role cannot affect `S` or `U`;
  normal scope rules still determine whether the complete report is provisional.
- Marker recognition is deterministic and requires no model inference.
- Reports identify the marker version, source path, qualified symbol when
  resolvable, marker location, and liveness evidence. They do not treat a
  comment as proof of liveness.

Enabling marker recognition changes the counting semantics. Its implementation
must increment the counting-rule version; historical snapshots retain the rule
version under which they were produced and are not recalculated in place.

## Acceptance fixtures required before implementation

The implementation should add versioned fixtures covering at least:

1. a marked local type without a recognized base/trait/protocol is discovered;
2. native recognition plus a marker counts the declaration once;
3. a live marked type resolves a runtime use across files and aliases where
   that language analyzer supports them;
4. a private unused marked type is dead only with complete closed-world
   evidence, while a public or unresolved type remains unknown;
5. decisions inside a marked type are removed from `U`, while an adjacent
   decision remains in `U`;
6. marker comments in test/framework/generated/excluded paths do not affect the
   application metric;
7. dangling, duplicated, unsupported-version, and unsupported-node markers
   yield deterministic diagnostics;
8. marking an import without a local type declaration does not count the
   imported external type.

Python, Swift, and Rust fixtures must be added as each language's marker parser
and liveness analyzer become available. Until then, the contract does not imply
that the current scanner recognizes markers in any language.
