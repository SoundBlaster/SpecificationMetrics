# Counting contract

The live ratio `S / U` measures one **owned production source set** at one
source revision. A repository root is a discovery boundary, not automatically
the measurement boundary. A whole-repository walk must assign every supported
source file exactly one role before its findings affect the ratio:

| Role | Examples | Contributes to `S` or `U`? |
| --- | --- | --- |
| `application` | Owned production code being improved | Yes |
| `framework` | SpecificationCore or other library implementation | No |
| `test` | Tests, fixtures, benchmarks, examples | No |
| `generated` | Generated, vendored, or build output | No |
| `excluded` | Reviewed file or directory outside the current scope, with a reason | No |

Roles come from an explicit, versioned source-scope manifest, with
repository-relative paths. The most specific matching path supplies the role;
conflicting roles at the same path or a file with no role make a
whole-repository measurement provisional. Path names such as `spec` or
`test` are not enough to infer ownership. A library can be measured as its own
project by assigning its production files the `application` role in a separate
measurement scope.

The `excluded` role accepts exact file paths and directory prefixes and
requires a non-empty reason. It excludes all Specification definitions and
decision candidates in those files, so it affects both `S` and `U`. A reviewed
candidate exclusion in the registry affects only that candidate in `U`.

Within `application` files, count each recognized Specification declaration or
factory source site once in `S`. Runtime instances and repeated uses do not
increase `S`. Classify each decision candidate exactly once, in this order:

1. `inside_specification`: its syntax node lies within a recognized
   Specification declaration or factory expression. Exclude it from `U`.
2. `uses_specification`: a resolved Specification value determines the
   candidate's branch. Exclude it from `U` only with reliable symbol/type
   evidence; a matching method name alone does not suffice.
3. `reviewed_exclusion`: a matching current-source fingerprint has a reviewed
   exclusion and reason. Exclude it from `U`.
4. `remaining`: count it in `U`.

The exact syntax subtree matters: an unrelated `if` elsewhere in the same file
remains in `U`. Nested recognized Specification definitions each contribute one
to `S`, while their decision candidates are excluded once. An unresolved use
remains in `U` and is flagged for review; it is never silently excluded.

Consequently, for the selected application source set:

```text
all_candidates = inside_specification + uses_specification
               + reviewed_exclusion + remaining
S = distinct Specification definitions and factory sites
U = remaining
```

For example, a project-owned `PricingSpec` containing two `if` statements
adds `1` to `S` and `0` to `U`; an unrelated `if` beside it adds `1` to `U`.
The source of a vendored SpecificationCore package adds nothing to either
count, even when the scanner walks through that directory.

The report and stored snapshot retain the source-scope manifest digest and
counting-rule version. The complete four-way candidate partition remains
future work because resolved `uses_specification` is not yet implemented.

The separate [application-site diagnostic](application-sites-contract.md) records
direct/mixed/unresolved Python-if evidence as preparation for that work. It does
not activate `uses_specification`, remove candidates from U, or change the counting rule.
Comparing ratios across different scopes or rule versions requires an explicit
annotation; old snapshots are not rewritten when the contract changes.

## Current implementation boundary

Counting rule v10 implements versioned source roles, semantic manifest digests,
the exact-subtree `inside_specification` exclusion for directly recognized
definitions, factories, the Python type marker, the Swift
`SpecificationMetricV1` protocol marker, and the Rust
`SpecificationMetricV1` trait marker, plus reviewed exclusions. Python and
Rust named declarations receive conservative `live`, `dead`, or `unknown`
liveness statuses; Swift remains `unknown`.
`--include` can still select owned production files or directories. An
unrestricted directory-root measurement without a manifest is provisional
discovery. The `provisional` flag also covers parse/marker errors, unassigned
files, and conflicting roles.

Python discovery now also follows static module-level class inheritance from
an already recognized native or marker declaration. It resolves multi-level
chains, generic bases, relative imports, symbol/module aliases and static
`from`-import re-exports within the measured source set. Each resolved subclass
counts once and its exact class subtree is excluded from `U`. A base-class
reference is a runtime use when its binding resolves unambiguously.

Discovery uses a fixed point, so file order does not change the result and
unseeded inheritance cycles do not invent Specifications. Rebound/conflicting
names, conditional or function-local imports, dynamic base expressions and
nested class qualification are not promoted to definite module-level ancestry.
Their branch candidates remain in `U` unless another explicit recognition rule
applies. This is syntactic source analysis, not execution or proof that an
import cycle can initialize at runtime.

The v8 -> v9 change corrects the previously missing transitive discovery and
inheritance use. It can increase `S`, decrease `U` and resolve `unknown` without
any application change. Treat that as an analyzer correction and start a new
comparison contract; do not rewrite v8 history or report it as a refactoring gain.


## Python typed predicate factories in v10

For a call such as `RULE = PredicateSpec[ContextFacts](predicate)`, the scanner
resolves the constructor expression before the subscript through the selected
Python modules. A resolved `specification_core.PredicateSpec` contributes one
factory site to S. Direct imports, import aliases and module-qualified imports
are supported. An unrelated constructor, ambiguous binding or lexically
shadowed name provides no evidence for this rule. The argument `ContextFacts`
is type metadata. Only the invoked factory counts. Candidates in the factory
call subtree receive the existing inside-specification treatment. Factory
liveness uses the existing source-presence convention.

On [SpecGraph 4add3afe](https://github.com/0al-spec/SpecGraph/tree/4add3afee736b9a97a0b6750c435e985959254cd),
with its application scope manifest and zero reviewed exclusions, the v9 and
v10 measurements share source digest
`bfa650679971f2b64f18f6416dbe9fe6a91a994e19287670b3d81c9f535d8c68` and
manifest digest `f7fe04b2f442ae87b91efc8257f297c0cda10a520796a8ec72dfd66f6cd8d73e`.

| Rule | S | U | S/U | Candidates inside recognized Specifications |
| --- | ---: | ---: | ---: | ---: |
| v9 | 127 | 10676 | 0.01189584 | 24 |
| v10 | 130 | 10676 | 0.01217685 | 24 |

The added sites are `INVALID_SPEC`, `UNAVAILABLE_SPEC` and
`REPORT_INPUTS_COMPATIBLE_SPEC`. This difference measures the change in analyzer
coverage on identical application bytes. Use v10 on both revisions for future
project comparisons.
