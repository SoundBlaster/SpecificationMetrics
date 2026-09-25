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

Roles come from an explicit, versioned source-scope manifest, with
repository-relative paths. The most specific matching path supplies the role;
conflicting roles at the same path or a file with no role make a
whole-repository measurement provisional. Path names such as `spec` or
`test` are not enough to infer ownership. A library can be measured as its own
project by assigning its production files the `application` role in a separate
measurement scope.

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
Comparing ratios across different scopes or rule versions requires an explicit
annotation; old snapshots are not rewritten when the contract changes.

## Current implementation boundary

Counting rule v2 implements versioned source roles, semantic manifest digests,
the exact-subtree `inside_specification` exclusion for directly recognized
definitions and factories, and reviewed exclusions. It does **not** yet
implement resolved `uses_specification` classification. `--include` can still
select owned production files or directories. An unrestricted directory-root
measurement without a manifest is provisional discovery. The `provisional`
flag also covers parse errors, unassigned files, and conflicting roles.
