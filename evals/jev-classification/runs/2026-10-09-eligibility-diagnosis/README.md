# Eligibility disagreements: three Astra brainstorms · 2026-10-09

## Scope and conclusion

Read-only diagnosis of sg-017, sg-019 and sg-033, following the
[repeat controls](../2026-10-09-repeat-controls/README.md). Three fresh
`gpt-6-astra` agents with `medium` reasoning received concise self-contained
briefs without conversation history. Their lanes were eligibility wording,
input/response mechanics, and reference/task validity. They saw the existing
results and reference labels: this was hypothesis generation, **not blind
annotation, independent gold, three correctness votes, or model evaluation**.
Agents did not edit files, use credentials, call Jev or delegate. Integration,
source verification and this document belong to the main agent.

**No new Jev calls or production changes were made.** The key finding is a
verified difference between the task phrasing supplied to Jev and to the model
reference. Whether that difference caused the low agreement remains untested.
The observed 4/8 agreement and 0/3 eligible recall remain valid *relative to that
reference*, but do not establish three objectively wrong Jev decisions.

## Evidence inventory

- [Exact requests](../2026-10-09-repeat-controls/round-1/plan.json): decode
  `wire_json`; IDs resolved using the frozen reference mapping.
- [Recorded responses](../2026-10-09-repeat-controls/round-1/responses.jsonl):
  numbers below are **round 1, canonical arm**, not selected best responses.
- [Reference task](../2026-10-05-intent-profile-reference/packet.json),
  [annotations](../2026-10-05-intent-profile-reference/annotations.json), and
  [mapping](../2026-10-05-intent-profile-reference/mapping.json).
- [Architecture profile](../../specificationcore-intent-profile-v2.json) and
  [classifier contract](../../../../docs/candidate-classification-contract.md).
- [Wire audit](wire-audit.json): offline reconstruction from the recorded study
  and checked-in provider serializer. All eight bodies are semantically equal
  to the current insertion arm, but none is byte-equal. This is reconstruction,
  not a captured historical HTTP body. Source digests are recorded.

## Confirmed task differences

| Topic | Jev Choice question | Independent reference task |
|---|---|---|
| Eligibility benefit | `named, reusable Specification` | `named, addressable, observable rule` |
| One use | Allowed in the architecture profile within state, not explicitly in the Choice criterion | Explicitly allowed in the direct decision instructions |
| Existing ownership | Exclusion includes a rule already owned by a Specification | Requires explicit evidence for the same decision; a library import alone is insufficient |
| Mechanics | Includes `technical enforcement` without qualification | `technical enforcement without a distinct product decision` |
| Local implementation | Exclusion includes `a local construct outside the opportunity definition` | Excludes coordination without a distinct product decision |

`Reusable` can mean *capable of reuse*, which is compatible with single use;
the wording difference is therefore an ambiguity, not a proven logical
contradiction. The profile already supplies the broader intent to Jev. The
hypothesis is that the short direct criteria dominate or are interpreted more
narrowly; we cannot infer that internal behavior from Choice probabilities.
Both tasks omit an explicit aggregation rule for a mixed function containing
mechanics and a policy. This weakens the sg-019 comparison independently of
model quality.

## Case analysis

| Case | Exact decision in the supplied source | Current answer | Reference and remaining uncertainty |
|---|---|---|---|
| sg-017 | Ready pre-SIB: no finding. Not ready without repair preview: review finding. Not ready with preview: warning. `_pre_sib_original_blocked` is an ordinary helper. | policy 0.90; excluded 0.56, eligible 0.27, needs_review 0.17; opportunity confidence 0.34 | eligible/policy. Recognition of policy succeeds; single-use suitability, target ownership and caller/helper identity remain possible sources of disagreement. |
| sg-019 | Within a 44-line repair function, `refs and all(ref in existing_ac for ref in refs)` decides whether an acceptance-criteria repair action is needed. | mechanics 0.86; excluded 0.96, eligible 0.02, needs_review 0.02; opportunity confidence 0.94 | eligible/policy. Reference selects an internal decision; Jev may classify the enclosing traversal/normalization/action-construction function. The unit of classification is unresolved. |
| sg-033 | Bind workspace identity, source ref, commit, two authorization flags and declaration digest to the requested bootstrap. | policy 0.84; excluded 0.74, eligible 0.18, needs_review 0.08; opportunity confidence 0.61 | eligible/policy. Recognition of authority policy succeeds. Whether this is a distinct decision or enforcement of a separately owned rule needs specific evidence; neighboring Specification imports do not establish ownership. |

