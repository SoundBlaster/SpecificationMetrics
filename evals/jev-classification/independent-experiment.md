# Independent machine-reference experiment

## What this experiment measures

The target is discovery assistance: find stable rules worth representing with
SpecificationCore without classifying mechanics or existing specifications as
remaining opportunities. `opportunity` and `concern_kind` stay independent.
Classification never writes the reviewed registry or changes S/U counters.

One isolated Codex subagent annotated 60 pinned SpecGraph contexts. Its context
contained neither prior proposals nor Jev output. Opaque IDs replace the
inventory IDs in the reviewer packet and model input. The reviewer read only
the prepared packet, with label definitions in its assignment. Source paths,
identifiers and imports remain visible because they are evidence.

This is **independent model annotation**, not human-approved gold. The parent
agent had seen prior proposals; it did not author or adjudicate these labels.
No second reviewer or human adjudication occurred. Both reviewers are Codex
agents, so shared model biases remain possible. The isolated subagent's exact
model/checkpoint was not exposed by the delegation interface.

## Frozen protocol

- Keep original provisional labels unchanged; save references separately in
  `corpus/annotations.model-v1.json` with source rationales and missing context.
- Group complete decision families, including related lifecycle functions and
  historical pairs. Sort families by SHA-256 of a fixed seed and family ID;
  reserve the first quarter for holdout. Labels do not select families.
- Screen six fixed prompts on one deterministically selected site from each of
  twelve development families. Four prompts add a single opportunity instruction
  to baseline; `boundary-test-v2` is the previous multi-factor comparison.
  State, concern-kind criteria, model and context stay fixed across providers.
- Rank challengers by eligible recall, then precision, then lower abstention,
  then variant ID. Keep baseline and the best challenger, including a tie.
  Freeze the exact prompt configurations before opening holdout.
- Run those two prompts once on every held-out site. Provider/contract errors
  remain counted as abstention and separately reported; missing rows fail
  scoring. Do not select a challenger when any API/contract errors occur.
- Preliminary discovery targets: recall >= 0.90, precision >= 0.80, abstention
  <= 0.35, no provider errors. These were recorded before hosted runs; meeting
  them on a small machine reference would still not authorize deployment.
- Report matrices, per-class precision/recall/F1, supported-class macro-F1,
  coverage, non-abstained error, false exclusions and whole-family paired
  bootstrap intervals. Classes absent from both truth and predictions have
  undefined scores and are omitted from macro-F1, rather than scoring as perfect.
- Use fresh responses, no retries, concurrency one and at most 120 hosted
  requests per invocation. Save results after each candidate, preserving outputs,
  probabilities, usage, returned model and input/prompt digests. Unique run
  directories prevent accidental overwrite. A holdout-start marker prevents
  silently rerunning the same finalist file; failed confirmation needs an
  explicitly documented new attempt.

The resulting split has 50 development sites in 25 families and 10 holdout
sites in 9 families. Screening uses only 12 of the development sites. The
holdout has only two eligible references and no abstention or domain-variant
references: it cannot validate those classes or a reliable recall target.
Do not move difficult cases between splits after observing results.

## Reproduce the offline artifacts

From this directory, use the project Python environment:

```bash
python experiment.py prepare --output results/new-review
# Give ONLY packet.json and the rubric to an isolated reviewer.
# For the recorded experiment, the committed model reference is reusable:
python experiment.py freeze \
  --annotations corpus/annotations.model-v1.json \
  --mapping results/new-review/mapping.json \
  --output results/new-review/manifest.json
python experiment.py score \
  --manifest results/new-review/manifest.json \
  --run runs/2026-10-05-independent-reference/development.json \
  --output results/new-review/development-summary.json
```

`prepare` validates corpus provenance/leakage invariants. Also run
`build_specgraph_corpus.py --repo /path/to/SpecGraph --check` to verify the
corpus against Git objects before a new study. The committed experiment manifest
retains context digests and references; context is reconstructed from the pinned
corpus, rather than copied into every receipt.

## Run new hosted experiments

Requires `TYPESAFE_API_KEY` from the existing shell environment. Without
`--allow-hosted`, the runner prints the request plan and sends nothing.

```bash
PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_CACHE_TYPE=memory \
  node run_experiment.mjs --phase development \
  --manifest results/new-review/manifest.json --allow-hosted \
  --output results/new-development
python experiment.py score --manifest results/new-review/manifest.json \
  --run results/new-development/run.json \
  --output results/new-review/development-summary.json \
  --select results/new-review/finalists.json
PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_CACHE_TYPE=memory \
  node run_experiment.mjs --phase holdout \
  --manifest results/new-review/manifest.json \
  --finalists results/new-review/finalists.json --allow-hosted \
  --output results/new-holdout
```

The recorded holdout is consumed. Future tuning using these results must treat
it as development evidence and collect new independent families for confirmation.
Repeatability and a separate context-size/context-content experiment are not
measured by this run. Jev has a mutable model ID, no immutable checkpoint.

Source excerpts remain Apache-2.0; tool code and annotations remain MIT.
