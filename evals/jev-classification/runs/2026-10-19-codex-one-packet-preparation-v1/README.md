# One-packet Codex backend qualification: offline preparation

Status: **prepared offline, runtime not qualified; inference not authorized**.
No model process or hosted request was made to prepare this package.

## Selected control

Use **R01 / baseline**, an existing Specification in SpecGraph:
`tools/subject_workspace_allocation_spec.py::WORKSPACE_ALLOCATION_SPEC`,
revision `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`, lines 7–17.
The full historical source was checked against that Git object during preparation
and is preserved in `source_file.py.txt`; its SHA-256 and excerpt binding match
the historical task.

```python
WORKSPACE_ALLOCATION_SPEC: PredicateSpec[WorkspaceAllocationContext] = PredicateSpec(
    lambda context: (
        context.allocation["workspace_identity"] == context.requested_workspace_identity
        and context.allocation["source_ref"] == context.requested_source_ref
        and context.allocation["expected_commit"] == context.requested_expected_commit
        and context.allocation["identity_allocation_authorized"] is True
        and context.allocation["source_ref_initialization_authorized"] is True
        and context.allocation["declaration_sha256"] == context.requested_declaration_sha256
    ),
    name="subject_publication.workspace_allocation",
)
```

The purpose is a **transport/schema qualification**, using a small known control
before a larger study. Selection is deliberate, not random or representative.
One answer cannot establish semantic accuracy, repeatability or a backend ranking.
The historical revision is intentional: this is not a scan of current SpecGraph.

## Preserved semantics and explicit differences

`packet.json` preserves the exact `task.state` and `task.questions` from
`../2026-10-18-ordinary-luna-preparation-v1/manifest.json`, request
`R01-baseline-luna-responses-coreinfra`. The four axes remain `concern_kind`,
`evidence_confidence`, `ownership`, and `tool_responsibility`. The aligned
architectural instructions and criterion definitions are unchanged. Unresolved
accepted-facts placeholders stay unresolved; no Intent document, extra helper
body, retrieved hit, prior model answer or author label is added.

The required wrapper repeats the same semantic paragraph from the independent
annotation brief. The Codex adapter adds its structural output/tool restrictions.
This preserves semantic guidance, **not historical wire identity**. Codex returns
categorical labels without rationale or native probabilities. Sol's frozen
comparator and receipt are hash-bound in `plan.json` and are not in the model
packet or prompt. No new Sol run is planned. Comparator agreement does not prove
independent semantic truth.

The selected profile is `gpt-6-luna`, **medium**, CLI `codex-cli 0.156.1`,
120 seconds, 1 MiB capture. The historical ordinary API pilot used **low**, a
30-second timeout and a 1024-output-token limit. The Codex profile cannot enforce
that token limit. Therefore a future observation also changes effort/transport
conditions and cannot isolate a causal backend improvement.

## Files and offline verification

- `packet.json`: sole semantic packet for the future model.
- `backend-config.template.toml`: portable path placeholders, no credentials.
- `prepared.template.json`: actual offline CLI output, including prompt, schema,
  effective arguments and their bindings. **Template, not executable readiness.**
- `source_file.py.txt`: full historical source witness, never executed/imported.
- `plan.json`: source/reference/file hashes, authorization, budget and criteria.

From the repository root, use the built CLI and repository Python environment:

```sh
.venv/bin/python -B evals/jev-classification/verify_codex_one_packet_v1.py \
  --binary /absolute/path/to/specification-metrics
```

The verifier checks historical receipts, exact task/guidance/criteria preservation,
source/excerpt hashes, reference bindings and the preparation budget, then runs
only `prepare-classification` to reproduce the template. `cargo test` runs this
offline verifier through `tests/codex_one_packet_preparation.rs`. CI uses Python
3.11; no SDK, model service or installed Codex is needed by this check.

## Future bounded run (separate authorization)

1. Obtain explicit approval for **one inference process**, four categorical
   questions, no adapter retries, no semantic retry, no new Sol calls. CLI-internal
   HTTP attempts, token use and currency cost are not bounded by process count.
   No hard monetary cap is claimed.
2. Resolve the executable and a dedicated authenticated Codex home with no
   `AGENTS.md` / `AGENTS.override.md`. Do not copy credentials into this package.
   Local CLI version was observed as `codex-cli 0.156.1`; authentication and hosted
   model availability remain unverified.
3. Copy the template config to an operator-selected artifact directory, replace
   only the two paths, and run **offline preparation again**. Preserve the resolved
   config/prepared hashes before dispatch. Keep all model settings fixed.

   ```sh
   /absolute/path/to/specification-metrics prepare-classification \
     --packet evals/jev-classification/runs/2026-10-19-codex-one-packet-preparation-v1/packet.json \
     --config /absolute/artifacts/backend.toml \
     --output /absolute/artifacts/prepared.json
   ```

4. After approval, dispatch once into a **fresh** private directory outside Git
   and project-config ancestry (the parent must already exist):

   ```sh
   /absolute/path/to/specification-metrics run-classification \
     --prepared /absolute/artifacts/prepared.json \
     --run-dir /absolute/artifacts/fresh-run \
     --allow-hosted-classification
   ```

5. Preserve raw events, final answer, process metadata and report on success or
   failure. Stop after the first attempt; diagnose a failure before proposing
   another authorization.

Transport acceptance requires one completed turn, no tools/configuration errors,
and all four schema-valid answers. Failed/incomplete output is
`analysis_incomplete`, never a fabricated `unknown`. A valid output is only a
`proposal` with `semantic_validation_status: not_run` and `metric_effect: none`.
Then compare its four labels with the existing R01/baseline Sol comparator and
review disagreements. Record latency, reported usage and missing billing/model
metadata explicitly. Do not convert the answer into accepted domain facts.

Next: review this preparation, resolve the isolated authentication prerequisite,
and authorize the single backend qualification run.
