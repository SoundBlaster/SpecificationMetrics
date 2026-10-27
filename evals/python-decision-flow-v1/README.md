# Real Python decision-flow corpus v1

## Purpose and selection

This is a source-backed development corpus for the opt-in
`python-decision-flow-v1` diagnostic. **29 unmodified examples, five repositories,
19 families, zero synthetic cases.** It does not change S/U or authorize automatic
opportunity exclusions. The source repositories were only read.

Discovery searched local checkouts under `~/Development/GitHub` for `FirstMatch`
and `.decide(...)`, excluding Git metadata, virtual environments, build outputs,
worktrees and historical evaluation directories. A second search in Flask and
FastAPI selected ordinary assignment-to-condition structures. This is a bounded,
purposive sample, not an exhaustive repository survey or random sample.

The available SpecGraph checkout was on an older working branch. For SpecGraph,
use the existing pilot revision `59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe` from
its Git history. Other projects use the pinned local HEAD objects listed in
`corpus.json`; these are not claims about their latest upstream releases.

| Project | `.decide` examples | Structural analogues | Source role |
| --- | ---: | ---: | --- |
| SpecGraph | 7 | 0 | Application code, including prior refactorings |
| SpycificationCore | 14 | 0 | Library tests demonstrating sync/async and adapted decisions |
| cctally | 2 | 0 | Other API with a method also named `decide` |
| Flask | 0 | 3 | Ordinary lookup, condition and conditional reassignment |
| FastAPI | 0 | 3 | Authorization, introspection and regex routing |

All 23 syntactic `.decide` calls in the selected example files are included.
The six ordinary-code analogues have their own tier. They are not counted as
successful recognition of SpecificationCore dataflow. The 38 selected source
files include SpecGraph factory/import dependencies, not just the excerpts.

## Labels and provenance

Each case records project/revision (through its snapshot), path, original line
and byte-column anchor, exact excerpt and SHA-256, enclosing lexical scopes,
family, semantic consumption, expected bounded diagnostic and rationale.
Selected full-source bytes also have SHA-256 pins. The original license texts
are retained under `licenses/`; excerpts retain their upstream licenses.

The labels were committed as `6f164c4` **before** the first corpus replay.
They were authored from source and the written v1 support contract, not copied
from replay output. They remain **author-labeled, independent review pending**;
the author already knew the analyzer. This is contract-conformance evidence,
not an independent precision/recall benchmark.

There are two distinct questions:

1. `semantic_read`: what does the source do with the value? For example,
   `branch_reads_result_enum` records a genuine source-level branch dependency.
2. `expected`: what evidence can the declared bounded v1 diagnostic establish?
   A genuine dependency can correctly be `unresolved` for this profile.

`no_immediate_binding` means the call exists but contributes no binding row.
`outside_api` belongs only to ordinary-code controls. Neither is an analyzer
flow status or evidence of dead specifications. Families group sibling calls
from the same operation/test; the two cctally copies share a family. Do not
weight every example as an independent observation.

## Reproduce without executing source code

Use local Git clones containing the pinned commits; the runner never fetches,
imports, installs or executes the corpus projects. Mutable worktree contents
are ignored. It verifies the Git blobs and exact excerpts before writing run
artifacts. Output must be a **new directory**; an existing run is not overwritten.

```sh
.venv/bin/python -B evals/python-decision-flow-v1/replay.py \
  --repo specgraph=/path/to/SpecGraph \
  --repo spycification=/path/to/SpycificationCore \
  --repo cctally=/path/to/cctally \
  --repo flask=/path/to/flask \
  --repo fastapi=/path/to/fastapi
```

Omit `--binary` for provenance/excerpt verification only. To replay, append:

```sh
  --binary /path/to/specification-metrics \
  --output /path/to/new/external-build-artifacts/real-flow-run
```

The replay materializes full original blobs at their original relative paths,
with an explicit import root and application-role benchmark manifest. Marking
the selected library test files as application here is an intentional test
scope; it is not a production metric for those repositories. SpecGraph uses
`tools` as its import root, preserving the existing resolver contract.

Each snapshot retains `flow.json`, stderr and the scope manifest. The assessment
records binary/corpus hashes, source/scope digests, report hashes, case outcomes
and per-project totals. Report hashes bind a particular run (including its root
path); compare source/scope digests and outcomes across machines rather than
requiring identical report or platform-specific binary hashes.

Run the offline harness checks with:

```sh
.venv/bin/python -B -m unittest discover \
  -s evals/python-decision-flow-v1 -p 'test_*.py' -v
```

They test missing-call handling, application-ID joins, control-tier separation,
source/excerpt drift and path validation. They do not increase corpus size.
No provider calls or embeddings are needed. This local multi-repository replay
is not added as a CI dependency on the author's filesystem.

## First replay, 2026-10-22 UTC

