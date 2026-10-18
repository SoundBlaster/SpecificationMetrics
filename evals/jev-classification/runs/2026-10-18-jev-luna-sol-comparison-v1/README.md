# Matched Jev/Luna comparison with Sol top line

The user authorized comparison after the 24-context Sol 6.1 Medium run.
All 16 planned native requests completed from 09:44:04.549 to 09:44:33.671 UTC on
2026-10-18: about 29.1 seconds, 16 network attempts, 16 potentially billable POSTs,
no TLS retries, ambiguous POSTs or possible duplicate execution. Returned model
and question identities matched the frozen request contracts. No credentials are
stored in the artifacts.

- [Pre-execution contract](../2026-10-18-sol-top-line-comparison-contract-v1/contract.json)
  pins the [Sol comparator](../2026-10-18-sol61-medium-repeatability-v1/top-line.json).
- [Execution binding](comparison-binding.json) and [exact request manifest](manifest.json).
- [Attempt ledger](attempts.jsonl), [captured responses](responses.jsonl),
  [transport receipt](receipt.json), [execution provenance](execution-binding.json).
- [Comparison](comparison.json) retains native labels, consistency conflicts,
  request/body identities and transport verification separately.
- [Diagnosis](diagnosis.md) explains every observed discrepancy pattern and the
  next controlled hypothesis test. [Result receipt](result-receipt.json) binds
  all files and producer code; the transport receipt is preserved unchanged.

Replay offline from `evals/jev-classification` using the repository environment
and required TB5 cache settings:

```bash
../../.venv/bin/python -W error -m unittest -v test_sol_top_line_comparison_v1.py
../../.venv/bin/python sol_top_line_comparison_v1.py --verify-contract
```

The recorded-run test reconstructs the comparison and verifies its result
receipt. These commands do not call the providers. Never rerun this directory
with `--execute --live`; a later experiment needs a new version and authorization.
