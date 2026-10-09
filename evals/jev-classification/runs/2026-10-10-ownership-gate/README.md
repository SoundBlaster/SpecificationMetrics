# Source-bound construction gate and recorded semantic replay

## Question and scope

Can a deterministic source check prevent the aligned Jev rubric from proposing
an existing Specification construction as a new refactoring opportunity?

This is an **offline composition diagnostic**, using the unchanged responses and
model annotations from the [matched-rubric run](../2026-10-10-rubric-alignment/README.md).
It makes zero new inference requests. It does not change production classifier
prompts, reviewed labels, registry entries or S/U. These are eight development
examples, not a held-out sample or human gold.

## Implemented rule

1. Read the full source file from its pinned SpecGraph Git revision.
2. Check its SHA-256, exact selected text, excerpt SHA-256 and line range.
3. Require the whole selected site to be a module-level assignment to the
   selected symbol, whose value directly constructs a recognized library object.
4. Resolve absolute `from specification_core import ...` bindings, including
   aliases and `FirstMatch.with_fallback`. Invalidate shadowed/deleted names,
   imported alternatives, attribute mutation and visible dynamic namespace use.
5. A positive routes opportunity to `excluded` **before** invoking the semantic
   callback. Any other supported result is `unknown` and keeps the semantic
   route. Missing construction is not proof of missing ownership elsewhere.

The gate recognizes direct construction, not arbitrary types, module aliases,
re-exports, delegated factories, whole-project ownership or runtime identity.
It assumes ordinary static Python bindings and the imported library contract;
arbitrary Python execution can defeat static binding assumptions. It cannot infer
`concern_kind`: those answers remain the original recorded Jev answers.

## Results

Both repeats produced the same result. Counts below are per repeat.

| Measurement | Raw baseline | Baseline + gate | Raw aligned | Aligned + gate |
|---|---:|---:|---:|---:|
| Opportunity agreement with model reference | 4/8 | 5/8 | 5/8 | 7/8 |
| Eligible recall | 0/3 | 0/3 | 2/3 | 2/3 |
| Already-constructed controls proposed eligible | 1/2 | 0/2 | 2/2 | 0/2 |
| Mechanics controls proposed eligible | 0/3 | 0/3 | 0/3 | 0/3 |

Positive evidence came from source, not case IDs or reference labels:

- `sg-018`: `_PRE_SIB_STATE_DECISION`, resolved `specification_core.FirstMatch`.
- `sg-020`: `_ACCEPTANCE_CRITERION_DECISION`, resolved
  `specification_core.FirstMatch.with_fallback`.

The other six sites remain `unknown` for construction and retain their recorded
semantic answers. In particular, sg-019 remains a false exclusion relative to
the model reference; its mixed-function target remains unresolved. The old raw
aligned experiment still failed its original success criterion. Adding this gate
does not retroactively make that prompt experiment pass.

The 7/8 figure measures a new composition against already-seen annotations.
It is not a fresh live model score, a RustDecision integration test or an estimate
of production quality. A future provider pipeline could avoid requests for the
two positives; this replay itself saved no historically consumed tokens.

## Actual Rust scanner audit

The runner also invoked the built Rust CLI on each complete historical source
file, isolated in its own temporary root. [report.json](report.json) retains the
selected-range candidates, factory definitions and parse issues, with source and
implementation hashes. All eight scans had no parse issues.

| Site | Control-flow candidates in selected range | Factory definitions |
|---|---:|---|
| sg-017 | 1 | none |
| sg-019 | 3 | none |
| sg-018 | 0 | FirstMatch + three PredicateSpec |
| sg-033 | 0 | none |
| sg-031 | 1 | none |
| sg-032 | 1 | none |
| sg-020 | 0 | two PredicateSpec; outer with_fallback absent |
| sg-034 | 0 | none |

Production `src/classify.rs` already filters `inside_specification` candidates
after a fresh scan. The historical native API experiment bypassed that pipeline.
However, **neither owned declaration generated a control-flow candidate here**:
there is no evidence that the production filter actually skipped either of
these whole declarations. The evaluation units and scanner units differ.
For the same reason, the table's zero for sg-033 does not mean no policy exists:
its selected conjunction is not one of the scanner's control-flow candidates.

Rust factory detection is currently syntactic by name, without import identity
resolution. It does not recognize the outer Python `FirstMatch.with_fallback`
factory. The bounded Python construction check must not be described as the
production Rust ownership guarantee. Both limitations deserve a separate Rust
discovery/identity contract, not a silent metric rewrite in this evaluation PR.

## Reproduce and validate

From the repository root, build the current scanner with `cargo build --locked`.
From `evals/jev-classification`, with a SpecGraph clone containing the pinned
commits and a **new, nonexistent output path**:

```bash
python3 ownership_gate.py \
  --source-repo /path/to/SpecGraph \
  --scanner ../../target/debug/specification-metrics \
  --output /tmp/ownership-replay-new.json
python3 -m unittest -v test_ownership_gate.py
```

The binary digest is machine/build dependent; source revision, source digests,
input digests and selected evidence identify the recorded audit. The runner
does not fetch source or contact an inference endpoint. Unit tests exercise
source freshness, aliases, rebinding/deletion, wrong/relative imports, namespace
mutation, neighboring constructors, provider bypass and preservation of unknown
and raw predictions. CI runs these without a SpecGraph clone or API key; a full
source replay additionally needs the historical Git objects.

## Next slice

Define one target-decision unit shared by discovery and evaluation. Extend Rust
discovery/import resolution for that unit, then use new-family adjudicated
examples before measuring live classification. Keep the sg-019 predicate-target
context comparison separate so its effect is not confounded with this gate.
