# Ordinary Luna through Jev4Mellea categorical SDK: pilot v1

## Scope and frozen comparison

Use Jev4Mellea 0.8.0's public `CategoricalTask`, `ChoiceQuestion` and
`ResponsesChoiceProvider` for eight SpecGraph evidence views: four targets, each
with baseline/retrieval. The SDK builds/parses the actual Responses request;
the consumer does not copy a JSON schema builder or native probability parser.

Reuse the original 24 Sol 6.1 Medium annotations, source witnesses, rubric,
eight-view consensus and receipt. **Zero new Sol calls.** Compare to both native
providers' [instruction-parity run](runs/2026-10-18-semantic-instruction-parity-live-v1/README.md).
Preserve historical producer sources and observations.

Construct the semantic task directly from each aligned native Jev request:
same decoded state (including unresolved placeholders and retrieval), named
questions, instructions, category definitions and question order. Remove only
the native question `type` envelope when constructing `ChoiceQuestion`.
Freeze source request hashes, semantic task, actual SDK-rendered request body,
SDK builder revision, package/source inventories, source/reference receipts and
scoring policy before live observation.

One Responses request jointly generates four labels; native requests also
contain four questions, but their internal evaluation grouping is unknown.
SDK serialization wraps the shared JSON state under `state` and adds a fixed
Structured Outputs instruction and schema. Sol supplies rationale/source quotes;
the API consumer requests labels only. This is a configured-pipeline comparison,
not a model-only experiment or a claim of identical computation.

## Selected configuration and budget

- Jev4Mellea 0.8.0, commit `b9b7f9a340473cb2705fbdf62b4011c19ddb09b2`.
- OpenAI Python SDK 3.31.0; all dependencies pinned in the pilot lock file.
- Ordinary `gpt-6-luna`, Responses API, requested reasoning effort `low`.
- Exact endpoint `https://hub.coreinfra.ai/openai/api/v1/responses`.
- 1,024 output tokens including reasoning; 30 seconds per HTTP operation;
  1 MiB maximum response body; no truncation, storage or streaming.
- Eight logical tasks, **at most eight HTTP dispatches**, zero automatic or
  semantic retries. Stop after the first failed task. Do not raise the token
  budget, repair JSON, change model/effort or repeat a completed/partial directory.
- The user approved this eight-view pilot. The separate SDK compatibility probe
  supports selecting this route/configuration; it is not classification evidence.

Python >=3.11 is the repository-wide collection/evaluation baseline required by
the SDK. Both Python CI setups select 3.11; the main job installs the shared lock
and runs the SDK pilot replay with the historical checks. Local `.venv` uses
Python 3.11.13; the previous 3.10.19 environment is retained only as a rollback
backup. Historical runtime metadata and artifacts stay unchanged; no historical
model calls are repeated. Machine-local TB5 paths are not repository configuration.

## Evidence and outcomes

Record the public SDK evidence, excluding HTTP headers/credentials: submitted
request JSON and bounded response bytes are credential-redacted by the SDK.
This is not an unconditional claim of exact unredacted HTTP bytes. Bind the
outgoing body to the frozen SDK request before dispatch; allow one dispatch per
task and no redirects or environment-proxy fallback. Keep a durable, fsynced
dispatch/completion ledger, timing, result metadata, SDK evidence hashes, source
and package inventories and execution-runtime snapshot. A dispatch is a
conservative potentially-billable boundary, not a billing receipt or remote
attestation. No API key is saved or printed.

The endpoint router forwards a streaming request. The audit transport must read
that stream before accessing its content and then forward exactly the frozen
bytes without reserializing them. A dedicated regression exercises this boundary;
MockTransport's later implicit read must not hide it during preparation.

Reconstruct successful results offline through the same public SDK with a mocked
HTTP transport and the captured body. Verify requested/returned model identity,
all question IDs/categories and metadata; never synthesize native distributions,
confidence or probability-based requirements. Reuse the existing role/support
and responsibility-consistency Specifications on the selected labels.

Separate transport/SDK errors, refusal, incomplete generation, identity mismatch,
domain-consistency conflicts, abstentions and reference disagreement. None of the
first five outcomes becomes an `unknown` label or a repaired success. Preserve
captured prefixes and planned denominators; do not score an incomplete cohort
as a complete comparison.

## Predeclared evaluation and interpretation

Report 32 planned axis slots, 16 primary role/ownership slots, eight responses,
per-axis and per-view labels, baseline/retrieval agreement, unknown roles,
consistency conflicts, available token usage and client elapsed time. Compare
with unchanged Sol and the saved Jev/Luna Decision configurations. Keep missing
usage unavailable and monetary cost unknown unless actually reported.

This pilot tests whether an ordinary low-reasoning generative backend can produce
useful coherent decisions through the common label contract at acceptable token
and latency cost. Its agreement/coherence may improve, worsen or trade off;
there is no automatic winner or production-acceptance threshold. This small
development cohort has baseline-sufficient examples and explicit ownership;
it cannot establish representative accuracy, retrieval's hidden-fact discovery,
provider reliability distributions or instruction-specific causality.

The general configurable-runner refactor and additional local/hosted backends
remain deferred until this bounded comparison is interpreted. No production S/U
changes or automatic fact acceptance follow from a model answer.

## Commands

From this evaluation directory, using the isolated environment:

```sh
python categorical_luna_pilot_v1.py freeze
python categorical_luna_pilot_v1.py stage
python categorical_luna_pilot_v1.py execute --live
python categorical_luna_pilot_v1.py score
# Add the diagnosis/README, then bind all run files.
python categorical_luna_pilot_v1.py seal
python -W error -m unittest -v test_categorical_luna_pilot_v1.py
```

Only `execute --live` performs hosted inference. Offline rendering/replay uses
the actual SDK with synthetic HTTP transports and explicit fixture keys.
