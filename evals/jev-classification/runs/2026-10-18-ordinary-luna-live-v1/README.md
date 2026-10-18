# Ordinary Luna through Jev4Mellea 0.8.0

**Observed:** 2026-10-18 11:52:16.494–11:52:51.433 UTC, 34.939 seconds.
Eight planned tasks, eight successful Responses requests, eight HTTP dispatches,
no retries, failures, ambiguous posts or duplicate executions. Each request
jointly classified four named questions over one frozen SpecGraph evidence view.

## Agreement with the unchanged Sol comparator

| Measure | Native Jev | Native Luna Decision | Ordinary Luna Responses, low |
|---|---:|---:|---:|
| All four axes | 31/32 | 18/32 | **32/32** |
| Primary role + ownership | 16/16 | 9/16 | **16/16** |
| Role | 8/8 | 3/8 | **8/8** |
| Evidence support | 7/8 | 1/8 | **8/8** |
| Ownership | 8/8 | 6/8 | **8/8** |
| Tool responsibility | 8/8 | 8/8 | **8/8** |
| Coherent tuples | 7/8 | 6/8 | **8/8** |
| Consistency conflicts | 1 | 2 | **0** |
| Unknown primary role | 0/8 | 5/8 | **0/8** |
| Baseline, all axes | 15/16 | 8/16 | **16/16** |
| Retrieval, all axes | 16/16 | 10/16 | **16/16** |

Native counts come from the unchanged [instruction-parity run](../2026-10-18-semantic-instruction-parity-live-v1/README.md).
Its models were not called again. **No new Sol calls:** all comparisons reuse the
original 24 Sol 6.1 Medium annotations and their eight-view consensus. Top-line
SHA-256 is `3f25fe46df4537286501fa39552087020cf7a138dd44e2f1a9603354e6d54e3c`.

These are reference-agreement observations on four development targets, not
semantic accuracy, a representative model ranking or production acceptance.
Baseline already supports all judgments here; the result does not demonstrate
retrieval gain. Six unknown ownership judgments and eight unknown tool judgments
do not establish that no owner/tool exists.

## Operational observations

| Provider | Reported input tokens | Reported output tokens | Sum of eight call timings |
|---|---:|---:|---:|
| Native Jev | 39,693 | 1,359 | 12.514 s, HTTP transport |
| Native Luna Decision | 34,571 | 0 | 14.505 s, HTTP transport |
| Ordinary Luna Responses | **35,167** | **874** | **34.423 s, SDK client** |

Ordinary Luna's median client call was 4.065 s (range 3.008–6.361 s).
The raw Responses usage reports 570 reasoning tokens within the 874 output
tokens. Three responses report zero reasoning tokens; that is provider usage
metadata, not proof of the model's internal computation. All responses report
`gpt-6-luna` and completed status under the fixed 1,024-token budget.

The ordinary pipeline had greater observed latency. Native timers cover HTTP
transport; the ordinary timer includes SDK construction, generation, validation
and closure. Runs were sequential and historical/current, not simultaneous
latency trials. Tokenization/accounting and prices differ across providers;
monetary cost remains **unknown**. These counts do not prove ordinary Luna is
cheaper, even though it used fewer reported tokens than Jev in this sample.
Native Luna's zero output count is preserved despite its valid choice results.

## Contract and reproducibility

The [predeclared protocol](../../ordinary-luna-categorical-pilot-v1.md) and
[frozen preparation](../2026-10-18-ordinary-luna-preparation-v1/manifest.json)
bind the same state, categories, aligned instructions and view order. The SDK
uses a strict-schema Responses envelope and jointly generates labels; native
internal grouping is unknown. This configured-pipeline comparison cannot isolate
model capability, joint generation, reasoning settings or serialization effects.

Jev4Mellea is pinned to 0.8.0 / commit
`b9b7f9a340473cb2705fbdf62b4011c19ddb09b2`, OpenAI SDK to 3.31.0, model
`gpt-6-luna`, requested reasoning `low`. Python 3.11.13 ran the pilot. The
repository-wide Python baseline and both Python CI setups now use 3.11; previous
artifacts retain their actual historical runtime metadata.

`CategoricalResult.answers` supplies labels only. No probability/confidence is
invented. The existing two SpecificationCore consistency rules accepted all eight
tuples without repairing labels or changing gates. Production S/U and accepted
facts remain unchanged.

Files preserve frozen SDK request bodies, public credential-redacted SDK response
evidence, a durable dispatch ledger, counters/timing, actual model/usage metadata,
source/package inventories and offline replay. SDK-redacted evidence is not an
unconditional claim of unredacted HTTP bytes or remote execution attestation.
`result-receipt.json` binds every file after analysis. See [diagnosis](diagnosis.md).

**Next task:** predeclare a broader, independently labeled contrastive cohort and
repeat Jev versus ordinary Luna with these fixed instruction/configuration
conditions before generalizing quality, reliability, latency or backend policy.
