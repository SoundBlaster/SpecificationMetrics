# Failure → cause → prevention → verification

Use failures as the input to a bounded improvement cycle. Each record must say
what failed, what evidence was retained, whether the cause is confirmed, what
prevents recurrence, and how that prevention was checked. An unresolved cause
is an explicit result; it does not justify inventing a provider explanation.

## Confirmed: strict mass validation interrupted a semantic study

- **Evidence:** [v1 receipt](runs/2026-10-13-contrastive-native-wires/receipt.json)
  stopped on request 42; [diagnosis](runs/2026-10-13-contrastive-native-wires/native-contract-diagnosis.json)
  retains the exact 0.99 total and a consistent selected maximum.
- **Confirmed cause of the interruption:** our `1e-6` admission rule plus the
  study-wide fail-fast lifecycle. The provider's precise serialization/rounding
  mechanism remains unconfirmed; it is a separate question.
- **Lesson:** match numerical acceptance to the task and documented precision;
  separate answer validity, semantic quality and interruption of the schedule.
- **Prevention:** the [versioned v2 warning policy](contrastive-mass-warning-v2.md)
  preserves raw numbers/confidence and continues after bounded warnings or
  result-local failures. Identity and transport failures remain explicit stops.
- **Verification:** `test_choice_mass_warning.py` covers 0.99/1.01 boundaries,
  just-outside values and the saved failing response; `test_contrastive_mass_warning.py`
  checks continuation versus usable coverage. The old replay still rejects
  the original response under v1. A later completed live run had no mass warning,
  so it does not establish that the tolerance caused live completion.

## Confirmed: a CLI test confused Python and JSON representations

- **Evidence:** during v2 implementation,
  `test_cli_preparation_is_exclusive_and_offline` failed because the in-memory
  retry configuration contained a tuple and the JSON round-trip contained a list.
- **Cause:** the test compared Python representations of a serialized contract.
- **Prevention:** compare canonical JSON bytes for JSON round-trip assertions.
  Preserve direct Python-type checks for contracts where the type itself matters.
- **Verification:** that test and the 96-test focused suite passed in PR #39.
  This was a test assertion defect, not a provider or runtime failure.

## Unresolved: concern-kind guesses with insufficient context

