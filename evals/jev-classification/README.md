# Jev prompt evaluation

The supported Python baseline is **3.11+** across collection, evaluation and CI.
Install `requirements-categorical-pilot.lock` into the repository `.venv` for
the pinned Jev4Mellea 0.8.0 Responses integration and common evaluation tools.
Native and ordinary models share category semantics; label-only Responses
answers never acquire synthetic native probabilities. Old benchmark artifacts
keep their historical runtime metadata and are replayed on the current baseline.

Current paired-reference design assessment:
[configuration qualification v2 and prepared repeatability pilot](paired-reference-qualification-v2.md).
This supersedes the invocation-ID interpretation in qualification v1 while
preserving its frozen artifacts and scoring v1. The subsequently authorized
[24 Sol 6.1 Medium repeats](runs/2026-10-18-sol61-medium-repeatability-v1/README.md)
completed in fresh contexts with no historical labels: all eight views were
unanimous. Their top line is a model-specific comparator, not independent semantic
truth. Preparation artifacts and the old scoring contract remain unchanged.

The matched [Jev/Luna live comparison](runs/2026-10-18-jev-luna-sol-comparison-v1/diagnosis.md)
completed all 16 requests: Jev agreed with 15/16 primary-axis labels but had five
role/support consistency conflicts; Luna agreed with 7/16 and mostly abstained.
The full raw-label comparison is 25/32 versus 15/32. These are agreement counts
against Sol on four targets, not semantic accuracy or production acceptance rates.

The subsequent [semantic-instruction parity repeat](runs/2026-10-18-semantic-instruction-parity-live-v1/README.md)
reused those same 24 Sol annotations with **zero new Sol calls**. Transferring
Sol's existing semantic guidance and category catalog raised Jev agreement from
25/32 to 31/32 (primary axes 15/16 → 16/16) and reduced conflicts from five to one.
Luna Decision rose from 15/32 to 18/32 while conflicts increased from one to two.
All 16 native requests completed without TLS retries. This remains a small
instruction-condition diagnostic; the general backend refactor is deferred.

The [ordinary-Luna SDK pilot](runs/2026-10-18-ordinary-luna-live-v1/README.md)
then used Jev4Mellea 0.8.0 / Responses, `gpt-6-luna` / low on those same eight
views: **32/32 Sol agreement, 16/16 primary agreement and zero conflicts**.
All eight calls completed in 34.939 seconds with no retries; usage was 35,167
input / 874 output tokens. Native Jev and Luna Decision remain at 31/32 and
18/32 from their saved run; Sol was not called again. Ordinary client latency
was greater than the historical native HTTP timings, and monetary cost is unknown.
This supports a bounded compatibility/quality observation, not general accuracy,
retrieval gain or an unconditional efficiency claim. Python 3.11 is now the
common supported baseline, including the unchanged historical offline replays.

This Promptfoo suite compares two versions of the opportunity question against
the same Jev model, candidate state, label set, and concern-kind question:

- `baseline-v1` reflects the current classifier contract in concise form.
- `boundary-test-v2` makes the domain-impact test, boundary ownership, and
  abstention rules explicit. It tests the hypothesis that Jev needs a sharper
  decision procedure, not a larger prompt or more repository context.

The default smoke case is `publication.site.069` from SpecGraph source code.
Its expected labels are a **pilot hypothesis**, not an
independent human-reviewed gold label. The diagnostic proposed `policy` and
identified the site as a possible Specification opportunity; neither result is
formal approval. One case can reveal prompt behavior and probability movement,
but cannot establish classifier accuracy or generalize across code.

The state contains the exact pinned source excerpt, imports and selected
supporting declarations, with previous diagnostic labels excluded. It does not
send the repository or a whole source file. Add cases only with a
documented label source and mark provisional labels explicitly. Keep uncertainty
visible; Jev Choice probabilities are relative to the fixed labels and are not
calibrated confidence.

