# Formal analysis roadmap

Date: 2026-10-07. Status: proposed; the stages below are not implemented by
this document. First pilot: Python decisions in SpecGraph. Implementation
language: Rust; Swift and Rust source support follow the Python pilot.

## Goal and existing boundaries

Make SpecificationMetrics decisions explainable and reproducible: establish
structural facts, enforce a classification contract, prove selected predicate
equivalences, and use optional Jev inference for unresolved semantic questions.
Support SpecificationCore's consistent representation, reuse, observation and
management of decisions while measuring remaining opportunities and distinct
Specifications alongside other code metrics.

Build on the [counting contract](counting-contract.md),
[classification contract](candidate-classification-contract.md) and
[rule reuse contract](rule-reuse-contract.md). The current structural matcher
does not provide general semantic equivalence. This roadmap adds capabilities;
it does not redefine the existing S/U calculation or grant model suggestions
authority over reviewed registry entries. Any future counting change requires
a separate versioned counting-contract migration.

## Delivery sequence

| Stage | Deliverable | Completion criterion |
| --- | --- | --- |
| 1. Decision contract | Definitions and an executable decision table | Every valid fact state has one outcome; contradictions abstain |
| 2. Structural evidence | Symbol resolution and exact decision bindings | Existing Specifications are recognized without hiding adjacent policies |
| 3. Transformation checks | Metamorphic corpus and regression tests | Supported transformations satisfy their declared relations |
| 4. Predicate equivalence | Bounded SMT pilot | Supported comparisons yield a proof, counterexample or explicit unknown |
| 5. PR pilot | Evidence report and calibrated semantic review | Every blocking finding has reproducible, reviewed grounds |

Deliver each stage as a focused PR. Later stages depend on the reviewed
contract and evidence format; no calendar estimate is implied.

## Stage 1: Decision contract

Analyze a specific decision: a condition, predicate or rule composition with an
AST location. Functions and files provide context rather than blanket exclusion.

Define independent dimensions in a proposed versioned evidence contract:

- `concern_kind`: `policy`, `mechanics`, `variant_behavior`, `unknown`.
- `representation`: `inline`, `specification`, `unresolved`.
- `disposition`: `eligible`, `excluded`, `needs_review`.

Preserve the current provider contract's `opportunity` field. Decide whether
`disposition` becomes an internal assessment or a versioned output field before
changing any schema; do not silently rename existing fields.

Define `implemented_by`, `invokes` and `duplicates` relations. Invoking a
Specification does not establish that all surrounding decisions are implemented
by it. A confirmed existing Specification decision can be `policy` and excluded
from *new* opportunities. Unresolved required evidence or contradictory facts
produce `needs_review`.

Validate completeness and consistency by exhaustive enumeration of the finite
fact states. Add SMT constraints when enumeration becomes impractical.

Acceptance cases: the named pre-SIB and acceptance-criterion FirstMatch decisions
from the evaluation corpus (`sg-018`, `sg-020`), plus a mixed function invoking
a Specification while containing an independent inline policy. Pin source
revisions and obtain reviewed expected labels; historical extraction and model
annotations alone are not a gold reference.

## Stage 2: Structural evidence

Extend the Rust analyzer with bounded symbol resolution for imports, aliases,
re-exports, recognized Specification declarations, FirstMatch compositions,
registered predicates and decision calls. Inspect existing liveness and reuse
resolvers before introducing another resolver; their supported scopes differ.

Express inference rules declaratively. Start with a small Rust rule evaluator;
adopt a Datalog runtime only if the pilot demonstrates a concrete need.

Each finding records the rule ID/version, source revision, analyzer version,
resolved symbols, relation chain and exact source spans. Locations are relative
to a captured revision. Cross-revision identity reconciliation is a separate
operation, not a promised property of an AST location.

Acceptance: recognize the two existing FirstMatch decisions; retain the mixed
function's independent inline policy; report dynamic imports, shadowing and
ambiguous resolution as explicit uncertainty where they prevent a conclusion.
No whole-function exemption follows from one recognized call.

