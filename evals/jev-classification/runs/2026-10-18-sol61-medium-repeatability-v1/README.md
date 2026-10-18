# Sol 6.1 Medium repeatability run

24 explicitly authorized new contexts completed, one frozen evidence view per
context, with no inherited conversation or previous labels. This is a live Codex
annotation cohort; no CoreInfra provider calls were made. No retries were used.

- [Configuration](configuration.json), [pre-execution binding](run-start.json)
  and [registration/seal ledger](dispatch.jsonl).
- [24 captured outputs](raw/), each bound to its planned task and unique context.
- [Reconstructed analysis](analysis.json): all eight views unanimous on all axes;
  48/48 primary and 96/96 all-axis same-view pair agreement.
- [Strong-model top line](top-line.json), with explicit comparator authority.
- [Adjudication and limitations](adjudication.md), including rationale differences.
- [Completion receipt](receipt.json), binding the complete file set and producer
  closure. This receipt completes the run; `run-start.json` is historical.

Offline replay from `evals/jev-classification`, using the workspace's verified
TB5 cache settings:

```bash
../../.venv/bin/python -W error -m unittest -v test_sol_reference_repeatability_v1.py
../../.venv/bin/python sol_reference_repeatability_v1.py
```

Replay does not rerun annotation or access credentials/network. Top line means
source-auditable agreement with this strong model on these exact packets, not
semantic accuracy, independent gold labels, a mathematical upper bound, or
retroactive qualification of historical H1/H2 scoring.
