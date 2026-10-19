# PR714 preparation v2: non-overlapping target context

Status: **prepared offline only**. This is the active preparation for the next
PR714 route pilot. No model requests or semantic results exist for this packet.
The [v1 preparation](../2026-10-19-specgraph-pr714-preparation-v1/README.md),
its producer, source snapshot, receipts, packets and tests remain unchanged.

## Confirmed cause and correction

[PR93 review](https://github.com/SoundBlaster/SpecificationMetrics/pull/93#discussion_r4314212455)
identified a structural context defect. V1 excluded dependencies only when their
text equaled the target. For D02/D03, a full enclosing function differed from
the selected subsection and therefore repeated the target's source coordinates
inside `dependency_context`. The baseline reproduces one overlapping parent for
each of those two decisions; D01/D04 have none. This is confirmed source overlap.
Its effect on provider answers or annotation quality has not been measured.

V2 subtracts the target's path/revision/absolute line interval from every source
dependency. It retains exact, separately addressed surroundings:

| Target | Before | Target (unchanged) | After |
| --- | --- | --- | --- |
| D02 | 6406–6416 | 6417–6427 | 6428–6439 |
| D03 | 6252–6272 | 6273–6298 | 6299 |

The new excerpts keep the same full-file digest/Git blob and get their own exact
span, symbol and excerpt digest. No ellipsis or placeholder is inserted into code.
Before + target + after reconstructs the original enclosing function byte-for-byte.
Thus the lock/inputs, alias setup and write/return context remain available while
the selected source interval appears only once in the packet's source fragments.
This correction does not change the existing rich-review wire representation,
which separately carries state and a citation fragment catalog.

D01/D04 packet bytes are unchanged. D02/D03 retain the exact selected source,
questions, semantic instructions, architecture profile, documents and tests;
only dependency context is segmented. Their evidence/context digests change, so
old task-bound receipts cannot silently substitute for these new evidence views.
There is no label, accepted fact, S/U or refactoring recommendation change.

## Verification and provenance

`prepare_specgraph_pr714_v2.py verify` first verifies frozen v1, then reconstructs
all v2 packets and contexts. The v2 receipt binds that parent receipt and the v2
producer, plus the exact generated inventory. It rejects any reintroduced target
overlap even after a caller refreshes capture hashes. All source bytes still
derive from SpecGraph PR714 merge tree
`3ad8836b9e14c501bdfb5aeec11bdfdd65974eea`; v1 retains the original public metadata,
source catalog and full-file hashes. This is local integrity, not signed trust.
Upstream license and attribution are copied into this bundle unchanged.

From `evals/jev-classification`, using the repository environment:

```bash
../../.venv/bin/python -B prepare_specgraph_pr714_v2.py verify
../../.venv/bin/python -B -W error -m unittest -v test_specgraph_pr714_preparation_v2.py
../../.venv/bin/python -B prepare_specgraph_pr714_v2.py verify --binary "$SPECMETRICS_BIN"
```

Regressions reproduce the preserved v1 overlap, check exact source reconstruction,
exercise interval subtraction (including partial/exact/foreign spans), reject
overlap after hash rebinding, and run the existing two SDK profile/routing tests
against v2 with synthetic labels and sockets blocked. Cargo also invokes the
actual offline CLI preparer for every v2 packet. Current-SDK CI composes the v1
and v2 bridge checks; no workflow change or inference permission is introduced.

The [v1 scope and future-run constraints](../2026-10-19-specgraph-pr714-preparation-v1/README.md)
remain applicable: four first-stage batches, at most four conditional ordinary
reviews, `assess_role` only, fresh contexts, no independent reference/accuracy
claim, and no live dispatch without a separately frozen/approved run contract.
Use **v2**, not v1, for that future dispatch preparation.