The [evaluation protocol](methodology.md) defines the objective, annotation,
group splits, paired comparisons and acceptance criteria. The
[SpecGraph corpus](corpus/README.md) adds 60 source-grounded cases in 34 families,
including 15 historical before/after pairs. All corpus annotations remain
unreviewed hypotheses. [Review packet](corpus/review.md) and
[blank review template](corpus/review-template.json) omit proposed labels.
No corpus-wide hosted evaluation has been performed; two providers would make
120 API requests. The default command still sends only the one smoke case.

## Run

Requires Node.js >=22.22.0 and a TypeSafe key. The promptfoo version is pinned in
`package-lock.json`; Jev is pinned to `1.13.0` in the config.

```bash
cd evals/jev-classification
npm ci
export TYPESAFE_API_KEY='…'
npm run eval
```

This sends the checked-in candidate state to TypeSafe Jev. It makes hosted
requests and may incur usage charges. It is deliberately not part of regular
CI and does not run during local validation. The result is written to
`results/latest.json`. The current one-case comparison sends two requests,
one per prompt variant; each request asks both classification questions. The
Promptfoo UI can be opened with:

```bash
npm run view
```

## Offline checks

```bash
python3 validate_cases.py
python3 -m unittest -v test_validate_cases.py
npm run test:offline
npm run validate
```

These checks validate dataset invariants and Promptfoo configuration without a
TypeSafe key or model request.

## Reading results

For each axis, Promptfoo reports whether the returned Choice matches the
case's pilot hypothesis. The assertion score is categorical agreement (1 or 0);
expected-label probability remains in the assertion reason and raw output.
Compare both:

1. whether the selected label changed or matched;
2. how the probability mass over the fixed labels moved.

Do not pick a prompt solely because it raised one expected-label probability
for this one case. Review the full per-label distributions, Jev model/version,
and additional cases with independently reviewed expected labels first.

The experiment changes only the opportunity instructions between providers.
The model version, state, criteria, and concern-kind question stay fixed, so
the comparison isolates one prompt factor. It does not evaluate source-context
size or redaction; those require a separate experiment with the same prompts
and different bounded states.

The first run is summarized in
[`runs/2026-10-04-publication-site-069.md`](runs/2026-10-04-publication-site-069.md).
Its exact original input is archived beside the report. That input contained a
previous `policy` diagnosis; this is label leakage, so the run cannot support an
independent quality claim. The updated source fixture must be treated as a new
input version; the previous output is not a result for it.

The suite uses Promptfoo's documented custom JavaScript provider interface.
The TypeSafe page currently documents a built-in provider, but the pinned npm
release `0.123.1` does not resolve `typesafe:jev-1.13.0`; the direct adapter
keeps this evaluation runnable against that published release. The adapter
uses one HTTP request per case/provider pair, a 30-second timeout, rejects
redirects, caps response size, and does not implement retries. It keeps bounded direct `fetch` for HTTP and stores only validated successful
provider results through Promptfoo's public cache helpers. Identical requests
reuse that cache; `npm run eval:fresh` (or Promptfoo `--no-cache`) forces a fresh
request. The key includes endpoint, model, state, rubric and an opaque credential
partition digest; credentials are not stored in keys or values. Errors and
oversized/malformed responses are never cached. Cached responses are marked
`cached: true` and `responseSource: cache`; their usage metadata describes the
original request, not newly billed tokens. Cache reuse is an evaluation convenience,
not a claim of independent repeated samples or immutable model behavior.

Offline CI includes actual rendering of the checked-in prompt with the pinned
Promptfoo evaluator and a fake provider, plus cache reuse/bypass/error tests.
No live Jev requests are needed. The standard Nunjucks interpolation is
`{{candidate_json}}`; triple-brace Mustache syntax is unsupported here.
# Independent source-reference comparison

The [independent experiment protocol](independent-experiment.md) adds blinded
model annotation, complete family splits, six fixed prompt variants, separate
confirmation and offline report scoring. The [recorded run](runs/2026-10-05-independent-reference/README.md)
made 92 fresh Jev requests. No improvement over baseline was demonstrated;
references are model annotations, not human-approved gold. This does not change
the original source corpus hypotheses or authorize automatic exclusions.