The reference itself records missing ownership/owning-feature context for all
three. That does not prove its labels wrong, but prevents treating them as
unconditional human gold. Jev Choice supplies no semantic rationale, so the
hypotheses below are proposed explanations, not reported model reasoning.

### Historical source check performed by the main agent

Pinned source files for all three cases were read from local SpecGraph Git
objects and their SHA-256 values matched the corpus metadata:

- sg-017: `3ad8836b9e14c501bdfb5aeec11bdfdd65974eea`,
  `tools/idea_to_spec_promotion_gate.py`. The consumer sets `ready = not findings`
  at line 302 and returns promotion paths only when ready at line 324. Findings
  therefore affect readiness; severity alone is not the decisive mechanism.
  [Pinned source](https://github.com/0al-spec/SpecGraph/blob/3ad8836b9e14c501bdfb5aeec11bdfdd65974eea/tools/idea_to_spec_promotion_gate.py#L302).
  This weakens the hypothesis that the branch merely formats a display message.
  The consumer was **not in the original bounded request**, so this extra evidence
  does not retroactively improve that request or change its recorded score.
- sg-019: `99b69a9eda02f44b336f7460244abbe9016af18a`,
  `tools/candidate_repair_loop.py`, lines 335–378. The target condition is at
  lines 347–349. Source confirms the mixed function, not an approved opportunity
  aggregation rule.
- sg-033: `9b285a2e018331460c1a6bee46a697b24a26d3fb`,
  `tools/subject_publication.py`, lines 499–508. The source confirms the six-part
  binding; this check did not establish whole-project ownership or trace every
  allocation producer.

## Hypotheses and dispositions

These consolidate all distinct agent ideas. Ranking reflects direct local
evidence and ability to distinguish alternatives cheaply, not model votes.

| ID / priority | Hypothesis and source | Discriminating test | Evidence against / stopping condition |
|---|---|---|---|
| H1 / first | Single-use or local policy is excluded because `reusable` and `local construct` are interpreted narrowly. Raised in all three lanes; exact wording difference verified. | First align the task with the reference. A later word-only arm can replace only the reuse requirement while keeping state and all other text fixed. | Aligned task leaves policy cases excluded; word-only changes do not reproduce on controls. |
| H2 / first | Mechanics/enforcement overlaps domain policy because Jev's mechanics criterion lacks `without a distinct product decision`. Eligibility and input/reference lanes. | Use the same qualified mechanics definition in reference and candidate questions; then test authority/validation cases against pure parsing controls. | Qualification does not affect the disputed cases, or human adjudication calls the targeted condition purely representational. |
| H3 / first | sg-019 is classified at whole-function granularity; reference selects an internal predicate. All lanes. | After task alignment, mark the exact target condition while retaining the original function as supporting context. Use the same target for reference and Jev. | Predicate-only view remains mechanics/excluded; or adjudication rejects an independent domain decision there. |
| H4 / second | Imported FirstMatch or neighboring `*_SPEC` declarations are mistaken for ownership of this exact rule. Eligibility and reference lanes. | Require a concrete target-to-Specification relation. Separately remove only unrelated imports, preserving semantics; include proven-owned controls. | Labels remain unchanged, or static review establishes an actual owner for the target decision. |
| H5 / second | sg-017 is a presentation/coordination site; its helper owns the decision conceptually. Reference lane. | Show the minimal readiness consumer and explicitly identify caller versus helper as the candidate. Avoid counting one rule twice. | Historical consumer already weakens the display-only version. No formal Specification ownership was established by naming an ordinary helper. |
| H6 / second | sg-033 enforces a policy chosen by the allocation producer rather than introduces a distinct rule. Reference lane. | Inspect minimal producer/schema and exact binding owner, then adjudicate whether the verifier contains a distinct product invariant. | Evidence establishes this binding as its own decision; producer flags alone do not establish ownership of their conjunction. |
| H7 / separate transport slice | Direct TypeSafe and CoreInfra/date/backend differences contribute to historical 7/8 versus current 4/8. Input lane; route difference verified. | A simultaneous direct/proxy comparison of matched payloads with repeats and provider-specific credentials. | Matched routes agree; differences disappear under task alignment. Same returned model name alone cannot prove backend identity. |
| H8 / low | Full envelope/question/criterion ordering matters beyond state order. Input lane; format difference verified offline. | Compare the complete reconstructed historical format with current format, keeping endpoint and semantic body fixed. | No reproducible categorical effect beyond same-byte variability. Earlier state-order controls do not resolve this broader factor. |
| H9 / low | Category names dominate descriptions or invert the intended opportunity meaning. Input lane. | Neutral A/B/C labels with an explicit frozen reverse mapping; or separate suitability and ownership diagnostic questions. | Neutral names preserve decisions; parser inspection shows no polarity inversion. These arms change the task interface and are not automatic production replacements. |
| H10 / prerequisite | Reference judgments embody a different task or choose different decision boundaries. Reference lane; direct task mismatch confirmed. | Same instructions, target span and visible facts for both annotator and Jev; human adjudication for material disagreements. | Agreement remains poor under a genuinely matched task with adjudicated targets. More model votes alone cannot resolve this prerequisite. |

The parser is a low-priority explanation: inspected code preserves provider
`choice`, validates labels/argmax, and does not apply a confidence threshold in
these runs. No evidence of a reversed label mapping was found. This inspection
is narrower than a proof that every adapter path is bug-free.

## Proposed next experiment: align the task before tuning

**Purpose:** determine whether agreement changes when both sides are given the
same architectural question. This tests a task-alignment intervention; changing
several rubric clauses together cannot identify which word caused a change.
It is not a benchmark improvement claim and needs no production change.

1. Freeze one concise task contract: the supplied site is the target; for a
   mixed site, eligibility asks whether it contains a distinct product decision,
   not whether every statement is a rule. Supporting code is evidence, not a
   separate candidate. A stable product rule qualifies with one use; technical mechanics means no
   distinct product decision; existing ownership requires evidence for the
   **same** rule. Known ownership remains a formal filter, not an LLM authority.
2. Re-annotate identical bounded inputs using exactly those instructions. Keep
   the old annotations immutable. Cases with unresolved unit/ownership questions
   remain explicitly unresolved rather than silently relabeled to match Jev.
3. Compare current versus aligned Choice wording on the frozen eight cases,
   with all model, endpoint, serialization and state bytes held fixed. Two
   repeats give **32 requests**; do not run this automatically from this report.
4. Keep the existing owned controls sg-018/020 and mechanics controls
   sg-031/032/034. Report eligible recall and per-case changes separately from
   owned/mechanics false positives; a blanket shift to eligible is not success.
5. If policy cases improve without control regressions in both repeats, the
   alignment hypothesis gains diagnostic support. If errors persist, inspect
   target granularity and ownership evidence before further wording changes.
   Any promising variant still needs an adjudicated, new-family confirmation
   set; the eight development cases cannot establish generalization.

Suggested concise opportunity instructions for review, not an installed prompt:

> Classify the supplied target site under the architecture intent. A mixed
> site can qualify when it contains a distinct product decision; supporting code
> is evidence, not a separate candidate. A stable product/domain rule can qualify with one use; procedural syntax or
> local scope alone does not exclude it. Choose eligible when it would benefit
> from a named, addressable, observable Specification. Choose excluded for
> technical mechanics without a distinct product decision, or explicit evidence
> that a Specification already owns this same decision. A library import or an
> ordinary helper name alone is not ownership. Choose needs_review when material
> ambiguity prevents a reliable judgment; do not invent missing context.

Use matching label descriptions and the same qualified mechanics criterion for
both reference and Jev. Do not introduce per-case answers, findings from this
analysis or historical before/after labels into the shared input. Any newly
added consumer or target span belongs to a separately versioned context study.