- **Evidence:** [PR #40](https://github.com/SoundBlaster/SpecificationMetrics/pull/40)
  records all 16 withheld opportunity answers as `needs_review`, while joint H2
  remains Jev 2/4 then 1/4 and Luna 3/4 in both repeats. Jev also changes one
  withheld responsibility label between repeats. V1 shows the same family of gap.
- **Cause status:** unresolved. Lexical cues, rubric interpretation, missing
  downstream effects and model limitations are competing hypotheses.
- **Lesson:** eligibility uncertainty and responsibility uncertainty are separate.
  A smaller context is an intervention, not an automatic `unknown` gold label.
- **Next prevention experiment:** [real-source context packet](runs/2026-10-13-context-evidence-preparation/README.md),
  with six new production targets and three evidence views each. Preserve exact
  target bytes, source spans, imports/declarations and source attribution.
  Obtain fresh independent labels before provider inference or a gate comparison.
- **Current boundary:** no semantic correction is claimed. A subsequent
  [independent annotation review](runs/2026-10-13-context-evidence-preparation/annotation-review.md)
  adds a new provisional reference without changing historical labels, provider
  prompts, thresholds, production classifier or S/U metrics. Six axis labels
  remain disputed: manifest-path policy/mechanics and gate policy/variant routing.
  One annotator per view confounds context and annotator effects; same-input
  reannotation is the next discriminating comparison, before a rubric change.

## Confirmed exposure path: combined context-ablation packet

During this preparation review, the combined catalog exposed all three evidence
views of each expression to a prospective annotator. A prose instruction not to
transfer labels could not remove access to fuller evidence. No annotation had
run, so actual label contamination is not claimed.

The regression `test_annotation_delivery_never_combines_views_of_one_target`
failed before the patch because isolated delivery artifacts were absent. The
prevention patch generates three disjoint six-case packet/template pairs and
requires a fresh isolated annotation context for each. The same regression now
checks one view and one occurrence of each target per delivery packet, plus
complete eighteen-case coverage. The integrator-only catalog remains available
for provenance and later provider preparation.

## Confirmed design defect: evidence mode correlated with annotator

- **Evidence:** [PR #41 review](https://github.com/SoundBlaster/SpecificationMetrics/pull/41#discussion_r4256695179)
  and the original source mapping show all six expression-only states went to
  one annotator, all declarations to another and all bundles to a third.
- **Confirmed cause:** delivery partitioning by mode made mode perfectly
  correlated with annotator. Cross-view differences could not distinguish these
  effects. Describing that limitation did not correct the experimental design.
- **Prevention:** a [new balanced producer](prepare_balanced_context_reference.py)
  rotates modes across targets: two states per mode per fresh annotator, still
  one view of each target. Preserve the original producer, inputs and annotations;
  enforce balance in the scoped workflow instructions and regression tests.
- **Verification:** `test_original_delivery_reproduces_the_mode_annotator_confound`
  reproduces `6/0/0`; `test_modes_are_balanced_without_showing_two_views_of_one_target`
  requires `2/2/2`, six distinct targets per annotator and blank delivery labels.
  Saved state replay proves no source, rubric or target expression was changed.
- **New diagnostic evidence:** [the completed balanced annotation round](runs/2026-10-13-balanced-context-reference/README.md)
  agrees with the earlier round on 15/18 labels for each axis and both axes on
  14/18 states. The path answers reverse on the same inputs; context size alone
  cannot explain the observed disagreement. This confirms annotation instability,
  not a provider's internal cause. Four states/six axis labels remain unapproved;
  a versioned rubric proposal is next. No Jev/Luna requests or metric writes.

## Proposed prevention: explicit decision-role criteria

The [expression-fit v2 proposal](expression-fit-rubric-v2.md) now records explicit
decision-role witnesses and tie rules for the disputed boundaries. It is a
proposed prevention pending fresh annotation, not a validated provider fix.
Its plan also requires task identity to bind rubric/questions: matching state
hashes alone cannot establish identical inputs across a rubric change. No
historical reference, production prompt or metric state was changed.

## Confirmed criterion failure: rubric-v2 decisive coverage on BDD steps

- **Evidence:** the [v2 independent reference](runs/2026-10-13-rubric-v2-reference/README.md)
  retains 36 fresh annotations over the same eighteen source states. Both
  rounds match on 18/18 cases per axis, but each axis has only 10/18 decisive
  labels. The frozen H2 requires decisive labels on ten v1 development controls;
  `context-03` abstains on both axes in both rounds, so H2 fails at 9/10 controls.
- **Cause status:** the criterion failure is confirmed. The semantic cause is
  unresolved. Annotators cite the absent contract distinguishing a BDD
  nonempty-steps domain requirement from input/schema validation. Excessive v2
  abstention, missing source context and overconfident v1 labels remain
  competing explanations. The rationale does not establish internal model
  reasoning, and the v1 labels are not gold.
- **Lesson:** report repeat agreement and decisive coverage together. A stable
  abstention is not evidence of improved classification; do not remove a failed
  control after seeing the result.
- **Prevention:** keep H2 as a separate gate from H1, bind each annotation to
  the exact rubric and task digest, and preserve raw output hashes. A new
  diagnostic must source-ground the BDD contract and test semantic-contract and
  ownership evidence separately where the source permits.
- **Verification:** the new offline validator replays both rounds and reports
  H1 pass / H2 fail. Seven regression tests cover task-identity binding, raw
  result replay, the H2 guard against perfect agreement under blanket
  abstention, and overwrite refusal. The reference remains unapproved for
  provider scoring; no provider calls or metric writes were made.

## Source audit: BDD contract exists; the failed annotation context omitted it

- **Evidence:** at pinned SpecGraph commit `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`,
  `SG-SPEC-0070` states that BDD `steps` is a nonempty ordered list of nonempty
  strings and records human approval. Its characterization test rejects an
  empty step list. The same commit links `BDDScenarioValuesSpec` through
  `BDDPolicy(Specification[BDDContext])`, `spec_id = SG-SPEC-0070`, its
  `_evaluate` implementation and composition evaluation. V2 `context-03`
  supplied only the method body, not those contract or implementation-link
  fragments.
- **Cause status:** confirmed that the source contract exists and was absent
  from the annotation input. This disproves a repository-wide missing-contract
  explanation. It does not establish that the omission caused the abstentions.
  The adopted contract specifies input validity but does not itself settle the
  v2 policy-versus-mechanics boundary: domain completeness and representation
  validity remain distinct interpretations.
- **Lesson:** distinguish a missing rule in the product from missing evidence
  in the prompt. A formal validity contract does not automatically establish
  whether its concern kind is domain policy or input mechanics.
- **Prevention:** the [balanced BDD factor diagnostic](runs/2026-10-13-bdd-steps-balanced-factorial-preparation/README.md)
  holds each target, architecture profile and rubric fixed while separately
  showing the adopted values contract and the same-decision Specification
  evaluation link. Its assignments cross evidence condition with annotator
  across distinct targets and do not seed expected labels.
- **Verification:** its offline producer binds all four source files to the
  pinned revision and prepares three blank assignments per cell. No annotation
  or provider run has started; v2 raw results and H2 remain unchanged.
- **Follow-up CI failure:** both general CI runs caught a stale
  `producer_sha256` in the saved receipt. The producer had received a final
  whitespace-only edit after the packet was frozen, but its self-hash receipt
  was not regenerated. Regenerating in a scratch directory showed that only
  `preparation-receipt.json` needed refresh; all packet hashes remained stable.
  The existing replay test caught this drift locally and will guard future
  producer edits.
- **Follow-up review finding:** the first preparation assigned one evidence
  condition to each annotator. Condition and annotator were therefore nested,
  so differences could not be attributed to evidence. Its target context also
  showed only an anonymous method body, not the containing Specification class.
- **Correction:** preserve that unstarted draft as superseded. The replacement
  uses four related predicates from two classes under `SG-SPEC-0070`; each of
  twelve contexts sees all four evidence conditions, one per distinct target.
  Each target-condition receives three contexts, packet position is balanced
  across conditions, and linked cells include the contiguous containing class
  and method plus the Specification base/evaluation path. No label is seeded.
- **Verification:** regression tests assert the target-condition and
  condition-position balance, prohibit repeated targets per context, and check
  that each linked target occurs inside its named class method. At preparation
  time no annotation or provider request had started. The subsequent
  [completed diagnostic](runs/2026-10-13-bdd-steps-balanced-factorial-results/analysis.md)
  retained 48 annotations in twelve contexts; no Jev/Luna request was made.

## Adjudication: ownership evidence does not settle primary responsibility

- **Evidence:** the balanced BDD diagnostic has one concern-kind split:
  `bdd-values-step-item`, cell 03, is `policy` once and `unknown` twice. All three
  opportunity labels are `excluded`. Annotator-01 cites the values-policy
  finding and Specification evaluation pipeline while acknowledging that the
  precise criterion behind `step.valid` is absent.
- **Cause status:** the packet omits the validity definition/contract and the
  retained rationale cites the finding and Specification evaluation path.
  The integrator judges this insufficient for `policy` under the frozen v2
  rubric. The model's internal cause remains unknown; naming bias, cross-case
  carryover and sampling variation have not been distinguished. This is not evidence
  that the full-source decision is mechanics or that its domain role cannot be
  established by additional evidence.
- **Lesson:** exact quote validation checks provenance, not semantic support.
  Match a witness to its axis: an evaluation path can settle existing
  representation while a material missing validity contract leaves primary
  responsibility unknown. A bare rule address is not its resolved contract.
- **Prevention:** the [separate integrator adjudication](runs/2026-10-13-bdd-step-item-adjudication/README.md)
  recommends `excluded / unknown` by applying the existing E2/E5/E6 rules.
  Preserve the original split, all raw labels and prior H2; the advisory review
  is not blind, human gold or a provider-scoring reference. No rubric revision
  is necessary for this decision.
- **Verification:** a separate receipt binds the three packets and raw outputs,
  identical state/task/rubric identities, original labels, and exact quoted
  rubric/packet witnesses. The next diagnostic should vary the semantic witness
  and source-derived naming cues before attributing the outcome to a model bias.

## Preparation findings: validity definition, cross-case leakage and runtime

- **Evidence:** the pinned source defines `TextInput.valid` as
  `value is not None and bool(value.strip())`; boundary conversion maps
  non-strings to `None`. `ScenarioInput.id`, `.title` and each `.steps` item
  share this type. The [new preparation](runs/2026-10-13-definition-owner-names-preparation/README.md)
  records seventeen verified excerpts from nine files.
- **Cause status:** the operational criterion and nonmutating use of `strip`
  are confirmed by source and a focused execution check. The primary domain
  purpose remains a separate semantic question. Supplying this same definition
  in one case of a multi-BDD packet would directly expose a withheld dependency
  of another case; this is a prospective design defect, not a demonstrated
  internal cause of any historical label.
- **Prevention:** select four distinct helper families, keep one target view
  per context, balance both target and condition positions, and prohibit direct
  `TextInput`-definition leakage into unrelated cases. The evaluation instructions
  now require this dependency-level check. Preserve rule strings and the
  Specification marker while reversibly renaming only selected owner tokens.
- **Verification:** seven new tests cover assignment/provenance, transformation,
  leakage, blank templates, source behavior and exclusive artifact creation.
  The initial source-execution test exposed the host's Python 3.9.6, which
  cannot evaluate the pinned Python 3.10 union annotations. Re-running in a
  repository virtual environment with Python 3.10 passed; the test now reports
  an explicit minimum-version failure. CI runs it on Python 3.10.
- **Limits:** a source definition does not dictate a concern-kind label; an
  exact quote does not establish semantic support; partial owner renaming does
  not remove all domain vocabulary. Prospective criteria are frozen separately
  from blank annotation inputs. No run, gold labels or metric effect is claimed.

## Definition/owner-name diagnostic: agreement without a gold reference

- **Evidence:** the [completed run](runs/2026-10-13-definition-owner-names-results/analysis.md)
  contains 64 annotations from sixteen fresh contexts. Focal opportunity is
  `excluded` in 16/16, including neutral-owner cells; focal concern is `policy`
  in all cells. The eight extended-context rationales contain neither a claim
  that the nonblank criterion is unavailable nor that `strip` changes stored
  text. The newline control is `excluded / mechanics` in 16/16.
- **Cause status:** the naming histograms match in this partial ablation; this
  does not establish universal name invariance or a causal explanation for
  earlier disagreement. Definitions are reflected in extended-context reasons,
  but they do not change these Choice labels. No internal model cause is proved.
- **Lesson:** a useful context addition can improve the specificity of a reason
  without changing its label. Stable same-decision ownership, operational
  predicate semantics and normative domain purpose need separate evidence.
  Unanimous `policy` answers remain proposals; no adopted Requirement or human
  gold was supplied for the focal semantic distinction.
- **Prevention/verification:** preserve frozen preparation and raw outputs;
  replay hashes, four-case assignments, independent axes and case-local quotes
  with `validate_definition_owner_annotations.py`. Nine regression checks reject
  stale identities, changed tasks, foreign-case quotes, duplicate cases, missing
  evidence and undeclared isolation. Rationale review is recorded separately
  and is explicitly an integrator judgment, not an automated semantic grader.
- **Unresolved:** the manifest-path target remains unknown in 16/16. The
  permitted-reference contract is absent from supplied packets; this does not
  claim it is absent from SpecGraph. Recover that contract before deciding
  whether this site defines domain integrity or generic representation rules.

## Replay review repair: manual evidence and receipt invariants

- **Evidence:** PR #49 found that deleting/replacing the manual review or
  declaring seven provider calls/nonempty excluded attempts still allowed the
  original replay to succeed and report zero calls. Running
  `python -m unittest -v test_validate_definition_owner_annotations.ReplayArtifactTests`
  before the correction reproduced 20 failed subcases and one error.
- **Confirmed cause:** the replay validated raw annotations but did not consume
  the fourth criterion's manual artifact or the receipt's execution/authority
  invariants. Successful raw evidence validation was being reported with
  unverified execution metadata.
- **Correction:** bind the unchanged review bytes into the receipt, validate
  all eight review-to-output bindings and manual aggregate consistency, and
  reject unsupported receipt declarations before reporting results. Manual
  rationale judgments remain manual, including failed judgments.
- **Verification:** eight new regression tests cover missing/empty/changed
  reviews, stale/duplicate/missing bindings, inconsistent counts, preserved
  manual failure and false receipt metadata. The complete focused preparation
  and replay suite passes 24 tests. No raw labels, judgments or criteria change.

## Manifest-contract preparation review repair (2026-10-14)

- **Evidence:** PR #52 identified that the twelve v1 contexts each received only
  one target in one evidence mode, contrary to the balanced-mixture rule in
  AGENTS.md. No annotator had been launched. PR #54 identified a separate
  delivery binding gap: a synthetic attempt retained correct frozen hashes
  while replacing each actual packet, template or prompt with `{}`. The old
  `validate_attempt` accepted all three altered-file scenarios.
- **Confirmed causes:** one-mode-per-context assignment confounded context/run
  identity with evidence mode. Receipt comparisons consumed regenerated frozen
  bytes but never opened the files dispatched to the annotator.
- **Correction:** preserve v1 artifacts and producer unchanged; introduce v2
  with four distinct source families and all four modes per context. Each
  target-cell and each target/mode position has three repetitions. Read actual
  delivered packet/template/prompt bytes in a delivery preflight and again in
  attempt validation, comparing both content and recorded hashes. Case-local
  evidence remains isolated across the four annotations.
- **Verification:** `python -m unittest -v test_manifest_contract_factorial.py
  test_manifest_contract_balanced.py` passes 22 tests, including the three
  confirmed file substitutions, missing files, foreign-case quotes and
  duplicate cases. Frozen preparation replay passes without annotation or
  provider calls. Review records and blank labels remain non-gold.
- **Limits:** balancing removes the assignment confound but does not prove
  independence from model bias, cross-case priming or rater-target interaction.
  Pre/post byte checks and a self-reported input scope do not establish actual
  model consumption or filesystem isolation. Packet/template paths must remain the declared annotator paths; a pristine
  copy elsewhere cannot hide changes to those files. Retain the delivery
  directory through replay rather than regenerating substitutes.

## Scope permitted-input contract repair before dispatch

- **Evidence:** PR #57 review found that v3.0 prepended mandatory scope use but
  inherited a later exhaustive semantic-input list omitting `evaluation_scope`.
  The complete composed prompt contains both clauses; no annotation had run.
- **Confirmed cause:** concatenating a new instruction did not update the
  inherited exhaustive contract. The protocol permitted inconsistent instruction
  resolution; no claim is made about a model having already ignored scope.
- **Correction:** preserve the published v3.0 producer/artifacts, supersede
  before annotation with v3.1, rewrite the complete allowed-input list, and bind
  structured scope acknowledgments into new templates/task identities.
- **Verification:** `test_scope_binding_v3_1.py` checks the final composed prompt,
  preserved semantic states, changed task identities, explicit unit/binding
  hashes, overwrite refusal and prompt drift. Runtime rationale fidelity remains
  a manual semantic judgment; copying a scope field is not proof of understanding.

## Intent uncertainty versus architecture action (2026-10-15)

- **Evidence:** the [human clarification](runs/2026-10-15-scope-binding-adjudication-v2/README.md)
  corrected the practical interpretation of four pinned examples. For ambiguous
  path design, inspect intent/proposal/spec and prefer strict formalization if
  ambiguity remains. Gate precedence is a candidate, formatting belongs to tool
  rule sets, and simple Specification composition needs no extra wrapper.
- **Confirmed design mismatch:** our `needs_review / unknown` presentation left
  architectural action unspecified although the human has an explicit style
  preference. This does not establish why a model produced a particular label,
  or prove that every historical abstention was incorrect.
- **Correction:** version the output contract as v4 with concern kind, ordinal
  evidence support and recommendation. Preserve uncertain role even when the
  recommendation is `formalize`; retain exact source/scope and documentary
  authority. Simple NOT/AND/OR and formatter rules are reuse boundaries.
- **Prevention:** `test_intent_first_v4.py` accepts unknown/insufficient/formalize,
  rejects unjustified certainty and action/basis contradictions, and exercises
  stale identities, source substitution, documentary acknowledgments and prompt
  drift. Four integrator examples illustrate the contract; they are not model
  predictions or independent gold. JSON Schema plus Python validation establishes
  structural/identity consistency, not semantic correctness.
- **Limits:** frozen v3.1 data and raw answers are unchanged. No current accuracy
  score improves by redefining a past task. Provider wire mapping, reference
  adjudication and a bounded live comparison remain separate work.

## Record template

1. Failure and exact command/criterion.
2. Frozen input/output and source/reference identities.
3. Minimal reproduction or discriminating comparison.
4. Confirmed cause, hypotheses still open, and the evidence distinguishing them.
5. Bounded correction/prevention, including any scope intentionally deferred.
6. Regression check or new diagnostic result, and what it does not establish.

Keep lessons in repository artifacts rather than only in chat history. Do not
turn a failed criterion green by relabelling an already observed case.