The follow-up [context ablation](runs/2026-10-05-context-ablation/README.md)
holds the prompt fixed and compares code, source task evidence and structural
implementation facts on eight diagnostic examples, with two fresh repeats.
It includes an explicit input correction and a separate static-filter view;
it is development evidence, not a new confirmation holdout.

The [SpecificationCore intent-profile ablation](runs/2026-10-05-intent-profile-ablation/README.md)
tests a different context factor: the same eight cases with and without a
versioned description of the project's global architecture goal. The prompt and
code state otherwise remain fixed. The result supports adding project intent as
an explicit classifier input on these examples, but inherited pre-profile labels
are not gold for the new goal.

## RustJev / proxy diagnostic evaluation

The [recorded RustJev / CoreInfra run](runs/2026-10-08-rustjev-coreinfra/README.md)
uses the frozen eight-case independent intent-profile model reference. Sixteen
single-question calls passed transport/core validation, but opportunity agreement
was 4/8 and eligible recall 0/3. Historical profile agreement was 7/8; provider,
question grouping, serialization and date differ, so the cause remains unproven.
The separate git-pinned `rust-driver` and `score_rustjev.py` preserve reproducible
inputs and offline scoring. No production classifier, registry disposition, S/U
count or confidence threshold was changed.

## Paired question grouping

The [native paired comparison](runs/2026-10-08-question-grouping-persistent/README.md)
held transport, endpoint, explicit model, canonical state and prompts fixed.
Joint and separate questions agreed on all labels: both scored 4/8 opportunity
and 7/8 concern-kind agreement. Joint requests used 44.6% fewer reported tokens
but numeric probability/confidence differences remain. Three operationally
stopped attempts are preserved separately. This diagnostic is not a RustJev
batch feature or a basis for autonomous exclusion.

## State key order and cumulative insights

The [exact-wire key-order comparison](runs/2026-10-09-state-key-order/README.md)
kept JSON semantics fixed but observed one changed opportunity label. Historical
insertion order scored 3/8 versus canonical 4/8; neither recovered earlier 7/8.
One response per arm cannot isolate ordering from baseline model variability.
All findings and their limits are collected in the [insight ledger](insights.md).
The frozen plan, receipts and report are validated offline in CI.

## Same-byte repeat controls

[Two fresh repeat rounds](runs/2026-10-09-repeat-controls/README.md) completed
32 requests. Labels stayed unchanged both across identical wires and key-order
arms, while probability/confidence varied. The earlier label flip did not
reproduce; opportunity agreement remains 4/8 and eligible recall 0/3.
`score_repeat_controls.py` reproduces the comparisons without inference.

## Eligibility diagnosis and brainstorm

[Three Astra Medium brainstorms](runs/2026-10-09-eligibility-diagnosis/README.md)
identify a verified task-phrasing difference between Jev and its model reference,
a mixed-function decision-boundary problem, and untested ownership/provider
hypotheses. Three fresh `gpt-6-astra` agents generated these hypotheses; no new
Jev inference or provider calls were made for this diagnosis. The report separates verified facts from
possible causes and proposes matched-task evaluation before prompt tuning.

## Matched-rubric comparison

The [aligned-rubric diagnostic](runs/2026-10-10-rubric-alignment/README.md)
used a fresh isolated reference agent and 32 paired Jev requests. Both repeats
improved eligible recall from 0/3 to 2/3 and concern-kind agreement to 8/8,
but owned false positives increased from one to two. The preregistered full
success criterion failed. Production prompts and metrics remain unchanged.

## Source-bound construction gate

The [offline composition replay](runs/2026-10-10-ownership-gate/README.md)
checks pinned source and resolved constructor imports before semantic routing.
It excludes two existing constructions, raising aligned opportunity agreement
from 5/8 to 7/8 without new inference. Six unknown sites retain recorded answers.
An actual Rust scanner audit also exposes different evaluation/discovery units
and missing outer `FirstMatch.with_fallback` recognition. This is bounded
diagnostic evidence, not a change to production ownership or S/U.

