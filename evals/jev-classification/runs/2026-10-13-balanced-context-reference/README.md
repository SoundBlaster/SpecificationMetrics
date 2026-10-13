# Balanced real-source reference round

**Status: 18 independent annotations completed; same-input comparison reviewed;
four states / six axis labels remain disputed; provider scoring not frozen.**

This supersedes the [earlier delivery design](../2026-10-13-context-evidence-preparation/annotation-review.md),
without changing its inputs, producer, outputs or receipts. It addresses
[PR #41's review](https://github.com/SoundBlaster/SpecificationMetrics/pull/41#discussion_r4256695179):
one evidence mode per annotator perfectly correlated mode and annotator.

## Corrected delivery

The same six production expressions from SpecGraph commit
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b` appear in the same eighteen states,
with exactly the same architecture profile, rubric, code and state hashes.
Only packet membership changes. A cyclic rotation assigns each of three fresh
annotators **two expression-only, two declaration and two bundle cases**.
Each annotator still sees one view of each target, never two views of one target.

The fresh contexts inherited no conversation history. They received only scoped
copies of their packet and blank template with the same annotation instructions
as the earlier round, no earlier answers or source mapping. Model/effort were
inherited with no override; actual model identity was not independently verified.
Each self-reports reading only the two allowed files. Copies were byte-identical
before dispatch and after completion. This is scoped conversation isolation on a
shared filesystem, **not an enforced filesystem sandbox**.

Balance removes the perfect mode/annotator correlation. This is still a selected
six-family development diagnostic, with one independent judgment per state in
this round. It does not establish a causal context effect or statistical
generalization. Packet composition and annotators also differ between rounds.

## Balanced annotations

Cells contain `opportunity / concern_kind`; original raw JSON is preserved.

| Target | Expression only | Containing declaration | Evidence bundle |
|---|---|---|---|
| YAML newline | excluded / mechanics | excluded / mechanics | excluded / mechanics |
| Manifest path | needs_review / unknown | excluded / mechanics | eligible / policy |
| Criterion coverage | needs_review / unknown | eligible / policy | eligible / policy |
| Canonical mutation flag | needs_review / policy | eligible / policy | eligible / policy |
| Active gate | needs_review / unknown | eligible / policy | eligible / policy |
| BDD scenario steps | needs_review / unknown | eligible / policy | excluded / policy |

The BDD bundle directly shows the Specification inheritance, rule reference and
evaluation path. Its `excluded / policy` result illustrates two separate axes:
a rule can be policy and already represented as a Specification. A method-only
view does not establish that ownership. No annotation has changed S/U accounting.

## Same-input comparison with the diagnostic round

[same-input-comparison.json](same-input-comparison.json) matches each case by
its exact state hash, retains both answers and performs no voting or relabelling.

- Opportunity: **15/18** labels agree.
- Concern kind: **15/18** labels agree.
- Both labels agree for **14/18** states.
- Four states differ, containing six changed axis labels.

These are reference-annotation agreement counts, **not Jev/Luna accuracy**.
The repeated observations are eighteen states from six related code families.

| State | Earlier answer | Balanced answer | Integrator disposition |
|---|---|---|---|
| context-09: path declaration | eligible / policy | excluded / mechanics | Both axes unresolved |
| context-16: path bundle | excluded / mechanics | eligible / policy | Both axes unresolved |
| context-13: permission expression | eligible / policy | needs_review / policy | Opportunity unresolved |
| context-18: gate declaration | eligible / variant_behavior | eligible / policy | Concern kind unresolved |

### Manifest path: same-input instability is observed

The two nonminimal path states reverse their earlier answers despite unchanged
source evidence. One interpretation treats relative/canonical, nontraversing
manifest references as an artifact-integrity policy; another treats them as
generic technical parser validation. Neither view proves downstream filesystem
access or complete confinement. The fact of same-input variation is confirmed;
its internal model cause and the correct category boundary remain unresolved.
The earlier path changes cannot be attributed solely to larger context.

### Permission key: responsibility is clearer than suitability

Both annotations classify the isolated `canonical_mutations_allowed` expression
as policy. The second declines to infer Specification suitability without the
branch/effect; the first regarded the explicit permission subject as sufficient.
This is a distinct opportunity-evidence threshold question. More context resolves
the branch's review-eligibility role; it does not prove writer authorization.

### Active gate: an overlapping category needs an explicit tie rule

The second declaration annotation treats active-gate precedence as lifecycle
policy, agreeing with both bundle annotations. The first declaration annotation
treated `none` versus active gate as variant routing. A majority is not an
independent semantic criterion. The exact predicate chooses precedence; dispatch
among individual gate actions is subsequent code. Retain that evidence in the
next rubric review rather than silently overriding the earlier answer.

## Reference disposition and next experiment

The **six changed axis labels** in the four states above remain unapproved for
hard provider scoring. The other thirty labels are retained provisionally, with
their original uncertainties. This is the integrator's review, not human gold or
a second independent adjudication vote. `needs_review` and `unknown` are valid
labels rather than automatic quality failures. No raw label was replaced.

The next bounded task is a **versioned rubric proposal** covering:

1. What distinguishes generic path validation from a domain integrity policy,
   and what concrete consumer/contract evidence establishes that distinction.
2. When an explicit permission subject establishes opportunity without a shown
   effect, keeping concern kind independent from suitability.
3. How to choose the primary responsibility when a boolean lifecycle predicate
   also distinguishes domain states; the target boundary must remain exact.

Apply a new rubric only to a new frozen reference, reviewed against examples
from these boundaries. Retain both existing rounds as historical evidence.
Only then prepare the next provider protocol; a formal evidence gate must be a
separate arm from raw model classification. **No Jev/Luna calls were made here.**

## Artifacts and verification

- `annotation-packet-01.json` through `annotation-packet-03.json`: balanced
  delivery inputs; matching templates remain blank.
- `source-mapping.json`: integrator-only target/view/delivery assignments.
- `balanced-preparation-receipt.json`: frozen source/state and producer bindings.
- `annotation-assignments.json`, `annotation-prompt.txt`: scoped handoff metadata,
  exact input/output hashes and dispatched prompt bindings.
- `independent-annotations-01.json` through `independent-annotations-03.json`:
  original outputs; semantic reasoning, code quotes and uncertainty per axis.
- `annotation-receipt.json`: replayable structural validation; no semantic proof.
- `same-input-comparison.json`: raw same-state annotation agreement and changes.

From `evals/jev-classification`:

```sh
python3 prepare_balanced_context_reference.py
python3 validate_context_annotations.py --run runs/2026-10-13-balanced-context-reference
python3 compare_context_references.py
python3 -m unittest -v test_prepare_context_evidence.py test_validate_context_annotations.py test_balanced_context_reference.py
```

The preparation writer requires `--write` and refuses any existing delivery
artifact before mutation. Default replay and comparison are offline and read
only. Tests reproduce the original `6/0/0` delivery imbalance, require `2/2/2`
per annotator, prohibit duplicate targets within a packet, preserve all eighteen
state hashes, check blank labels and verify overwrite refusal.

The code excerpts retain SpecGraph's Apache-2.0 license, copied in
[upstream-LICENSE.txt](upstream-LICENSE.txt); selection and evaluation tooling
do not relicense them. Exact source spans, attribution and full-file verification
are retained in the [original source preparation](../2026-10-13-context-evidence-preparation/README.md).
