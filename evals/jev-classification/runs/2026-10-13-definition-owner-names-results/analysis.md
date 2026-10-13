# Definition and owner-name diagnostic — completed

## Scope and authority

On 2026-10-13, sixteen fresh subagent contexts annotated four distinct Python
expressions each: **64 judgments**, four repetitions per target/cell. The
[preparation](../2026-10-13-definition-owner-names-preparation/README.md), rubric,
prompt, source excerpts and prospective criteria were frozen before dispatch.
Each context saw one evidence view of each target, with four different cells.
No Jev/Luna provider API calls, human gold, production metric writes or rubric
changes occurred. Model and effort were inherited without explicit overrides;
the runtime model identity was not independently verified.

These are independent model annotations, **not an approved scoring reference**.
The integrator has prior hypotheses and performed the separate rationale review.
No raw answer was repaired or relabelled; no attempt required replacement.

## Raw distributions

Each entry gives `opportunity / concern_kind`, repeated **4/4** times.

| Exact target | 01: base/original | 02: extended/original | 03: base/neutral | 04: extended/neutral |
|---|---|---|---|---|
| `not step.valid` | excluded / policy | excluded / policy | excluded / policy | excluded / policy |
| `gate != "none"` | eligible / policy | eligible / policy | eligible / policy | eligible / policy |
| manifest path predicate | needs_review / unknown | needs_review / unknown | needs_review / unknown | needs_review / unknown |
| `not rendered.endswith("\n")` | excluded / mechanics | excluded / mechanics | excluded / mechanics | excluded / mechanics |

For each target, the label pair is identical across all sixteen judgments.
Within each target/cell all four repetitions match. There is no observed
condition-associated label difference in this sample. Repeated judgments are
not sixteen independent source targets.

Both axes have decisive coverage **48/64 (75%)**. Per target and per cell,
coverage is 4/4 for probes a, b and d, and 0/4 for probe c. Abstention is
unknown, not an exclusion or a wrong answer. This study contains no
`variant_behavior` judgment and cannot evaluate that category's quality.

Full counts and per-axis distributions: [validation-summary.json](validation-summary.json).

## Prospective criteria

| Criterion | Observation | Outcome within this diagnostic |
|---|---|---|
| H_ownership | Focal opportunity excluded in 16/16 | Met |
| H_names | Focal concern histograms match 01↔03 and 02↔04: policy 4 vs 4 | Met |
| H_definition | Eight extended-context focal responses assert neither unavailable nonblank semantics nor mutation of stored text | Met; integrator review |
| H_local_control | Newline control excluded/mechanics in 16/16 | Met; authored development expectation |

No prospective criterion failed. H_definition is a narrow interpretation check,
not a requirement that every rationale explicitly discuss nonmutation. Some
responses do not restate the full definition; none makes the prohibited claims.
[semantic-review.json](semantic-review.json) lists all eight reviewed raw outputs
and their hashes. Choice labels alone cannot establish this result.

## Interpretation and disagreements

**Existing ownership is consistently recognized.** Focal explanations follow
the selected predicate through `findings`, the `Specification` base evaluation,
and its evaluation loop. The same path remains visible in every cell. Exclusion
therefore means the decision already has a Specification, not that it lacks a
policy responsibility or is unsuitable for the pattern.

**Definitions improve explanation specificity without changing labels.** The
eight base-context responses explicitly note missing `step.valid` internals.
Extended-context responses describe present, nonblank text; they no longer claim
the operational criterion is unavailable. For example, annotator-07 writes:
“TextInput.valid distinguishes present, nonblank text from missing or blank
values.” This is consistent with the supplied definition and boundary conversion.
The `strip()` predicate tests content; stored source text is unchanged.

**Focal semantic correctness remains unsettled.** All sixteen choose policy,
including eight without the definition. Their rationales infer scenario-value
admissibility from the finding/evaluation role. That is a plausible reading,
but an evaluation path establishes ownership more directly than domain purpose.
Neither a nonblank predicate nor a rule address independently resolves an adopted
Requirement. There is no independent gold proving that this rule must be policy
rather than generic input validation. The earlier integrator recommendation
`excluded / unknown` was advisory and concerned a different task/view; its raw
evidence and the historical H2 failure remain unchanged. Unanimity here does
not invalidate that caution or prove the model has resolved the semantic issue.

**The other targets show selective rather than blanket abstention.** Gate
priority explanations distinguish whether gate obligations take precedence
from later dispatch to an individual gate action. Newline explanations cite the
local append as serialization mechanics. All sixteen manifest-path responses
identify missing contract evidence that could distinguish permitted domain
references from generic path representation constraints. They do not establish
that such a contract is absent from the repository.

## Reproducibility and limits

- [execution-receipt.json](execution-receipt.json) binds all frozen preparation
  files, each assigned input, the fully formatted dispatch prompt, agent task,
  isolated directory and raw output. Raw files are `independent-annotations-01.json`
  through `independent-annotations-16.json`.
- Isolation is fresh context plus scoped input assignment and agent self-report,
  not an enforced filesystem sandbox. All sixteen report only their two inputs.
  Distinct helper families prevent direct withheld-definition leakage; residual
  cross-case priming and common model biases remain possible.
- Neutralization changes selected owner NAME tokens only. Domain fields, type
  names, rule addresses, strings and the `Specification` marker remain visible.
  Matching histograms do not prove general name invariance or statistical
  equivalence. Four hand-selected families do not represent the codebase.
- Context additions differ by target. Do not pool them as one treatment effect.
  Inputs and prompt differ from prior runs; this is not an unchanged-input repeat.
- Exact quotes validate provenance; semantic support is reviewed separately.

From `evals/jev-classification`, with Python >=3.10:

```sh
python3 -m unittest -v test_validate_definition_owner_annotations.py test_prepare_definition_owner_names.py
python3 validate_definition_owner_annotations.py
```

Local verification used the repository Python 3.10 virtual environment:
16 tests passed. CI now replays this result offline; no runtime credentials or
temporary annotation directories are required to replay saved evidence.

## Next bounded experiment

Recover the actual permitted-reference contract for the manifest-path predicate
from SpecGraph specifications and callers. If available, prepare a new blinded
contract-context diagnostic, preserving this run and its unknown labels. If
absent, record the missing contract explicitly. Do not tune a prompt to force a
decisive answer or promote current consensus to scoring gold.
