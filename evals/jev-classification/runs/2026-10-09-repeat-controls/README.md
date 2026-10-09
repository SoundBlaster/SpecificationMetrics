# Same-byte repeat controls · 2026-10-09

## Protocol fixed before inference

Two fresh rounds, each containing the same eight cases and both state-key-order
arms: **32 requests maximum**, two fresh observations per exact wire. Round 1
retains the earlier balanced pair order; round 2 reverses each pair, with the
same case order. Model `jev-1.13.0`, endpoint, questions, semantic state and exact
request bytes for each candidate/arm remain unchanged. The sender from the
[previous diagnostic](../2026-10-09-state-key-order/README.md) is reused.

`protocol.json` pins both round manifests. Each manifest pins its plan, source
states, reference annotations and producer implementation. The offline scorer
verifies identical request digests between rounds, ordered response-to-plan
binding and model/response contracts before comparing outputs. No prompt or
threshold tuning occurred. The execution stops before starting another round
if the preceding round is incomplete; each sender stops on its first operational
failure. Limits: 40,000 observed tokens per round checked after responses, no
inference retries, 1 MiB response cap, 30-second socket timeout. A socket timeout
is not a hard total-run deadline. The key spending cap is separate from tokens.

There is no local evaluation cache. Upstream caching and backend sampling
settings are not observable, so fresh HTTP responses do not prove independent
samples or immutable model weights. Connections are reused within each round;
each round creates its own connection.

## Results

| Measurement | Round 1 | Round 2 |
|---|---:|---:|
| Successful / planned requests | 16/16 | 16/16 |
| Elapsed seconds, including TLS preflight | 11.839 | 14.120 |
| Reported tokens | 34,420 | 34,420 |
| Opportunity agreement, insertion / canonical | 4/8 / 4/8 | 4/8 / 4/8 |
| Eligible recall, either arm | 0/3 | 0/3 |
| Concern-kind agreement, either arm | 7/8 | 7/8 |

All **32/32** responses completed, **25.959 seconds** summed round elapsed time,
**68,840 reported tokens**, zero inference retries or operational failures.
Reported tokens are not actual dollar cost or remaining credential balance.

| Comparison | Axis | Changed labels / comparisons | Maximum probability delta | Maximum confidence delta |
|---|---|---:|---:|---:|
| Identical bytes across rounds | opportunity | 0/16 | 0.09 | 0.14 |
| Identical bytes across rounds | concern_kind | 0/16 | 0.06 | 0.08 |
| Different key order within rounds | opportunity | 0/16 | 0.21 | 0.32 |
| Different key order within rounds | concern_kind | 0/16 | 0.12 | 0.16 |

Each same-byte comparison is round 1 versus round 2 for one candidate/arm.
Each cross-arm comparison is insertion versus canonical for one candidate/round.
These pairs share cases and responses; they are not independent trials for a
significance calculation. Agreement references one blinded model annotator,
not human-approved gold; these are diagnostic development cases, not a holdout.

## Insights and revised interpretation

1. **Categorical stability did not imply numerical stability.** Identical bytes
   produced different probabilities/confidence, although selected labels stayed
   fixed in both new rounds. Threshold-based fallback could react differently
   even when top labels are unchanged; no threshold is calibrated by this run.
2. **The earlier label flip did not reproduce.** Earlier sg-018 insertion was
   `eligible`; both new insertion responses are `excluded`, matching canonical.
   Exact wire digests match the earlier plan. Thus the previous ordering pair
   cannot support a deterministic claim that order caused its categorical change.
   Older output is retained separately, not pooled into the fresh control result.
3. **Ordering remains a robustness variable, not a demonstrated root cause.**
   Cross-arm numerical deltas were larger than same-byte deltas in this small
   run. That observation does not establish a general effect size, causality or
   backend behavior. Two repeats are insufficient to estimate rare flip rates.
4. **The main semantic failure persists.** All reference-eligible cases remain
   excluded and owned sg-020 remains eligible under every arm/round. Repeating
   calls did not improve the classifier or recover historical 7/8 agreement.
   Representation stability and semantic correctness require separate checks.
5. **Do not use repetition as a quality fix.** Preserve the architecture goal,
   verify ownership formally, and inspect the concrete eligibility criteria
   behind false exclusions before another prompt experiment. The policy versus
   mechanics reference for sg-019 still needs human adjudication.

These findings are added to the [cumulative ledger](../../insights.md).
No production classifier routing, prompt, thresholds, registry or S/U changed.

## Offline reproduction

From `evals/jev-classification`:

```bash
python3 -m unittest -v test_repeat_controls.py
python3 state_key_order.py --run runs/2026-10-09-repeat-controls/round-1
python3 state_key_order.py --run runs/2026-10-09-repeat-controls/round-2
python3 score_repeat_controls.py --run runs/2026-10-09-repeat-controls --output /tmp/repeat-controls-summary.json
```

`summary.json` uses analysis revision 2, recalculated offline after review.
`analysis-v2.json` pins the unchanged historical protocol and every local analysis
module, including the round scorer and `experiment.py` metrics. The scorer
verifies this complete set before producing a report; dependency drift fails
closed. Historical live manifests (including their empty analysis digest fields),
producer hashes, wire plans, responses and receipts remain unchanged. The new
analysis manifest describes this recalculation, not the implementation at live
execution time. Agreement and stability measurements are unchanged.

No keys or inference are needed. The report is derived from stored responses,
receipts and frozen plans. The sender requires explicit `--live` to infer and
refuses to overwrite completed run directories; the scorer likewise refuses to
overwrite its output. CI runs the offline tests and validates both plans.