## Explicit target alignment

The [failure-learning cycle](failure-learning.md) records failures, confirmed
causes versus hypotheses, prevention patches and regression evidence. Local
[agent instructions](AGENTS.md) require closing this loop without rewriting
frozen failures or inferring a provider's internal reasoning.

The [real SpecGraph context packet](runs/2026-10-13-context-evidence-preparation/README.md)
contains six pinned production expressions in three evidence views each. All
18 labels remain blank pending independent annotation. Context amount is an
intervention, not an automatic gold label. Preparation and Git-source checking
were offline; no new Jev/Luna calls or metric writes were made.

The [eight-case Rust export](runs/2026-10-10-decision-targets/README.md)
binds one explicitly selected expression per development case to exact source
bytes. Four targets match legacy scanner anchors; four have no such candidate.
No old semantic labels were copied and no inference ran. The next comparison
needs fresh target-specific annotations and bounded helper/data context.

## CoreInfra TLS retry protocol

The [new transport protocol](coreinfra-retry-protocol.md) provides bounded
TLS-only retries, identical request bytes, a durable attempt ledger and an
explicit worst-case attempt budget. `coreinfra_retry_run.py` is offline by
default and keeps all responses unscored until provider-specific validation.
Existing experiments retain their original zero-inference-retry protocols.
The [matched expression comparison](runs/2026-10-12-matched-expression-wires/README.md)
has since completed under this transport; the
[contrastive study](runs/2026-10-13-contrastive-native-wires/results.md) stopped
partially on native response validation. Transport completion and semantic
quality remain separate.

## Expression reference preparation

The [new eight-expression packet](runs/2026-10-12-expression-reference/README.md)
adds explicit source-bound helper/data context and a rubric for exact expressions.
It contains the unlabelled preparation template, separate non-blind author
proposals, a fresh isolated model reference and a draft Jev/Luna comparison
protocol. The reference agrees with author proposals on both axes for all eight
cases; this is annotator agreement, not provider accuracy or human gold.
No historical labels were transferred and the preparation made no Jev/Luna
calls. A subsequent [native smoke](runs/2026-10-12-coreinfra-luna-contract-smoke/README.md)
verified the Luna operation/schema; strict Choice decoding and live comparisons
are recorded separately below.

### Matched expression provider comparison

[The frozen wire plan](runs/2026-10-12-matched-expression-wires/README.md) now
provides identical state/rubric inputs for Jev and Luna, with strict native Choice
decoding. Preparation and validation were offline; the subsequent explicit live
execution is recorded separately. Wire validation alone implies no classifier
quality score or S/U change.

The [first live matched comparison](runs/2026-10-12-matched-expression-wires/README.md)
completed 32/32 native-valid responses in 61.52 seconds. Both providers achieved
5/8 opportunity agreement and 2/3 eligible recall per repeat, failing the frozen
criterion. This is model-reference development evidence; raw results are preserved
and no S/U writes or production changes were made.

### Contrastive mechanics / policy diagnostic

[Four authored pairs and four withheld controls](runs/2026-10-13-contrastive-native-wires/results.md)
were frozen after fresh independent annotation. Live execution stopped at 42/48
requests because Jev returned a probability sum of 0.99: 41 native-valid answers,
one invalid, six unattempted, no retries or ambiguity. In the complete first
repeat, H1 role distinction is 4/4 for Jev and 3/4 for Luna; H2 joint abstention is
1/4 and 3/4; both meet directional H3 at 4/4. Whole two-repeat reliability is not
demonstrated. Per-axis abstention, context sensitivity, native response validity
and selected-label correctness are separate findings; no automatic S/U changes.

The [v2 runner](contrastive-mass-warning-v2.md) now accepts Jev 3/4-option Choice
mass totals from 0.99 through 1.01 with an explicit warning, preserving raw
probabilities and native confidence. Rejected answers remain unavailable without
ending the schedule; identity/transport failures still stop it. H3 includes Jev
precision sensitivity, while execution completion and usable coverage are
separate. The historical v1 study is unchanged.

