# Jev, Luna Decision and ordinary Luna: consolidated observations

Date: 2026-10-18. This is a post-run synthesis, not a new experiment or a
production qualification. Sources remain frozen and are linked below.

## Quality, timing, cost and repeatability

The comparison uses the same four SpecGraph targets, two evidence views per
target, four category questions per view, and aligned semantic guidance.
Sol 6.1 Medium supplies the unchanged eight-view comparator from 24 annotations.
Those annotations are unanimous within each view; they are not human gold.

| Measure | Jev 1.13.0, native | Luna Decision, native | Ordinary Luna, Responses / low |
| --- | ---: | ---: | ---: |
| Agreement across four axes | 31/32 | 18/32 | 32/32 |
| Role + ownership agreement | 16/16 | 9/16 | 16/16 |
| Coherent answer tuples | 7/8 | 6/8 | 8/8 |
| Role unresolved | 0/8 | 5/8 | 0/8 |
| Valid responses | 8/8 | 8/8 | 8/8 |
| Observed retries | 0 | 0 | 0 |
| Sum of eight call timings | 12.514 s | 14.505 s | 34.423 s |
| Median call timing | 1.522 s | 1.519 s | 4.065 s |
| Reported input tokens | 39,693 | 34,571 | 35,167 |
| Reported output tokens | 1,359 | 0 | 874 |
| Money attributable to this cohort | Unknown | Unknown | Unknown |
| Same-condition repeatability | Not established | Not established | Not established |

Native timings cover HTTP transport; ordinary timings include SDK construction,
generation, validation and closure. These sequential historical runs are not
a controlled latency trial. Instruction-parity repeats changed the native
instructions and therefore do not establish same-condition repeatability.
All models share development examples: no held-out accuracy or general ranking
follows. Unknown ownership/tool agreement does not prove positive discovery.
Native Luna's zero reported output is retained despite valid choice responses.

Evidence:

- [Native instruction-parity run](runs/2026-10-18-semantic-instruction-parity-live-v1/README.md)
  and [per-view comparison](runs/2026-10-18-semantic-instruction-parity-live-v1/comparison.json).
- [Ordinary-Luna run](runs/2026-10-18-ordinary-luna-live-v1/README.md)
  and [per-view comparison](runs/2026-10-18-ordinary-luna-live-v1/comparison.json).
- [Sol repeatability run](runs/2026-10-18-sol61-medium-repeatability-v1/README.md).

## Cache accounting and the user's billing observation

The user's CoreInfra dashboard screenshot shows small GPT-6 Luna charges on the
displayed interval. It supports low observed spend, but does not isolate the
eight requests or establish a comparable per-candidate price for all providers.
No account screenshot or credential is committed here.

The eight saved ordinary Responses bodies expose this exact decomposition:

| API usage category | Tokens |
| --- | ---: |
| Input minus cache reads and writes | 24 |
| `input_tokens_details.cache_write_tokens` | 19,463 |
| `input_tokens_details.cached_tokens` | 15,680 |
| `input_tokens` total | 35,167 |
| `output_tokens` | 874 |
| Reasoning tokens, already included in output | 570 |

For every response, total input minus both cache buckets equals three. The
user's SQL report contains eight rows with input three and the exact eight
output counts. This establishes an arithmetic reconciliation for these saved
responses; it does not establish universal analytics/billing semantics. Do not
interpret three as the whole prompt, or count reasoning twice. Raw usage is
preserved in `sdk_response_base64` in the ordinary run's `responses.jsonl`.

Obtain request-attributable charges or documented bucket rates before quoting
money per candidate. With confirmed per-million rates, the ordinary cohort
estimate would be `(24 * input_rate + 19463 * cache_write_rate +
15680 * cache_read_rate + 874 * output_rate) / 1000000`, labeled as an estimate
and kept separate from billed amounts. Unknown monetary values remain null,
not zero. Record currency, rate date and billing scope alongside any amount.

## What this supports next

Use Jev as the provisional first semantic classifier and ordinary Luna as the
bounded reviewer of unresolved cases. Keep native Luna Decision selectable,
but this cohort does not support preferring it as the default first stage.
The [review cascade contract](../../docs/semantic-review-cascade-v1.md) defines
the escalation boundary and leaves final ambiguity visible in PR review.

An offline selection illustrates the intended route: seven Jev tuples are
coherent with known roles and supported evidence. R04/baseline alone has
`policy / insufficient`; the existing role/support rule flags it. Its saved
ordinary-Luna tuple is `policy / supported`, with the other axes unchanged.
Selecting the saved Luna tuple for that one view yields 32/32 comparator
agreement with one selected escalation among eight views. This is retrospective
label selection, not a live cascade result, a measured cost saving, or a test of
source-citation validation. Luna was originally called on all eight views.

This also shows a limitation: native Luna Decision has five coherent abstentions
and two contradictory tuples, so the basic role/support routing rule would
select seven of eight views for review. The remaining coherent result can still
miss ownership. Required-axis checks and a held-out audit must cover those gaps;
consistency alone does not prove semantic correctness.

Next deliverable: an offline cascade evaluator using the versioned routing
rules, saved-response replay and synthetic failure cases. Evaluate a larger
independently labeled cohort before production qualification; keep model
suggestions separate from accepted facts and S/U.
