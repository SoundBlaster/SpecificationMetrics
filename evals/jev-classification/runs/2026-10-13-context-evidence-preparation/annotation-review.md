# Independent annotation and integrator review

## Result and authority

Three fresh subagent contexts annotated all **18 cases / 36 axis labels**. Each
received one packet and blank template in a separate temporary directory, with
`fork_turns: none`, no model/effort override, no author labels, provider outputs,
source mapping, corpus README or other evidence views. Each reports reading only
its two assigned files. Input copies were byte-identical before dispatch and
after completion; original outputs were copied without editing.

This is independent model annotation followed by the author's/integrator's
review, **not human gold or consensus**. Model identity was inherited, not
independently verified. Isolation was by fresh conversation, scoped copies and
instructions; the shared filesystem was not an enforced sandbox. This stage made
**zero Jev/Luna requests** and wrote no S/U or production classifier state.

The [receipt](annotation-receipt.json) binds the assigned input/output bytes,
prompt template and validator. Structural checks validate coverage, state hashes,
labels, explicit reasoning, uncertainty and code quotes supporting both axes.
They cannot prove a quote entails a label or that the input-scope self-report is
true. No raw label was corrected or replaced during integration.

## What each view produced

Cells contain `opportunity / concern_kind`.

| Target | Expression only | Containing declaration | Evidence bundle |
|---|---|---|---|
| YAML newline | excluded / mechanics | excluded / mechanics | excluded / mechanics |
| Manifest path | needs_review / unknown | eligible / policy | excluded / mechanics |
| Criterion coverage | needs_review / unknown | eligible / policy | eligible / policy |
| Canonical mutation flag | eligible / policy | eligible / policy | eligible / policy |
| Active gate | needs_review / unknown | eligible / variant_behavior | eligible / policy |
| BDD scenario steps | needs_review / unknown | eligible / policy | excluded / policy |

Expression-only annotation retained uncertainty in four cases, but classified
newline formatting and the explicit mutation-permission key. Therefore neither
context length nor absence of fragments is an automatic abstention rule.

**One annotator per view confounds annotator and evidence effects.** Cross-view
differences are descriptive; they are not same-input disagreement rates, causal
context effects, provider accuracy or eighteen independent code families. There
are six related families and no Jev/Luna predictions for this corpus yet.

## Integrator disposition

### 1. YAML newline: stable representation mechanics

Cases `context-17`, `context-08`, `context-06` all select `excluded / mechanics`.
The expression tests a newline suffix; the larger views show `yaml.safe_dump`
and `rendered += "\n"`. The supplied evidence supports a formatting decision.
Retain the raw labels as a provisional reference for these exact states.

### 2. Manifest path: unresolved policy/mechanics boundary

Cases `context-12`, `context-09`, `context-16` differ on both axes. The middle
annotator treats the rejection of an unsafe manifest path as a named admissibility
rule. The bundle annotator treats the same checks as parser input validation;
its extra consumer converts manifest entries into a dictionary. The fragment
does not show downstream filesystem access or a particular confinement root.

Both nonminimal views contain the **same** `_safe_path` implementation. Added
parser context does not erase its admissibility constraint, and the word
`unsafe` does not alone establish a product authority boundary. The rubric does
not settle whether this generic path-safety invariant is a distinct product
decision. Evidence-sufficiency and rubric interpretation are competing causes.

Retain `context-12`'s abstention. Leave **both axes** of `context-09` and
`context-16` unapproved for hard scoring. Do not silently turn either raw answer
into `needs_review`, count the larger view as gold, or call this a provider bug.

### 3. Criterion coverage: operands and effect become explicit

`context-15` lacks operand types and effects. In `context-05` and `context-04`,
`requested` and `covered` are sets of acceptance-criterion identifiers, and the
test returns `missing_criterion_binding`. The bundle also shows the claim cannot
be satisfied when a reason remains. These facts support the two nonminimal
`eligible / policy` annotations. Retain all three raw labels provisionally,
with their original uncertainty. This does not prove complete claim validity.

### 4. Canonical mutation flag: policy without inferred writer authority

All three views select `eligible / policy` (`context-13`, `context-11`,
`context-10`). The expression explicitly concerns permission to mutate canonical
material. The containing function shows that only the singleton `False` passes
this prerequisite for recognizing a reviewable gap; missing, true and other
values are skipped. It does **not** show that this function authorizes a writer.
Retain the labels provisionally and preserve that distinction in later scoring.

### 5. Active gate: stable opportunity, disputed primary responsibility

`context-14` abstains. Both nonminimal views choose `eligible`, but `context-18`
calls the target variant dispatch and `context-01` calls it lifecycle policy.
The same predicate selects active-gate handling before status-based refinement.
It can be described both as discriminating `none` from active gate states and as
giving gate resolution precedence. Dispatch over individual gate actions occurs
after this predicate, but the current rubric lacks an explicit tie rule for this
overlap. The additional action descriptions do not alone resolve that overlap.

Retain opportunity labels provisionally. Leave the **concern_kind** labels of
`context-18` and `context-01` unapproved for hard scoring. A forced majority vote
would hide the category ambiguity.

### 6. BDD scenario steps: evidence of existing ownership

`context-02` abstains. `context-03` exposes required scenario steps and reports
an `invalid_value` finding, but its method fragment omits the enclosing class
and base. Its `eligible / policy` judgment is relative to that limited evidence,
not a claim that the real project needs another Specification.

`context-07` includes `BDDScenarioValuesSpec(BDDPolicy)`, its `rule_ref`,
`BDDPolicy(Specification[BDDContext])` and `_evaluate` calling `findings`.
That supports **excluded / policy**: it is still a rule and is already represented
as a Specification. Retain these evidence-relative annotations provisionally.
Production S/U accounting must use ownership evidence rather than the minimal
view's architectural-fit suggestion.

## Lessons and next bounded experiment

1. Context sufficiency, opportunity, responsibility and existing ownership are
   distinct questions. A Specification can own a policy and therefore be excluded
   as a *new* opportunity; exclusion does not mean mechanics.
2. More context can expose ownership without making every category unambiguous.
   Preserve semantic uncertainty separately from structurally valid model output.
3. **Next:** obtain a second blind annotation on each of the four disputed exact
   states (`context-09`, `context-16`, `context-18`, `context-01`), with the same
   frozen rubric. Each fresh context must receive only one evidence view per
   target and no previous answers. This tests same-input stability before a
   new rubric version or provider protocol is prepared.
4. If same-input labels still vary, adjudicate the two boundary definitions and
   publish a versioned rubric/reference. Do not rewrite this diagnostic. Freeze
   provider wires and any separate formal context-gate arm only afterwards.

Six disputed axis labels remain unapproved; the reference is **not frozen for
provider scoring**. Provisional retention of the other annotations is an
integrator judgment, not an independent second vote. The original H2 provider
failure cause remains unresolved.

## Verification

- `python3 -m unittest -v test_prepare_context_evidence.py test_validate_context_annotations.py`:
  13 passed. Negative cases cover missing/duplicate/stale cases, cross-case
  invented evidence, one-axis evidence, absent uncertainty and invalid mapping.
- `python3 prepare_context_evidence.py --source-repo /path/to/SpecGraph`:
  saved preparation reproduced; all pinned Git source bindings verified.
- `python3 validate_context_annotations.py`: offline receipt reproduction,
  with no source execution, provider requests or label overrides.
