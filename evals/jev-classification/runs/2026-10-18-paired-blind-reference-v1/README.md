# Independent paired-view annotations, 2026-10-18

## Result

- 8 new context-free subagents, one supplied view each, same requested inherited
  configuration; no inherited author conversation or prior labels.
- Frozen assignment slots and baseline-before-retrieval prerequisite preserved.
  Four baseline files were sealed before the four retrieval agents were started.
- 4/4 target pairs retain the same complete category tuple (16/16 paired axes).
  No categorical disagreements or consistency conflicts needed correction.
- All source quotes and line spans verify against their supplied views.
- R04 gains a direct caller witness without a category change; see the
  [source audit](adjudication.md) for code examples and remaining uncertainty.
- Hosted CoreInfra Jev/Luna requests: **0**. S/U and accepted Facts unchanged.

## Execution refinement and limits

The original frozen assignment v1 modeled four actual identities, each with two
fresh contexts. The user explicitly requested eight new subagents. This run
keeps its task/slot/family mapping but uses **eight distinct actual invocations**,
two per balanced logical slot. This is an explicit execution refinement, not a
claim that the old four-person identity contract was satisfied. The old private
four-identity roster checker is not applied to this eight-invocation run; the new
verifier requires eight distinct IDs, no context forks, identical requested
configuration and sealed baseline prerequisites. Original preparation/assignment
artifacts are unmodified.

The four slots are balancing blocks, not four human annotators who each saw both
modes. Stable participant effects cannot be estimated. The common requested model
configuration avoids deliberately changing the annotation model by arm, but
stochastic/backend effects and correlated same-model errors remain unmeasured.
No actual backend model name was exposed by the spawn tool. The shared filesystem
was bounded by read-only task instructions; there was no per-agent OS sandbox.

Agent results are independent of prior author labels and each other's views at
dispatch. They do not establish independent semantic truth. The integrator's
later source audit is history-aware and explicitly identified. The provisional
`reference.json` is view-conditioned evaluation data, not canonical domain Facts.
No Jev/Luna score or same-view inter-rater reliability is inferred from it.

## Evidence and replay

`dispatch.jsonl` records identities, no-fork mode, exact input/prompt hashes and
baseline sealing order. Times are registration times, not authenticated spawn
timestamps. `raw/*.json` contains delivered final JSON values; formatting was
normalized during integrator transcription. Hashes identify stored artifacts,
not provider HTTP bodies. `analysis.json` reconstructs pairwise comparisons;
`reference.json` retains labels and unresolved facts with source-audit binding.
`receipt.json` covers all run files and replay producer sources.

```bash
cd evals/jev-classification
../../.venv/bin/python paired_blind_reference_v1.py \
  --run runs/2026-10-18-paired-blind-reference-v1
```

This verification is offline, rejects changed inputs/citations/identities/order,
and does not rerun agents. H1/H2/H3 provider results and scoring remain pending.
This cohort's baseline sufficiency limits semantic-gain measurement; the audit
defines a future hidden-witness cohort without silently changing this one.
