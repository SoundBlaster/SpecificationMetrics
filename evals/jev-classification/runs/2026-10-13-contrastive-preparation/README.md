# Contrastive mechanics / policy preparation — 2026-10-13

## Status and question

**Independent model annotation and integrator review completed. Executable native
wires are now [frozen separately](../2026-10-13-contrastive-native-wires/README.md).
The [subsequent live run](../2026-10-13-contrastive-native-wires/results.md)
stopped after 42/48 requests on a native-contract failure; its partial scores are
separate from this preparation and annotation record.**

The fresh subagent's labels agree with author hypotheses on 12/12 cases on each
axis. [Reference review](reference-review.md) preserves all uncertainties and
records the limited isolation scope. Agreement is not provider accuracy or human
gold. The original plan, blank template and preparation receipt are historical
pre-annotation snapshots; current reference readiness is recorded in
[reference-review.json](reference-review.json).

The preceding [matched study](../2026-10-12-matched-expression-wires/README.md)
left a common disagreement: a membership/all expression was excluded as
mechanics although its effect suppresses a domain repair. This diagnostic asks
whether Jev and Luna distinguish **the role of an identical computation** from
the computation's syntax, under the same SpecificationCore architecture profile.

Four expression shapes come from pinned SpecGraph history. Their surrounding
functions and scenario contracts are newly authored counterfactuals. These are
eight authored full-context examples plus four context-withheld controls, **not
twelve newly discovered production sites**. Historical source is provenance,
not canonical approval of the new scenario or its proposed label.

## The four pairs

Each row has two full-context members with **identical expression bytes**.
`mechanics / excluded` and `policy / eligible` below were the author hypotheses;
the fresh independent annotation retains them. No labels were transferred from
earlier runs.

| Pair | Shared target | Proposed mechanical role | Proposed domain role |
|---|---|---|---|
| 01 | `items and all(item in known for item in items)` | Choose a direct lookup rendering path; fallback produces the same tuple while preserving unknown tokens | Skip or propose an acceptance-criterion repair placeholder |
| 02 | `not ready and mode != "preview"` | Avoid repeated CRLF normalization and preserve the requested text representation | Require promotion review when the report is not ready and repair preview was not used |
| 03 | Six field/flag conjuncts | Print an exact-match marker for a diagnostic row | Decide publish/hold from allocation bindings, two grants and declaration digest |
| 04 | `preferred or default` | Project a pre-escaped log chunk with its display placeholder | Select a requested review-task queue or the configured default queue |

Pair 03's target is:

```python
record["identity"] == expected["identity"] and record["ref"] == expected["ref"] and record["commit"] == expected["commit"] and record["flag_a"] is True and record["flag_b"] is True and record["digest"] == expected_digest
```

Example: pair 01's complete functions are:

```python
def materialize(items: list[str], known: dict[str, str]) -> tuple[str, ...]:
    if items and all(item in known for item in items):
        return tuple(known[item] for item in items)
    return tuple(known.get(item, item) for item in items)


def plan_repair(items: list[str], known: set[str]) -> tuple[str, ...]:
    if items and all(item in known for item in items):
        return ()
    return ("add_acceptance_criterion_placeholder",)
```

The first selects a rendering path. The second selects a repair instruction.
Empty `items` makes the original expression return `[]`; both functions consume
its truthiness. This preserves the previously diagnosed boundary. Resolving
criterion references does not establish semantic or complete requirement coverage.

[scenarios.json](scenarios.json) contains all eight complete functions and their
explicit input/effect contracts. [source-evidence.json](source-evidence.json)
contains four exact historical quotes, Git revisions, full-file/quote SHA-256
hashes and UTF-8 spans. Derivations are explicit: identifier renaming, prepared
facts and, for pair 02, inlining an early-return helper over those facts. No
equivalence of the complete historical application is claimed.

## The context-withheld control

Each pair also has **one** shared state containing its expression and the
unchanged profile, with no containing function, scenario contract or input/effect
meanings. Its proposed answer is `needs_review / unknown`, subject to independent
annotation. This tests handling of insufficient evidence.

Do not send the same withheld input twice and score it once as policy and once
as mechanics. There are four unique withheld states, not eight. Their labels
must be adjudicated separately; they do not inherit either full-context label.

## Experiment and criteria

The machine-readable [study plan](study-plan.json) fixes:

- **12 states × 2 providers × 2 repeats = 48 logical requests.** Both Choice axes
  are in each request. At most three attempts each: **144 attempts / potentially
  billable POSTs**, not a dollar estimate. Remaining credential balance is unknown.
- Requested Jev `jev-1.13.0` and Luna `gpt-6-luna` through the previously verified
  CoreInfra native routes. Both receive identical canonical state and rubric
  text; API envelopes differ. Native validators remain strict.
