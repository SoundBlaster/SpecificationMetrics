# Categorical backend contract and Codex CLI adapter v1

Status: experimental Rust packet/adapter seam. The existing Jev `classify`,
scanner, registry, rule-reuse gates and S/U calculations retain their behavior.
There are no new model runs or changes to frozen experiment producers.

## Task and proposal

`CategoricalPacket` adds explicit semantic instructions, a source-revision
assertion and rubric version to Jev4Mellea's `CategoricalTask` vocabulary:
`task.state` and named `task.questions`, each with `instructions` and a label to
definition `criteria` map. The Rust types are a serialized interoperability seam,
not a dependency on the Python SDK or a reimplementation of its native parsers.
They can carry the same four-axis task used by the evaluation bridge. The
[fixture](../tests/fixtures/backends/packet.json) is synthetic and illustrative;
it is not a new SpecGraph measurement or a pre-approved live packet.

Preparation retains the complete semantic packet in the prompt and generates a
closed JSON Schema with exactly one selected label per question. No confidence,
probability, rationale or additional label is synthesized. Object keys are
canonically sorted; historical wire bytes and question order are not rewritten.
Use the [prompt-parity protocol](classification-prompt-parity.md) before treating
a newly rendered packet as comparable to an old observation.

The packet, effective configuration, rendered prompt, schema and exact CLI argv
each have a `blake3:` digest. Preparation freezes argv as well as the packet;
execution reconstructs and verifies the current profile before reservation.
Duplicate JSON keys, unknown protocol fields, malformed JSON,
empty instructions/definitions and oversized input are rejected. This verifies
local content binding. The source revision, Intent and rubric remain caller
premises; the backend does not rescan a checkout or attest that supplied code
belongs to the asserted revision. Upstream source/evidence builders and
downstream semantic validators retain that responsibility.

A `proposal` means the selected labels satisfy the packet's output contract.
`semantic_validation_status` remains `not_run`, and `metric_effect` remains
`none`. Consumers must apply the existing named routing/consistency
Specifications before review or any separate authority decision. This seam does
not automatically connect arbitrary packets to those consumers or accept facts.
Native probability consumers cannot use this label-only backend: requesting
native distributions is a capability error, not a fabricated one-hot result.

## Effective configuration and supported scope

The [TOML example](../configs/codex-categorical.example.toml) makes backend,
absolute executable, explicit Codex authentication home, required CLI version, model, reasoning effort, process
timeout and capture limit explicit. Unknown settings fail deserialization.
`system_one`, `general_api`, `ollama` and `lm_studio` are reserved backend values
and fail as unimplemented; they never fall back to Codex or a hosted service.
Their adapters and the scanner-provider migration remain later roadmap work.

The initial CLI capability profile is pinned to **codex-cli 0.156.1**. Supported
requested efforts are `low`, `medium` and `high`; preparation does not claim a
particular model supports them. Execution verifies the installed version before
reserving a run. Strict CLI configuration, an explicit model/effort and captured
diagnostics expose CLI/provider rejection as incomplete analysis. This is not
remote capability attestation: effective server/model settings are unavailable
unless reported. Qualify a selected model with a separately approved bounded
live run before using it in backend selection; no model substitution or effort
fallback is implemented by this adapter.

`max_output_tokens` is explicitly unsupported by this CLI profile; requesting it
fails before dispatch. Capture byte limits are not generation-token or billing
limits. No server startup, model download, CLI installation, authentication copy
or configuration editing is performed.

## Offline preparation

```sh
specification-metrics prepare-classification \
  --packet tests/fixtures/backends/packet.json \
  --config configs/codex-categorical.example.toml \
  --output prepared.json
```

This reads bounded files and renders the packet, prompt, schema and digests. It
does not invoke even `codex --version`; the example can be prepared without an
installed executable. `capability_status` is explicitly configured/unverified.
The prepared artifact contains source context and should be handled accordingly.

## Explicit execution

After selecting the installed executable, approving the real packet/config and
choosing a fresh absolute run directory **outside Git and project-config
ancestry**, execution is a separate action:

```sh
specification-metrics run-classification \
  --prepared prepared.json \
  --run-dir /absolute/external-output/new-run-id \
  --allow-hosted-classification
```

The executable and local CLI version are checked before creating the directory;
failed preflight does not reserve that run ID. An existing run directory is
rejected, including after failure. The newly created owner-private directory
durably records preparation, argv, runtime/executable identity, exact stdin and
schema before dispatch. There is one inference CLI process and no adapter retry,
resume, model fallback or automatic escalation. A different run ID is a separate
explicit invocation; this is not a global ban on repeating an experiment.

