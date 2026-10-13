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
- **Prevention:** the [prepared BDD factor diagnostic](runs/2026-10-13-bdd-steps-factorial-preparation/README.md)
  holds the target, architecture profile and rubric fixed while separately
  showing the adopted values contract and the same-decision Specification
  evaluation link. It assigns one condition to each fresh context and does not
  seed expected labels.
- **Verification:** its offline producer binds all four source files to the
  pinned revision and prepares three blank assignments per cell. No annotation
  or provider run has started; v2 raw results and H2 remain unchanged.

## Record template

1. Failure and exact command/criterion.
2. Frozen input/output and source/reference identities.
3. Minimal reproduction or discriminating comparison.
4. Confirmed cause, hypotheses still open, and the evidence distinguishing them.
5. Bounded correction/prevention, including any scope intentionally deferred.
6. Regression check or new diagnostic result, and what it does not establish.

Keep lessons in repository artifacts rather than only in chat history. Do not
turn a failed criterion green by relabelling an already observed case.