Analyzer source: `60a063282b6fcb86b3ad308500480752c6a16760` (PR #100).
See [assessment.json](assessment.json) for the frozen assessment.

| Result | Count |
| --- | ---: |
| `.decide` calls inventoried | 23 |
| Immediate identifier bindings | 9 |
| `linked` | 1 |
| `unresolved` | 8 |
| `not_linked` | 0 |
| Calls outside immediate-binding inventory | 14 |
| Ordinary-code analogues, outside API | 6 |
| Agreement with author expectations | 29 / 29 |

The single accepted link is SpecGraph's `binding_error` at
`tools/traceability/publication.py:238`, read at `if binding_error` on line 246.
The two cctally calls remain unresolved; no Specification usage is inferred
from their name. Flask/FastAPI produce no `.decide` calls.

**29/29 is not 100% dataflow coverage.** Most checks exercise explicit refusal
or inventory boundaries. Only one accepted link is available. There are no
real `not_linked` examples here, and library test examples are not production
usage. Reassignment/deletion and annotation boundaries still rely on separate
synthetic regression tests, not evidence supplied by this corpus.

## What the real examples expose

SpecGraph, `tools/candidate_repair_loop.py:425–427`:

```python
            decision = _ACCEPTANCE_CRITERION_DECISION.decide(context)
            if decision.value == _AcceptanceCriterionDisposition.ADD_PLACEHOLDER:
                actions.append(_acceptance_criterion_action(context))
```

This source clearly reads a decision in a branch. It is nested in a loop, and
the comparison is against a named enum member. Both exceed v1's direct
function-body / primitive-literal subset. `unresolved` exposes missing support,
not missing Specification usage. A second real example at lines 530–532 shares
these limitations. Supporting their origins alone would still leave the enum
comparison unsupported; test the two capabilities separately.

Flask, `src/flask/app.py:927–932`:

```python
        propagate = self.config["PROPAGATE_EXCEPTIONS"]

        if propagate is None:
            propagate = self.testing or self.debug

        if propagate:
```

The second condition can read a replacement value. This is a useful real
control for future CFG work, but it is not a FirstMatch example and must not
inflate the current diagnostic's measured coverage.

Next: independently review the 19 families, then propose bounded support for
within-iteration block origins and statically verified enum comparisons using
the two unchanged SpecGraph examples. Keep this separate from U exclusion.

## Independent review, 2026-10-23 UTC

A fresh **gpt-6-astra / medium** subagent reviewed all 29 examples against a
source-only packet and the pre-clarification written contracts. It received no
author labels, semantic tags, rationales, family/tier labels, previous analyzer
results or conversation history, and was instructed not to access them. This
was an instructional boundary in a shared filesystem, not an OS sandbox; see
its recorded input-access statement.

See the [review report](reviews/astra-medium-2026-10-23/README.md), unchanged
independent labels and comparison. Categories agree **29/29**; flow statuses
agree **29/29**, with no disagreements to adjudicate. The reviewer identified
two documentation ambiguities: `assert` must be an explicit barrier, and
unsupported-scope identifier bindings must be distinguished from calls with
no binding row. Both are clarified in the flow contract; analyzer behavior and
the original corpus/assessment remain unchanged.

This is one independent model review of a small, purposive development sample.
It does not turn agreement into semantic coverage or population precision/recall.
Next: evaluate bounded support for the unchanged loop/enum SpecGraph examples.

## Loop/enum extension, 2026-10-23 UTC

The [separate extension report](extensions/loop-enum-2026-10-23/README.md)
records support for same-iteration loop origins and verified same-module enum
comparisons. On the unchanged source corpus, linked bindings increase from
1 to 3 and unresolved bindings decrease from 8 to 6. Original author/reviewer
labels and the first assessment remain frozen; extension expectations and
observations are recorded separately. This does not change raw S/U.

## Real negative search, 2026-10-25

A [bounded local/history search](searches/not-linked-2026-10-25/README.md)
inspected 42 historical SpecGraph call observations and checked five close
candidates with the analyzer. It confirmed **zero new real `not_linked`
examples**: one site linked and four remained unresolved. Search observations,
rejected-candidate explanations, frozen expectations and CLI evidence are kept
separate from this corpus; no old labels or corpus totals were changed.

## Synthetic invalidation contrasts, 2026-10-25

A [separate counterfactual dataset](counterfactuals/invalidation-v1/README.md)
reuses the three real linked controls and inserts an overwrite or deletion
before each original branch. All three unchanged controls stay linked; all six
explicitly synthetic variants become not linked with the expected invalidation
reason and stop anchor. These are controlled damaged programs, not newly found
real bugs. Original real-corpus counts and labels remain frozen; raw S/U and
analyzer behavior are unchanged.

## Synthetic preservation contrasts, 2026-10-26

A [separate preservation dataset](counterfactuals/preservation-v1/README.md)
adds 12 explicitly synthetic inert insertions to the same three real controls.
All 15 positive checks retain the selected link, while all nine previous
invalidation checks reproduce. The three real controls are shared across the
datasets, not new independent observations. Snapshot application IDs change
with source digests; explicit source-case correspondence preserves the pairing.
