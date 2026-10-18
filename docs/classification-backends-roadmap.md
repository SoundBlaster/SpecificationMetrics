# Classification backend roadmap

Date: 2026-10-18. Status: proposed; this document does not implement adapters or
authorize model inference, server startup or model downloads.

## Goal

Provide inexpensive, fast semantic classification and architectural checks with
an explicit quality floor. Select execution backends through configuration while
keeping the task, bounded source context, category definitions and deterministic
Specification-based validation consistent. System One is one backend option.

This extends the [classification contract](candidate-classification-contract.md)
and the [formal analysis roadmap](formal-analysis-roadmap.md). The current Rust
CLI has a Jev-specific client; a general backend interface remains planned.
Suggestions continue to be separate from reviewed facts, registry dispositions
and S/U snapshots.

## Progress and remaining scope

The initial instruction gap has already been investigated in the merged
[semantic instruction-parity diagnostic](../evals/jev-classification/semantic-instruction-parity-v1.md)
and its [captured native run](../evals/jev-classification/runs/2026-10-18-semantic-instruction-parity-live-v1/README.md).
That diagnostic reused the unchanged Sol reference; it made zero new Sol calls.
The [ordinary Luna pilot](../evals/jev-classification/ordinary-luna-categorical-pilot-v1.md)
also ran through the public Jev4Mellea categorical SDK. The current evaluation
environment uses [SDK 0.9.0](jev4mellea-0.9-upgrade.md), and the
[categorical review bridge](categorical-review-bridge-v1.md) connects captured
native results to the existing routing Specifications and independent review.

The experimental [Rust categorical packet contract and Codex CLI adapter](categorical-backend-contract-v1.md)
now provide offline preparation and explicit bounded execution through separate
commands. They do not migrate the existing scanner's Jev provider, implement
general API/local server adapters, or establish hosted model compatibility.
The remaining delivery sequence does not require repeating completed experiments
or grant new inference authorization.

## Planned backends

| Backend | Execution route | Required planning scope |
| --- | --- | --- |
| System One | Native provider API | Preserve native categorical outputs and available distributions |
| General LLM API | Structured-output API | Validate the response schema and preserve available source evidence |
| Codex CLI | Non-interactive process | Explicit model/effort, bounded packet, final JSON schema and process budget |
| **Ollama** | **Local model server adapter** | Configurable endpoint/model, capability preflight and local execution provenance |
| **LM Studio** | **Local model server adapter** | Configurable endpoint/model, capability preflight and local execution provenance |

Ollama and LM Studio are separate first-class targets, not an assumption that one
generic HTTP endpoint implements both completely. Start with direct server
adapters for controlled packet-in/result-out execution. Any later routing through
Codex must be recorded as a distinct route with its own overhead and capabilities.
No server, model, API compatibility or reasoning feature is asserted available
merely because it appears in this plan.

## Shared contract and configuration

- Keep semantic tasks separate from transport: model ID/revision, backend,
  endpoint, reasoning settings, context budget, schema/rubric version, timeout,
  concurrency and retry budget are explicit effective configuration.
- Check capabilities for the selected server **and model** before inference:
  supported structured-output mode, reasoning controls and context/output bounds.
  Unsupported settings produce a clear configuration diagnostic; never silently
  ignore `high`, change model, drop schema enforcement or switch to hosted service.
- Return one typed classification proposal. Preserve native probabilities when
  available; ordinary structured judgments may omit them. Do not fabricate a
  one-hot distribution or compare self-reported confidence to native scores as
  though they were calibrated alike.
- Distinguish schema validity, role/support coherence, source evidence and
  acceptance authority. All backends feed the same applicable validators;
  malformed output, missing evidence and contradictions remain visible.
- Supply the frozen bounded packet without prior labels or uncontrolled project
  history. Record the task instructions actually sent; broader agent browsing is
  a separate execution mode, not an invisible context improvement.
- For local runs, record server/version, requested and reported model identity,
  model digest and quantization where exposed, hardware/runtime settings and
  cold/warm state. Unavailable metadata stays explicitly unavailable. Local
  server selection does not itself attest where inference actually ran.
- Capture raw results, effective configuration, timing, retries and provenance.
  Do not install, download, start servers or perform inference as a side effect
  of offline configuration validation.

## Delivery sequence

| Phase | Deliverable | Completion criterion |
| --- | --- | --- |
| 1 | Shared backend contract and Codex CLI/general API routes | The same pinned packet passes common contract tests; model-specific unsupported features fail explicitly |
| 2 | Ollama adapter | One locally served model produces schema-valid proposals with recorded configuration, failure paths and source bindings |
| 3 | LM Studio adapter | The same contract suite passes against its adapter; selected server/model compatibility is verified independently |
| 4 | Matched quality/cost/latency comparison | Compare supported configurations on frozen packets with reviewed disagreements and complete coverage accounting |

Phase 4 additionally requires the
[prompt-parity protocol](classification-prompt-parity.md): all selected backends
receive the same canonical semantic guidance and evidence view, with rendered
prompt hashes and capability differences recorded. The original Sol/native
comparison used unequal instruction detail; the later instruction-parity and
ordinary Luna pilots are separate, source-bound observations. Keep those prompt
conditions distinct. Reuse an existing reference only after verifying the
unchanged semantic guidance, rubric, evidence views and recorded configuration
under the protocol. Establish parity before the separate accepted-facts
placeholder ablation or model-selection conclusions.

Measure both `medium` and `high` only for models that expose those settings; do
not assume more reasoning makes a cheap model as accurate as the strong-model
comparator. A local pilot requires an explicitly selected model and available
runtime, not an automatic download of an unspecified Llama or other checkpoint.

## Evaluation and selection

Track agreement with the pinned comparator separately from independently
reviewed correctness, useful non-abstaining coverage, contradictions, false
ownership/reuse assertions and repeatability. Count retries and escalation in the
cost of a usable, validated decision rather than optimizing only nominal token
price. A strong-model top line is an empirical comparator, not a mathematical
upper bound.

Measure end-to-end latency including CLI startup and model loading; distinguish
cold/warm runs, concurrency, cache hits and hardware. Report API currency charges,
subscription allowance usage and local resource/runtime costs separately; an
already-paid subscription or local server is not unlimited zero-cost capacity.
Do not invent dollar equivalents when billing evidence is unavailable.

Next slice: qualify the experimental Codex route on one approved frozen packet,
then connect prepared backend results to the existing validation consumers and
add the general API route. Review the captured ordinary Luna low-effort pilot
before preparing a separately authorized medium/high comparison. Ollama and
LM Studio follow as explicit local adapter milestones under the same contract.
