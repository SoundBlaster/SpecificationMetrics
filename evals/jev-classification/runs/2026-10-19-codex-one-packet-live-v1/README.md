# Codex qualification: R01 / baseline live observation

Date: 2026-10-19. **One authorized inference process; no adapter/semantic retry,
no new Sol calls.** The packet and planned configuration were prepared in
[PR #89](https://github.com/SoundBlaster/SpecificationMetrics/pull/89).

## Result

The installed Codex CLI `0.156.1` completed one turn in **9.645 seconds** with a
schema-valid answer, empty stderr, and no tool events. The adapter returned
`proposal`; this qualifies the observed transport/schema route for this one
packet. `semantic_validation_status` is **not_run** and `metric_effect` is
**none**. It does not qualify model accuracy or accept domain facts.

| Axis | Codex Luna, requested medium | Frozen Sol medium | Historical API Luna low |
| --- | --- | --- | --- |
| concern_kind | policy | policy | policy |
| evidence_confidence | supported | supported | supported |
| ownership | **unknown** | **existing_specification** | **existing_specification** |
| tool_responsibility | unknown | unknown | unknown |

There are **three matching axes out of four**, and **no complete-view agreement**.
This selected control is not a dataset accuracy estimate; `unknown` is a genuine
model answer, not a transport failure converted into an abstention.

| Reported observation | Codex CLI | Historical API |
| --- | ---: | ---: |
| Elapsed seconds | 9.645 | 6.3613 |
| Input tokens | 10,834 | 3,316 |
| Output tokens | 37 | 181 |
| Requested effort | medium | low |
| Returned model identity | unavailable | gpt-6-luna |
| Currency cost | unavailable | not assessed here |

The reported input-token difference is **7,518** (3.27 times the historical
count). Codex supplies its own transport/system envelope, but the experiment
does not capture the server's full prompt or isolate the cause of this difference.
It is not a controlled latency, cost or effort comparison. Codex reported zero
reasoning output tokens; that neither attests medium effort took effect nor
proves the absence of internal reasoning. Model/effort remain requested settings.

## Isolation, authorization and evidence

- User authorization: **«Выполняй»**, continuing the frozen one-process plan.
- Same historical SpecGraph revision, state, questions, guidance and schema.
  Only the executable/authentication-home paths were resolved locally. The
  effective prepared artifact and exact arguments were recorded before dispatch.
- A private task home referenced the existing owner-only `auth.json` through a
  symlink. The harness did not read or copy credential contents; no credentials
  are included here. No configuration, global instructions or prior sessions were
  copied into the task home. The temporary auth symlink was removed after capture.
- The pinned adapter disabled project/skill instructions and tools; the event
  capture shows only thread/turn lifecycle and the final agent message. This is
  not attestation of an identical system prompt across providers.
- `authorization.json`, `backend.toml`, `authorized-prepared.json` and
  `prepared.json` preserve the local
  execution premises; **the local paths are historical evidence, not a portable
  configuration or a reusable authorization**.
- `authorized-prepared.json` retains the exact pre-dispatch CLI output bound by
  the authorization SHA-256. Runtime `prepared.json` is the adapter's equivalent
  serialization without the terminal newline. Both byte hashes are preserved;
  the verifier checks parsed equality rather than rewriting either artifact.
- `argv.json`, `runtime.json`, `request.stdin`, `response.schema.json`,
  `events.jsonl`, `stderr.txt`, `answer.json` and `report.json` are raw captures.
  `receipt.json` binds captures and reference files; `comparison.json` is derived
  after capture. No authentication directory/cache is published.
- One inference process does not prove one billable HTTP request. Internal
  provider requests, currency cost and returned CLI model remain unavailable.

See [diagnosis.md](diagnosis.md) for the ownership discrepancy, evidence and
proposed next diagnostic. The existing Sol comparator remains unchanged and is
an empirical reference, not independently established semantic truth.

## Offline verification

```sh
.venv/bin/python -B evals/jev-classification/verify_codex_live_v1.py
cargo test --locked --test codex_one_packet_preparation
```

The checks validate hashes, unchanged semantic input, authorization/budget,
capture/report/comparison bindings and preserved disagreements. They do not
execute Codex, contact a provider, or reuse the expired single-run authorization.