Codex uses a fresh ephemeral session, ignores user config, requests the read-only
sandbox and disables project instructions, automatic skill instructions, shell,
MCP/apps/plugins, memories, agents, browser and search tools through its pinned
configuration profile. The default local `view_image` and `sleep_tool` features
are explicitly disabled before dispatch. Only packet input is supplied on stdin. Unexpected tool
events make the result incomplete. These are requested CLI restrictions, not a
claim of identical system prompts, remote execution attestation or a new OS
security boundary. Existing managed controls can reject the invocation.
Authentication remains owned by Codex; a small environment allowlist passes its
existing authentication inputs without saving or printing them. The child uses
only the explicitly selected `authentication_home`. Preflight rejects global
`AGENTS.md` or `AGENTS.override.md` in that home, including unreadable/symlink
entries, before reserving the run. Those files are loaded independently of
`--ignore-user-config` and the project instruction byte limit: relying on those
two settings alone would leak prior context into the comparison. No personal
home/configuration is edited and no credentials are copied. The operator selects
an already authenticated home suitable for this bounded run.

Unix process-group supervision enforces a 1–300 second timeout, kills remaining
descendants and drains bounded stdout/stderr. Non-Unix execution is unsupported.
Each capture/final answer is limited to the configured 128 bytes–1 MiB ceiling;
an overflowing pipe retains at most one extra detection byte. This does not cap
all internal CLI disk writes. Incomplete/failed turns, tool activity, nonzero
exit, missing or mismatched final messages, malformed labels and oversized
answers produce `analysis_incomplete`, retain captured diagnostics and exit
nonzero. They do not become an `unknown` answer or an accepted result.

## Evidence and verification

The run retains `prepared.json`, `argv.json`, `runtime.json`, `request.stdin`,
`response.schema.json`, bounded `events.jsonl` and `stderr.txt`, Codex's
`answer.json` when available, and `report.json` with capture digests. These files
contain potentially sensitive source/results. Runtime records the actual local
CLI and adapter-executable digests, CLI version and host architecture; it does not authenticate
the provider's inference. Usage is copied only when available in the completed
turn event. Returned model, monetary cost, native distributions and underlying
HTTP request count stay unavailable. One process invocation can include
provider-internal activity; it is not proof of one billable API request.

Offline tests use an executable fixture, with no Codex inference or credentials:

```sh
cargo test --locked --test categorical_backend
```

They exercise preserved semantic input, capability rejection, duplicate keys,
authorization, stale preparation, version failure before reservation, success
without invented evidence, refusal/invalid labels, tool events, output overflow,
timeout, descendant cleanup and repeated-run rejection. The existing Rust CI
already runs this integration suite via `cargo test --locked`.

CLI semantics were checked against installed 0.156.1 `exec --help` and the
[official CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
and [non-interactive guide](https://learn.chatgpt.com/docs/non-interactive-mode).
Actual hosted execution and model-quality/cost comparison remain unmeasured.

## Review corrections and prevention — 2026-10-19

Two confirmed P1 findings exposed a gap in the original offline fixtures:

- `codex_hooks`, `memory_tool` and `imagegenext` are legacy aliases in the pinned
  CLI. Their canonical `hooks`, `memories` and `image_generation` settings already
  existed in the profile. Redundant aliases can emit configuration-warning
  `item.completed` error events before `turn.started`; the strict stream parser
  correctly treats that stream as incomplete. Removed the aliases, along with
  obsolete no-op feature switches, rather than accepting warning/error streams.
- The pinned registry enables `view_image` and `sleep_tool` by default. Omitting
  a setting did not disable those tools. In particular, a local image could be
  read outside the frozen evidence before an after-the-fact event check rejected
  the run. Both features are now disabled in the invocation profile itself.

Root cause: the process fixture accepted arbitrary argv. Checking CLI help and
mocked successful output had not verified version-specific aliases, removed
switches or default tool exposure. The independent
[registry fixture](../tests/fixtures/backends/codex-0.156.1-features.json) records
149 canonical keys, legacy aliases, removed/deprecated switches and the audited
default local-tool subset, with upstream commit/source hashes. It is extracted
from the exact 0.156.1
[feature registry](https://github.com/openai/codex/blob/b412ff32c417f855c2b2d1581b77058eed87c84b/codex-rs/features/src/lib.rs)
and [alias map](https://github.com/openai/codex/blob/b412ff32c417f855c2b2d1581b77058eed87c84b/codex-rs/features/src/legacy.rs).
Warning serialization is verified against the same revision's
[JSONL processor](https://github.com/openai/codex/blob/b412ff32c417f855c2b2d1581b77058eed87c84b/codex-rs/exec/src/event_processor_with_jsonl_output.rs).

The two profile regressions failed against the original argv, reporting
`noncanonical feature codex_hooks` and missing `features.view_image=false`.
They pass after correction. Additional cases keep pre-turn configuration
warnings invalid and reject a modified frozen tool restriction even when its
local digest is recomputed. Experimental preparations made before this review
must be regenerated offline; no historical model result is rewritten or rerun.
This remains source/fixture evidence, not a new live provider qualification.