The subsequently authorized [v2 live run](runs/2026-10-13-contrastive-warning-v2/results.md)
completed 48/48 accepted responses in 83.80 seconds, without warnings, retries or
ambiguity. Jev meets H1 at 4/4 pairs in both repeats, Luna at 3/4; both fail joint
withheld-context H2 and meet H3. All 16 withheld opportunity answers are
`needs_review`; the remaining gap is concern-kind abstention. Jev has one
withheld repeat label change; Luna's repeated answers match exactly. These are
development-set/model-reference findings, not production accuracy or S/U changes.

### Real-source context reference diagnostics

The [balanced context-reference round](runs/2026-10-13-balanced-context-reference/README.md)
uses six exact SpecGraph expressions and three evidence views. Each fresh
annotator receives two cases per mode and one view of each target. The earlier
[mode-correlated round](runs/2026-10-13-context-evidence-preparation/annotation-review.md)
is retained as diagnostic evidence. Raw annotations, context/annotator effects,
ownership evidence and semantic adjudication remain separate; this reference
preparation does not authorize Jev/Luna requests or S/U changes.

The [expression-fit v2 rubric proposal](expression-fit-rubric-v2.md) makes
decision-role evidence, policy/variant tie rules and missing-context treatment
explicit while preserving the label sets. A subsequent
[independent v2 reference](runs/2026-10-13-rubric-v2-reference/README.md)
matched on all 18 states in both fresh rounds, but decisive coverage fell to
10/18 per axis. The frozen H2 control failed on a BDD steps predicate that both
rounds marked `needs_review / unknown`. V2 is therefore not approved for
provider scoring; the rubric proposal and prior labels remain separate.

The [BDD steps source audit and balanced follow-up preparation](runs/2026-10-13-bdd-steps-balanced-factorial-preparation/README.md)
found the adopted values contract and existing SpecificationCore evaluation
paths in the pinned SpecGraph commit. Its four evidence conditions cover four
related decision sites; twelve fresh contexts each see all four conditions on
different sites, with three contexts per target-condition. The
[completed diagnostic](runs/2026-10-13-bdd-steps-balanced-factorial-results/analysis.md)
retains 48 annotations in twelve fresh contexts. Opportunity labels are
unanimous in all sixteen target-condition groups; responsibility labels have
one 2–1 split. The earlier [single-target draft](runs/2026-10-13-bdd-steps-factorial-preparation/README.md)
is preserved as superseded after review identified an annotator-condition
confound.

An [integrator adjudication](runs/2026-10-13-bdd-step-item-adjudication/README.md)
recommends `excluded / unknown` for the disputed step-item predicate with
Specification linkage and no validity contract. The existing rubric already
separates ownership from responsibility: the evaluation path establishes
existing representation, while the meaning of `step.valid` remains absent.
The review is advisory and not blind or human gold. Raw labels and agreement
counts remain unchanged; v2 is still not approved for provider scoring.

The [definition and owner-name follow-up](runs/2026-10-13-definition-owner-names-preparation/README.md)
froze sixteen fresh contexts and 64 blank annotations before dispatch. The
source audit resolves `TextInput.valid` to a nonblank-string check with original
text preserved. Its domain purpose remains a separate question. Four independent
helper families cross additional context with partial owner-name rewriting;
the explicit newline append is a local-role control. Preparation itself performs
no annotation or provider request.

The [completed definition/owner-name diagnostic](runs/2026-10-13-definition-owner-names-results/analysis.md)
preserves all 64 raw annotations from sixteen fresh contexts, with no rejected
attempts. Each target has identical labels across four conditions and four
repetitions per condition. The focal result is `excluded / policy`; gate priority
is `eligible / policy`, manifest paths remain `needs_review / unknown`, and
newline formatting is `excluded / mechanics`. All four prospective criteria are
met, with the definition criterion reviewed separately by the integrator.
Agreement is not semantic correctness, a scoring reference, or a production
metric update. Replay with `python3 validate_definition_owner_annotations.py`.

