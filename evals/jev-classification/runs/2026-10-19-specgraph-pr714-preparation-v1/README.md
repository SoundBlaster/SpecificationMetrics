# Historical SpecGraph PR714: offline route preparation

Status: prepared only. Hosted requests: **0**. Inference is **not authorized**.
This is an operational packet/adapter preparation, not a new ablation or an
accuracy benchmark. The closed instruction/envelope investigation stays closed.

## Source and intent

[SpecGraph PR #714](https://github.com/0al-spec/SpecGraph/pull/714),
`Respect product namespaces and migrated IDs in child allocation`, merged tree
`3ad8836b9e14c501bdfb5aeec11bdfdd65974eea`.

The observed failure was reuse of an identity after migration from the core
namespace into the product namespace. The PR introduces a workspace ID policy;
candidate hints and locked reservations consider canonical identities, pending
children, active reservations, and both sides of migration aliases. It retains
the default core namespace and rejects malformed policy before execution/write.
These are source-described behaviors, not test results produced by this package.

The bounded context contains exact code/helpers/constants, operator guidance,
characterization test source, and the cited canonical `SG-SPEC-0015` scope.
That canonical spec explicitly excludes runtime implementation; its citation
does not establish ownership of this exact allocation rule. No dedicated
proposal document for this PR is supplied. PR metadata was observed during this
preparation, not authenticated as its merge-time body. Git fragments are from
the exact merge tree. No current working-tree source or later implementation
is used. Source excerpts retain their upstream Apache-2.0 license and attribution
in `SpecGraph.LICENSE` and `SpecGraph.NOTICE`.

## Four independently answerable targets

All spans are in `tools/supervisor.py` at the revision above:

| ID | Exact scope | Lines |
| --- | --- | --- |
| D01 | `next_sequential_spec_id` | 6313–6321 |
| D02 | Selection block in `reserve_child_materialization_spec_id` | 6417–6427 |
| D03 | Alias checks in `load_spec_id_policy` | 6273–6298 |
| D04 | `parse_namespaced_spec_id` | 6245–6249 |

Locking, directory creation, timestamps and persistence surrounding D02 are
context, not part of its selected decision. The full parent function is supplied
so its binding and effect boundary can be inspected. D04 includes the actual
regular expression; the classifier need not infer it. No entire supervisor file
is submitted. Future executions must use fresh contexts without previous answers.
The targets share a dependency family and are not independent population samples.

The author's provisional interpretations from the selection discussion are
deliberately absent from packets. No gold labels, model answers, accepted role
facts, ownership claims, checked tool rules or repository-wide absence claim are
included. Hypotheses about repeated allocation logic remain proposals requiring
comparison; no deduplication result or refactoring recommendation is accepted.
The four-axis rubric, semantic instructions and architecture profile are reused
byte-for-value from the pinned prior aligned packet. Earlier model outputs are
not reused for these decisions.

## Contents and bindings

- `source-inputs.json`: immutable source catalog and public PR metadata; full-file
  SHA-256/Git blob IDs, exact excerpt spans/digests, upstream license. A constant
  snapshot digest in the preparer independently anchors this catalog.
- `D01`–`D04.packet.json`: backend-neutral schema-v1 tasks with unchanged four
  Choice questions. Each is below the existing 64 KiB CLI input bound.
- `D01`–`D04.context.json`: existing routing contexts with `assessment=not_run`,
  `action=assess_role`, no checked claims and no required additional axes.
- `plan.json`: case identities, byte counts, rubric pin, no-inference authority
  and the proposed future run scope.
- `preparation-receipt.json`: exact generated file inventory/digests and preparer
  hash. These hashes establish local integrity, not signed provenance or truth.

The native default is the existing bridge profile `jev-coreinfra / jev-1.13.0`.
`context_for` can bind the same semantic packet to the existing ordinary profile
`luna-responses-coreinfra / gpt-6-luna`; no silent provider fallback is added.
The offline compatibility tests use both profiles and synthetic results. They
exercise retained proposals, conditional review preparation and incomplete
execution, and cannot claim how either provider will classify this PR.

## Verify without inference

From `evals/jev-classification`, using the repository environment:

```bash
../../.venv/bin/python -B prepare_specgraph_pr714_v1.py verify
../../.venv/bin/python -B -W error -m unittest -v test_specgraph_pr714_preparation_v1.py
../../.venv/bin/python -B prepare_specgraph_pr714_v1.py verify --repository /path/to/SpecGraph
../../.venv/bin/python -B prepare_specgraph_pr714_v1.py verify --binary "$SPECMETRICS_BIN"
```

The optional source check reads the fixed Git objects; it does not checkout,
execute SpecGraph or run its tests. The optional binary check calls only
`prepare-classification`, with the existing portable example config; it never
launches Codex or reads authentication. No repository checkout/network is needed
for standalone verification. Cargo CI exercises inventory/tamper regressions and
the actual CLI preparer. The current-SDK bridge CI entry point also composes the
two packet compatibility tests; no workflow permission change is needed.

### Preparation failure learning

The first local compatibility test incorrectly passed a decoded JSON dictionary
to Pydantic's strict Python-mode `model_validate`: JSON arrays for tuple fields
then produced `tuple_type` errors before bridge binding. The existing replay
uses `model_validate_json`, the correct JSON boundary. The harness now follows
that seam and reads the actual context file in its stale-binding regression.
This was a confirmed test-harness integration defect, not a packet/schema or
provider semantic failure; frozen packet bytes and prior consumers were unchanged.

## Next bounded step, separately authorized

Freeze a dedicated live dispatch contract for four first-stage batches (four
axes each), with at most one ordinary review per target when the existing router
selects it. Establish exact request bytes, current SDK/producer/config pins,
per-request and aggregate output/time/attempt limits, explicit TLS retry rules
and a durable dispatch lease before requesting authorization. This preparation
contains no live runner, lease, API key or provider receipt.

Report site-bound labels, routing traces, not-run/unresolved cases and observed
transport/usage separately. No accuracy percentage is available without an
independent reference. Do not invoke Sol, expand context, create Specifications,
change accepted facts/S/U, publish a PR comment, or modify historical experiments
as an implicit consequence of this package.
