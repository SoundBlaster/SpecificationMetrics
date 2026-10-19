# Final instruction-placement check — research closed

Completed 2026-10-19. User instruction: **«Сделай проверки ещё, но потом глубже
копать не хочу уже»**. This concludes the bounded investigation. No further
ablation, enlarged corpus, model call or CLI root-cause probe is scheduled.

The [protocol](../../final-instruction-placement-v1.md) and producer were committed
as `b490c0f`; the exact twelve requests were frozen in `f4a5164` before dispatch.
No producer, source task, scoring criterion or request was changed after freezing.

## Results

| Observation | Developer rules | User rules |
| --- | ---: | ---: |
| Valid responses | 6/6 | 6/6 |
| Matching Sol comparator axes | 24/24 | 24/24 |
| Complete-view agreement | 6/6 | 6/6 |
| Consistency violations | 0 | 0 |
| R01 existing Specification recognized | 2/2 | 2/2 |
| Reported input tokens | 46,426 | 46,426 |
| Reported output tokens | 888 | 849 |

Both repetitions have identical labels for every case/condition. R01 is
`policy / supported / existing_specification / unknown`; R02 is
`policy / supported / unknown / unknown`; R03 is
`mechanics / supported / unknown / unknown` in both arms.

The within-pair request difference is exactly one JSON value: the first input
message's role, `developer` versus `user`. That message contains the same canonical
classification instructions/criteria. The second user message holds the same
source state. The public Codex default template stays fixed in top-level
`instructions` in both arms. Provider, requested Luna/medium settings, strict
schema, limits, stateless execution and AB/BA schedule remain matched.

**The preregistered priority-associated ownership-abstention prediction was not
supported on these controls.** There was no observed role-placement effect on
labels. This does not prove that priority never matters or establish the cause
of the earlier CLI answer. The tested public envelope differs from the old
server-cached CLI template, and this is a small selected sample with an empirical
reference rather than independently established semantic truth.

## Integrity and checks

- **12 logical requests, 12 network attempts, 12 potentially billable POSTs**;
  zero TLS/semantic retries, zero ambiguous posts and zero new Sol calls.
- Run interval: `08:27:38.606481`–`08:28:36.846298 UTC`, about 58.24 seconds.
- Public Jev4Mellea SDK decodes captured response objects offline; the existing
  durable transport sends the actual frozen role-treatment bytes. The mock SDK
  replay wire is not represented as the request actually sent.
- Receipts bind producer closure, protocol, input/reference hashes, manifest,
  attempt ledger and captured response objects. HTTP headers and original JSON
  whitespace are not retained by the reused transport. Gross token counts are
  not monetary charges; no currency amount is fabricated.
- Current and historical SDK environments replay the same final comparison.
  Tests exercise the exact single-field difference, source preservation,
  preparation without network, rebind rejection, synthetic priority effects,
  single-use execution, capture tampering and this real captured run.
- No active credential value is present in the run files. No accepted facts,
  registry dispositions or metrics are changed; semantic accuracy is unavailable.

## Closed conclusion and delivery handoff

Across the public-envelope and role-placement studies, **24 controlled API
requests produced 96/96 comparator-matching labels** on the same three selected
controls. This is descriptive consistency, not a broad accuracy claim. The
public envelope clearly increased reported input tokens in the first study;
neither study reproduced the old CLI ownership abstention.

Retain that original CLI disagreement unchanged. Its exact cause stays unknown.
The API studies support continuing ordinary delivery with the current explicit
instruction/schema and formal-validation contracts. They do not require another
round of prompt tuning or a deeper investigation of Codex internals.

**Research status: closed at user request.** Further inference in this investigation
requires a new explicit user request. The next ordinary delivery task is review
and integration of the prepared PR stack, preserving classifier proposals as
separate from accepted facts.
