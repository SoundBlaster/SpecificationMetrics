# Replay scope-binding v3.1 result package

From the original `evals/jev-classification` directory:

```sh
rtk proxy ../../.venv/bin/python -B runs/2026-10-14-scope-binding-v3-1-results-astra-high/replay_package.py
```

The command is read-only. It checks the complete SHA256SUMS inventory, execution
receipt dependencies, all 12 frozen-validator attempts, exact retained/original raw
equality, and all 144 review entry identities and 288 contiguous rationale quotes.
It does **not** decide whether the proposed semantic judgments or raw labels are
correct. The assembly script binds explicitly authored review data; it is not a
semantic grader and is intentionally not an overwrite/replay command.

Individual original-path replay:

```sh
rtk proxy ../../.venv/bin/python -B validate_scope_binding_annotations.py \
  --assignment runs/2026-10-14-scope-binding-v3-1-results-astra-high/attempt-receipts/annotator-01-attempt-01.json \
  --annotation runs/2026-10-14-scope-binding-v3-1-results-astra-high/raw-attempts/annotator-01-attempt-01/annotations.json
```

Every receipt declares the actual absolute packet/template/prompt paths. They must
still exist with the recorded bytes, and the original producer/validator dependency
bytes must match. A relocated checkout can verify package hashes but cannot claim
original-path dispatch verification from copies alone. Do not rewrite receipts to
make replay pass after relocation or mutation.

Before each spawn, the CLI `--check-delivery --assignment` command was run against
that slot's original delivery receipt and the exact checked prompt was supplied to
the fresh context. Slots 01–04, 05–08 and 09–12 were dispatched in three completed
waves, with at most four annotation children active. Slot 01 preflight output was
captured as an explicitly marked parsed transcription from the successful tool
output; slots 02–12 contain the CLI stdout directly. The original tool transcript is
the dispatch evidence for prompt delivery and canonical task creation. A prompt file
hash is not independent proof that a model consumed it.

The blank original delivery receipts/template retain their preparation-stage state.
Filled attempt receipts and execution-receipt.json are the post-run authorities.
No raw JSON, label or evidence quote was repaired. All first attempts were formally
valid; there are zero failed/excluded attempts or replacements. Direct external
provider API requests are zero; 12 annotation contexts are counted separately from
the one nonblind model-integrator context.

Isolation remains scoped assignment plus fresh context and self-report, without
filesystem enforcement. Pre/post checks cannot detect an intervening mutation that
was restored. Requested model/effort are recorded, runtime model identity remains
unverified/null. Formal acknowledgment of scope is not semantic fidelity. Review is
proposed NONBLIND MODEL-INTEGRATOR work, not human gold or adjudication. There is no
automatic batch semantic gate and no provider scoring reference.
