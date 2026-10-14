# Layer 2 — contract × consumers diagnostic

Preparation only: four tasks, twelve fresh contexts, one whole expression per
context. No annotation, Jev/Luna request, scoring gold or metric update occurs.

| Cell | Documentary contract | Path consumers | Independent repetitions |
|---|---|---|---|
| 01 | Absent | Absent | 3 |
| 02 | Present | Absent | 3 |
| 03 | Absent | Present | 3 |
| 04 | Present | Present | 3 |

The common parser baseline, target, profile, owner names and complete rubric-v2
questions are held fixed. Each cell's three packets and templates are byte
identical. Four cells are deterministically interleaved in each repetition;
this is not random allocation. A fresh annotator sees only its packet/template,
not other views, hypotheses, source mappings or authored audit labels.

Documents occupy `text` fragments with explicit documentary authority; code
occupies `code` fragments. Exact source byte/line provenance stays in the
integrator mapping. The normative bundle is implemented proposal/operator
guidance, not a canonical Requirement. Supporting consumers do not change the
whole selected BoolOp's boundary or give it their side effects.

## Prospective criteria

- H_contract: document-present rationales must not deny the supplied documented
  traversal requirement. Missing canonical adoption or a settled primary role
  may still justify uncertainty.
- H_consumers: consumer-present rationales must not deny supplied path uses or
  the shared staging-prefix use. Enumerating all uses is not mandatory.
- H_target_fidelity: rationales must not silently narrow the target or attribute
  symlink resolution, digest/public-safe/authority checks or URL encoding to the
  selected predicate. Effects in consumers must remain distinct.
- H_traceability: all identities, per-axis quotes and declared isolation must
  match the assigned evidence; quote provenance does not prove semantic support.

The first three are **manual rationale checks**. No particular Choice label is
required. Preserve specific `needs_review / unknown` answers and all failed
criteria rather than tuning a prompt to force policy. No independent gold is
assigned; label agreement is not semantic correctness.

Report per-cell histograms, decisive coverage with denominator three and
within-cell disagreements. Compare document additions at each fixed consumer
level and consumer additions at each fixed document level. One source target,
small samples, common model bias, unequal context lengths and deterministic
ordering prevent broad statistical or causal conclusions.

## Frozen artifacts

`runs/2026-10-14-manifest-contract-factorial-preparation/` contains twelve
packets/templates, the prompt, rubric, mapping, dispatch plan, prospective
study plan, license and receipt. The receipt binds source inputs, generated
bytes and producer identity. The source-selection layer remains integrator-only.

From `evals/jev-classification`, using Python >=3.10:

```sh
python3 prepare_manifest_contract_factorial.py
```

This replays frozen preparation without inference. `--write --run NEW_DIRECTORY`
creates a new preparation exclusively; an existing directory is rejected.
Do not write raw responses into the frozen preparation directory. An interrupted
write is not resumable: use a fresh directory and retain the failed attempt.

Layer 3 supplies regression checks and output validation. Layer 4 supplies a
scoped handoff and manual-review instructions. Preparation does not authorize
launching agents or provider calls; those phases need a separate user request.