The [four-layer contract/consumer preparation](manifest-contract-factorial-plan.md)
freezes source-selection catalogs and balanced v2 packets: twelve fresh contexts
with four distinct targets each (48 case annotations), crossing documentary
requirements with consumers. Each context sees all four modes on different
targets; the unexecuted single-target v1 is preserved as superseded. Offline gates preserve the exact
whole expression, additive factors, repeated task identities, document/code
quotes and attempt receipts. The [handoff runbook](manifest-contract-factorial-runbook.md)
provides scoped delivery folders, actual-file preflight checks and genuinely
blank manual-review records.
Preparation is not dispatch, an evaluated reference or a production metric update.

The [scope-binding diagnostic v3 preparation](scope-binding-diagnostic-plan.md)
separates shared-definition and selected-application judgments while keeping
source code, consumers and binding facts fixed. Its 12 four-case packets plan
48 annotations, with source-pinned AST anchors and offline CI replay. Templates
remain blank; dispatch readiness is explicitly false until scope-aware actual-file
handoff and retained-attempt validation are implemented. No metric or gold changes.

The active scope-input contract is now v3.1 (`prepare_scope_binding_v3_1.py`):
the permitted-input list explicitly includes `evaluation_scope`, and blank rows
carry structured scope acknowledgments. Frozen v3.0 is preserved as superseded
before annotation; no historical output is relabelled.

The [scope-v3.1 handoff and retained-attempt runbook](scope-binding-handoff-runbook.md)
provides actual-file preflight, implementation/preparation bindings and explicit
returned scope acknowledgments. Formal validation leaves semantic scope fidelity
unverified; three 48-row manual-review groups remain blank. Historical preparation
flags are unchanged, and materialization does not dispatch annotation contexts.

The [completed balanced-v2 Astra High annotation package](runs/2026-10-14-manifest-contract-balanced-results-astra-high/README.md)
retains 48 annotations from twelve fresh contexts with no formal failures or
replacements. For the focal manifest predicate, document-present cells agree on
`eligible / policy`; the consumer-only cell has two `excluded / mechanics` and
one `needs_review / unknown`. The three controls have stable labels across all
four cells. Exact raw answers, delivery bytes, 60 proposed nonblind review entries
and receipt hashes are retained; agreement and formal replay do not establish
semantic correctness or human gold. See its replay guide for the original-path
actual-file validation boundary.

A [post-run consumer-only disagreement analysis](runs/2026-10-14-manifest-consumer-disagreement-analysis/README.md)
separates observed I/O uses from inferred primary responsibility, records the
shared-definition/application ambiguity and proposes a separately versioned
scope-binding diagnostic. The conservative integrator preference remains
review-pending, not a replacement for raw labels or human adjudication; no new
inference, scoring rule or metric change is introduced.

The [completed scope-binding v3.1 diagnostic](runs/2026-10-14-scope-binding-v3-1-results-astra-high/analysis/report.md)
retains 48 raw annotations in twelve fresh Astra/high contexts, with no formal
failures or replacements. The manifest application with documents received three
`eligible / policy` answers; the shared definition with the same documents retained
a 1–2 split against `needs_review / unknown`. All sixteen per-target/cell histograms
and both axes are retained. Proposed nonblind review leaves six role-witness
judgments pending; agreement does not establish correctness or a scoring reference.
The [parent audit](runs/2026-10-14-scope-binding-parent-audit/README.md) separately
checks raw/review bindings and records why comparison with v2 is descriptive only.
No direct Jev/Luna API calls or production S/U changes were made.

The [scope-binding adjudication table](scope-binding-adjudication-v1.md) proposes
two explicit decisions for human review: retain uncertainty for the shared path
contract, and distinguish an already-owned domain predicate from its findings
collection caller. The human confirmed D1/D2 on 2026-10-14; the
[bounded adjudication record](runs/2026-10-14-scope-binding-adjudication-v1/README.md)
binds those decisions to exact cases/tasks. Provider-scoring reference application
remains pending and frozen annotations are unchanged. The table also records the PR #60 context-identity provenance finding;
unique receipt strings do not by themselves establish isolated contexts.

