# Formal recommendation replay v1

Offline replay of four development cases alongside 18 preserved Jev/Luna native
observations. Zero requests. See the [policy and decision table](../../formal-recommendation-policy-v1.md).

`report.json` contains provenance-bearing facts, decisions with skipped-rule
traces, unresolved-fact question plans, and raw native labels in separate fields.
It binds policy producers and historical input reports by SHA-256. Verify with:

```bash
../../.venv/bin/python replay_recommendation_policy_v1.py
```

Run from `evals/jev-classification`. `--write` refuses an existing run directory.
The historical conditional experiment and its failed H1 remain unchanged. These
four known development fixtures are not an independent reference and do not
establish model accuracy. Source attachment, proposal adjudication and native
provider integration are future steps; no live run is authorized by this package.
