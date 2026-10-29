# Bounded alias reference model v1

An executable reference for the [proposed contract](../../docs/local-alias-flow-contract.md).
It uses Python's standard `ast` and `tokenize`, separately from the production
Rust/tree-sitter analyzer. **The production alias profile is not implemented.**
Raw S/U, existing CLI profiles and frozen evaluation labels are unchanged.

## Model and scope

`model.py` separates a finite name-state machine from Python syntax lowering.
One symbolic origin is tracked through `origin`, `other` and `deleted` states.
Copying, rebinding and deletion affect exactly the target name. The first
if, unsupported effect, bound or scope end terminates the derivation.
Applied events retain source anchors and touched before/after states;
rejected operations never become applied events. This is static evidence,
not an execution trace, safe-evaluation proof or body-equivalence result.

The parser checks direct function/loop-body scope, annotations, projections,
literal/copy shapes and control/effect barriers. Both standalone and trailing
inline sibling comments count toward the 64-node bound; Python AST discards
comments, so the adapter recovers them with `tokenize`. No inspected source
is imported, evaluated or executed.

The model accepts **supplied recognized-origin and verified-enum facts**.
It does not recognize a FirstMatch or enum by spelling/capitalization, and
does not independently re-prove the existing factory/import/enum resolver.
Unit fragments assume the contract's stated FirstMatch precondition. For
the source-backed run, the runner verifies frozen sources, mutation hashes,
license and prior recognized-call evidence; its tiny enum-fact verifier is
restricted to the two frozen SpecGraph enum classes. It is not a general
Python enum resolver or protection against runtime monkey-patching.

The reference is an independent implementation of transfer logic and syntax
lowering, not independent semantic annotation or a formal correctness proof.
The labels were authored before this model and remain unchanged.

## Results

The retained [assessment](assessment.json) records:

| Check | Result |
| --- | --- |
| Frozen unit matrix | 47 / 47 expected outcomes, including stop and reference state |
| Source-backed alias variants | 12 / 12; 6 linked and 6 not linked |
| Reused real source controls | 3 / 3 linked |

These are contract checks on selected development examples, not a population
accuracy estimate. The three controls are shared with previous datasets.
The existing production v1 still returns unresolved for all 12 alias variants.
Factory and enum preconditions are explicit in each source result and in the
assessment receipt, together with source/matrix/model/runner hashes.

Seventeen offline unittest methods pass. Besides the 47-case matrix, three
property tests enumerate **120 state/operation combinations** over the 12
two-name maps (`d` in three states; `a` absent or in three states):

- 48 copy combinations check RHS-before-LHS and noninterference.
- 48 literal-rebind/delete combinations check that other names are preserved.
- 24 guard combinations check the status partition.

This bounded enumeration does not cover all eight-name programs or prove
global totality. Further tests cover exact/overflow limits, rejected-event
evidence, projection checks, scope directives, unknown enum facts, parenthesized
copy/literal refusal and runner integrity. A changed/empty contract matrix
fails its frozen digest check rather than becoming a successful empty run.

### Root cause retained as a regression

An additional test exposed missing inline-comment accounting: the initial
adapter counted standalone comments only. With a two-node limit,
`a = d  # comment` followed by an if incorrectly linked instead of stopping
at the limit. The fix distinguishes AST statement byte spans from comment
tokens, including comments following the origin itself. The new regression
failed before the fix and passes now; the frozen 47-case expectations were
not changed to accommodate it.

## Reproduce

Run the same dependency-free checks as the dedicated CI job:

```sh
.venv/bin/python -B -W error -m unittest discover \
  -s evals/local-alias-reference-v1 -p 'test_*.py' -v
.venv/bin/python -B evals/local-alias-reference-v1/run.py
```

The default runner validates only the pinned unit matrix and prints a summary.
It needs no model provider, embeddings, Rust binary or other repository.
To repeat the source-backed phase, use a local clone with the frozen objects:

```sh
.venv/bin/python -B evals/local-alias-reference-v1/run.py \
  --repo /path/to/SpecGraph \
  --output /path/to/new/external-artifacts/alias-reference-run
```

The runner never fetches. Source verification completes before output creation;
output must be a new directory outside both source checkouts. Full local
assessment evidence was produced on TB5 and copied here after hash verification.
Ruff format/check, the existing counterfactual harness tests and diff checks
also pass. No Rust code changed or broad Rust suite was run locally.

Next: implement the separately named Rust opt-in profile and compare it with
this reference on the frozen matrix and source-backed cases. Keep implemented
v1 output and raw metric behavior unchanged.
# Comparing the Rust alias profile

After building the binary, compare the three frozen SpecGraph controls and
their twelve synthetic variants against the stored Python reference:

```sh
python -B evals/local-alias-reference-v1/compare_rust.py \
  --repo /path/to/SpecGraph --binary /path/to/specification-metrics \
  --temp-root /path/to/external/temporary-directory
```

The command verifies the frozen source provenance, uses isolated temporary
copies, and emits the binary digest and individual outcomes. It requires the
pinned Git revision to be present in the source checkout. This comparison does
not prove population accuracy or execute source programs.