The [dispatch provenance repair](runs/2026-10-14-scope-dispatch-provenance-repair-v1/README.md)
binds twelve actual returned task names to distinct child-session UUIDs and exact
writer/output associations. The [replacement retention runbook](scope-dispatch-provenance-runbook.md)
uses captured tool results instead of slot-derived identities. Encrypted task
delivery can be correlated, but plaintext prompt equality, runtime model identity
and filesystem isolation remain unverified. Frozen historical artifacts are unchanged.

The historical [remaining manifest-application analysis](runs/2026-10-15-manifest-application-without-documents-analysis/README.md)
proposes `needs_review / unknown` for target-01/cell03. Its code establishes path
validation and adapter uses but leaves the primary artifact-reference contract
ambiguous. This is not a rule that documentation is mandatory: code-only gate
precedence provides a contrasting role witness. At that snapshot the proposed D3 decision was unconfirmed; see the subsequent
human clarification below for the current architecture action.

The historical [16-task reference-readiness matrix](runs/2026-10-15-scope-reference-readiness-v1/README.md)
separates seven human-confirmed tasks (five decisive pairs and two abstentions),
one proposed D3 task and eight unconfirmed controls. Original three-response
histograms remain distinct from decision authority. It lists a three-item
confirmation packet and retained provenance limits; no scoring reference is frozen
or activated by this inventory, and no new inference ran.

Start with [four concrete code examples](scope-reference-code-examples.md) when
reviewing those labels: the actual path helper and callers, gate/refinement
precedence, YAML newline formatting, and the already-owned BDD predicate. Each
example identifies the exact selected expression, its architectural question and
the current decision status; snippets link to pinned SpecGraph source.

The [2026-10-15 human clarification / adjudication v2](runs/2026-10-15-scope-binding-adjudication-v2/README.md)
records all four corrections: inspect intent/proposal/spec documents and prefer
formalization if path design remains ambiguous; gate precedence is a Specification
candidate; formatter/linter rule sets own formatting; recognized Specifications
remain Specifications under simple NOT/AND/OR without mandatory wrapper classes.
Gate/newline are now human-confirmed family decisions, with integrator mappings
to the four frozen views each. BDD ownership is reaffirmed. The composition
complexity limit is not yet defined. The earlier D3 abstention is retained as
historical evidence-role analysis, not the only architecture action.

Pinned proposal 0215 explicitly requires fail-closed path traversal. This supports
the documented manifest application, while shared-helper primary role and old
no-document task inputs remain distinct. The new record pins source digests,
prior presentation and all16 task identities. It changes current guidance;
it does not retrofit a new rubric or gold label into old tasks. Future evaluation
must version architectural action separately from concern kind and evidence
confidence. Frozen artifacts, production S/U and scoring remain unchanged; no
new inference ran.

The [intent-first evaluation contract v4](intent-first-evaluation-v4.md) now
separates `concern_kind`, ordinal `evidence_confidence` and `recommendation`.
It encodes the human preference to formalize ambiguous decisions after bounded
intent lookup, reuse simple Specification compositions, and leave formatting
with formatter/linter rule sets. The [four integrator examples](runs/2026-10-15-intent-first-v4-contract/README.md)
preserve pinned source/scope but use a new profile and task identities. Typed
validation and CI cover uncertainty/action separation, stale identities, source
quotes and document acknowledgments. These are development examples, not new
model answers or an unseen/scoring reference. There is no provider wire adapter,
dispatch, automatic old-label mapping or production S/U change.

**Current correction: [intent-first v4.1](runs/2026-10-15-intent-first-v4-1-contract/README.md).**
Independent Astra/high review found a reproducible consistency gap: v4 accepts
`keep_procedural / mechanics` even when role is `policy` or `unknown`. v4.1
requires `mechanics / supported` for this action and exports the strict
`{"annotations": [...]}` response envelope requested by GitHub review. It
clarifies `formalization_preference` as uncertain role support; supported domain
rules keep their confidence and use `domain_contract`. The frozen v4 executable
and examples remain historical; new tasks use v4.1 contract/task identities.
No example labels/actions, model outputs, provider scoring or production S/U changed.