## Stage 3: Metamorphic testing

Generate variants with declared preconditions and expected relations:

| Transformation | Expected relation |
| --- | --- |
| Formatting changes | Assessment is invariant |
| Resolvable import alias | Specification recognition is invariant |
| Reordering supported pure Boolean operands | Predicate meaning is invariant |
| Extracting a policy into a recognized Specification | Concern remains policy; its inline opportunity disappears |
| Copying its predicate into a caller | A procedural duplicate becomes detectable |
| Adding an independent policy next to a call | A separate candidate appears |

Use deterministic regression/property tests for the analyzer. Use repeated
model runs to measure violation rates for Jev. Specify input assumptions for
every transformation: renaming or moving Python code can change reflection,
name resolution or behavior and is not automatically semantics preserving.

Acceptance: all supported deterministic transformations pass; model violations
are retained as reproducible cases with provider/input provenance. These tests
provide evidence about properties, not a general correctness proof.

## Stage 4: Bounded SMT equivalence

Pilot the registered SpecGraph workspace-allocation family. Encode a restricted
language of pure Boolean operations, enum values and explicitly supported
comparisons. Compare a procedural predicate P and Specification predicate S by
asking whether there exists an input x such that P(x) differs from S(x).

- `UNSAT`: equivalent within the encoded semantics and input domain.
- `SAT`: retain the differing input as a counterexample.
- `unknown`, timeout or unsupported syntax: no proof; require review.

Retain source-to-formula mappings, input-domain assumptions, encoder and solver
versions, query digest and result. Python truthiness, exceptions, short-circuit
evaluation and side effects require explicit modeling or rejection. An
unsatisfiable input domain must be diagnosed rather than used to claim useful
equivalence. A Boolean proof alone does not establish identical handler effects,
warnings, traces or runtime behavior.

Acceptance: equivalent supported variants are proved; removing a necessary
condition produces a counterexample; unsupported expressions never become
proved duplicates. Existing exact matching keeps its current behavior until a
separate reviewed gate extension is approved.

## Stage 5: Semantic review and PR pilot

Give Jev bounded source context, the architecture intent profile and checked
structural facts. Check its suggested output against the decision contract.
Preserve provider limitations: the current Choice adapter supplies labels and
scores, not a semantic explanation; do not fabricate a rationale.

Evaluate against independently reviewed labels, separating related families
between prompt development and evaluation. Choose any confidence threshold on
a held-out calibration set; a diagnostic threshold such as 0.50 is not evidence
of calibrated error risk. Avoid assuming higher reasoning effort improves
accuracy without evaluation.

The PR report exposes S/U changes, confirmed procedural duplicates, unresolved
sites, semantic suggestions and provenance. Start new analyses in informational
mode. Introduce enforcement only for approved rules and verified findings within
declared supported scope. Follow the existing trusted-base catalog boundary;
head changes must not disable their own gate.

Acceptance: reports reproduce on pinned commits; false exclusions, false
duplicate findings, abstention, eligible recall/precision and reviewer workload
are measured separately. Model suggestions remain distinct from authoritative
registry dispositions and S/U snapshots. Incomplete analysis is visible and
cannot be presented as zero violations.

## Success measures and first task

Track structural recognition accuracy and supported scope, missed independent
inline policies, metamorphic violation rates, equivalence proof coverage,
counterexamples, unknowns and analysis runtime. Report semantic quality on its
own axes. Do not collapse these observations into a combined quality score.

First task: write the versioned decision contract and exhaustive decision table
for the two recognized FirstMatch cases and the mixed-function control. Review
that contract before implementing exclusion or gate changes.

## Method references

- [Soufflé: program analysis expressed in Datalog](https://souffle-lang.github.io/pdf/cav16.pdf).
- [Programming Z3: SMT modeling and solving](https://z3prover.github.io/papers/programmingz3.html).
- [Hypothesis: property-based testing](https://hypothesis.readthedocs.io/en/latest/).