- Same architecture profile and question rubric as the preceding matched study;
  no prompt variant tuning in this experiment.
- Deterministic shuffled case orders, each case's provider order reversed on
  repeat two, and separate stateless requests. Pair members are not presented
  together as an instruction to produce different answers.

| Hypothesis | Passing criterion, per provider in each repeat | A failure means |
|---|---|---|
| H1: complete context supports correct role distinction | All **4/4 complete pairs** correct on both axes; 0/4 mechanical false positives and 4/4 policy recovery | This strong claim fails on these development cases |
| H2: missing meanings trigger uncertainty | All **4/4 withheld controls** return `needs_review / unknown` | Abstention under missing context is not reliable on these controls |
| H3: probabilities move in the intended direction | In at least **3/4 pairs**, both P(policy) and P(eligible) are strictly greater for the proposed policy member | This directional signal is not demonstrated; ties do not pass |

H1/H2/H3 and repeated-label stability are separate claims. Native option
probabilities are compared only **within a provider**. Confidence remains an
uncalibrated diagnostic; no fallback threshold is selected. Missing/invalid
responses retain planned denominators and prevent a completed-test claim.

Primary reporting uses complete pairs, full-context recall/false positives and
the four separate withheld controls. Avoid a single pooled 12-case accuracy that
hides opposite-role errors or rewards abstention as full-context success.

## Reference and execution sequence

1. **Completed:** gave only [case-packet.json](case-packet.json) and the blank
   [annotation template](annotation-template.json) to a fresh independent
   annotator, without previous labels, author proposals, mappings or provider
   results. The assignment required both axes, exact evidence quotes and
   uncertainty. The review records isolation scope and the possibility of
   noticing repeated expression shapes.
2. **Completed:** reviewed annotations before provider inference; no label
   disagreements or overrides, with seven uncertainty notes preserved. No corpus
   revision was required. For future revisions, a full pair without opposed roles
   or an answerable withheld control requires a new preparation/version and
   independent review. Do not force labels or quietly drop inconvenient cases.
3. **Completed in a separate run folder:** froze the reviewed reference and
   executable native request manifest, with exact
   state/question/decoder/producer/reference hashes. The existing
   [logical schedule](logical-schedule.json) is **not executable native wires**.
   This preparation script has no live mode and does not read credentials.
4. **Completed partial execution after explicit request:** sent 42/48 requests;
   stopped on one invalid probability distribution, without TLS retries or
   ambiguity. Six requests are proven unattempted. Ledgers/raw outputs/usage are
   preserved; any probe or rerun requires a separate recorded experiment.
5. **Completed offline partial scoring:** retained failed hypotheses and the
   original denominators. No production exclusions, registry dispositions or
   S/U updates. The whole two-repeat study is incomplete.

[author-proposals.json](author-proposals.json) is nonblind and deliberately
separate. [preparation-receipt.json](preparation-receipt.json) records the original
artifact/input/producer hashes, byte inventories and pre-annotation pending
status. [independent-annotations.json](independent-annotations.json) preserves the
raw annotation; the separate review records its current acceptance and limits.
Neither artifact establishes provider quality.

## Offline verification

From `evals/jev-classification`:

```sh
python3 prepare_contrastive_pairs.py
python3 prepare_contrastive_pairs.py --source-repo /path/to/SpecGraph
python3 -m unittest -v test_prepare_contrastive_pairs.py
python3 validate_contrastive_reference.py
python3 -m unittest -v test_validate_contrastive_reference.py
```

Default mode rebuilds in memory and checks saved artifacts; the optional Git
checkout verifies complete historical file hashes and exact quotes. CI checks
the authored expression spans, paired identity, withheld controls, blank
reference separation, fixed request/attempt denominators and producer digests
without requiring the historical SpecGraph checkout. `--write` creates new
preparation artifacts and refuses existing outputs. It never makes inference.

## Interpretation limits and next step

This is a deliberately constructed development diagnostic. Full-context members
differ in code names, input types, contracts and effects. Equal target bytes
control syntax; they do not identify which contextual component caused a model
answer. The withheld/full comparison tests a bounded context intervention, not
generalization, hidden model reasoning, calibrated confidence or superiority of
one provider. Four pairs and two repeats are not independent population samples.

The proposed eligible/policy and excluded/mechanics correlation is deliberate
here; it does not collapse those orthogonal axes in the general classifier.
Already-composed controls remain evidence from the previous study. Future
confirmation needs new natural-code families and human adjudication.

**Next step:** investigate the native probability contract as described in the
[partial live results](../2026-10-13-contrastive-native-wires/results.md), before
proposing a new version or further inference. Do not resume the original run or
revise its reference labels after results.