The [native v4.1 handoff](intent-first-native-handoff.md) prepares eight bounded
Jev/Luna transport-smoke requests with three Choice questions: concern kind,
ordinal evidence support and action. Native provider confidence stays separate.
The [frozen wire package](runs/2026-10-15-intent-first-native-preparation-v1/README.md)
can be staged offline into a new execution directory for the existing transport;
real inference still requires explicit authorization and `--live`. The decoder
retains contradictions as observations and never fabricates a full rich Annotation.
No provider calls or semantic scoring ran during preparation.

The authorized [2026-10-15 native smoke](runs/2026-10-15-intent-first-native-smoke-v1/README.md)
has now completed: 8 HTTP/native-valid responses in 16.01 seconds, eight attempts,
no retries. Four returned tuples violate the frozen consistency contract; a
consistent BDD tuple separately misses existing Specification reuse. Raw outputs,
local ledger/receipt replay and an explicit facts-versus-hypotheses diagnosis are
retained. This verifies this bounded API integration, not semantic accuracy or
full v4.1 annotation quality; production S/U remains unchanged.

Next is the [conditional-action diagnostic](conditional-native-action.md): a
[frozen offline package](runs/2026-10-15-conditional-native-action-preparation-v1/README.md)
for 18 requests / at most 54 network attempts. It contrasts fresh unchanged
baseline wires with explicit role/support premises, plus a BDD-only source-derived
ownership witness. All arms retain three Choice questions. Report native shape,
raw tuple consistency, premise compliance, action violations against common
premises and BDD reuse separately. These are known development fixtures, not
independent classification gold; no new inference has run in preparation.

**Live selection: [source-bound v2](conditional-native-action-v2.md).** PR64 review
found that v1 checked a free method snippet without proving it belonged to
BDDPolicy. V2 pins contiguous source and binds the method to its declaring class;
the [active package](runs/2026-10-15-conditional-native-action-preparation-v2/README.md)
keeps the same 18/54 budget and H1/H2 criteria. Sixteen baseline/conditioned wires
are unchanged; two BDD witness wires gain verified source provenance. V1 is
retained unexecuted for replay, and superseded for live use.

The authorized [v2 live diagnostic](runs/2026-10-15-conditional-native-action-live-v2/README.md)
completed 18/18 HTTP/native-valid answers in 42.24 seconds with no retries.
Conditioning reduced action violations against common development premises from
2 to 1 for Jev and 1 to 0 for Luna, but both echoed only 3/4 assigned premises:
strict H1 is not supported. Luna selected BDD reuse only with the explicit
source-bound witness (H2 supported in one pair); Jev already selected reuse with
conditioning. Raw outputs, preregistered comparisons and offline evidence replay
are retained; no accuracy or production S/U claim follows.

## Local retrieval pilot

The [EmbeddingGemma 2 pilot](embeddinggemma-retrieval-pilot-v1.md) evaluates
local discovery of historical SpecGraph refactoring counterparts. It compares
BM25, dense 768d/256d and RRF hybrid rankings on the same frozen vectors. This is
a development retrieval test, with source provenance and offline replay; it does
not approve ownership evidence or modify production S/U. Results and runtime
limits are recorded in the [run report](runs/2026-10-15-embeddinggemma-retrieval-v1-attempt-3/README.md).

The [helper-context/bilingual follow-up](runs/2026-10-15-retrieval-helper-live-v1/README.md)
repairs the known missing-body retrieval case and evaluates 518 current-source
declarations with eight authored English/Russian query pairs. H1 is supported on
the known case; the original hybrid H2 fails. Dense768 reaches top-5 8/8 per
language. An isolated [fusion v2 replay](runs/2026-10-15-retrieval-fusion-replay-v2/README.md)
fixes discarded Unicode text and unsupported zero-score BM25 votes without new
inference. Use v2 for further fusion experiments; v1 remains frozen evidence.
