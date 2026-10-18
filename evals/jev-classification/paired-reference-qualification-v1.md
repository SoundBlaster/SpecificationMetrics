# Paired reference qualification v1

PR74 review confirmed a design failure: eight actual agents with one view each
do not satisfy the original four-participant crossover. Each actual identity
sees only one evidence mode. Four logical slots and identical requested model
configuration do not isolate annotator variation from an evidence effect.

The original eight annotations, code, receipts and source audit are preserved.
Their 0/16 category changes are valid descriptive observations, not validation
of a paired causal comparison. Their `reference.json` status was too permissive;
it is superseded for downstream eligibility by this mandatory qualification.

`paired_reference_qualification_v1.py` first checks annotation integrity, then
counts modes by **actual agent identity**: 8 actual annotators, 0 with one view
of each mode. Its frozen result is `diagnostic_annotations_only_not_paired_reference`,
with `paired_quality_scoring_allowed=false`. A checksum-rebound promotion fails
reconstruction. No override flag turns this version into an eligible reference.

Downstream scoring must verify the qualification, not infer readiness from the
existence or internal status of the old reference. H1/H2 are not evaluable from
this run. Diagnostic agreement with its labels may be reported under that exact
name, without accuracy/effect/pass claims. H3 transport/native-contract checks
are independent of annotation balance. No qualification authorizes inference.

```bash
../../.venv/bin/python paired_reference_qualification_v1.py \
  --verify runs/2026-10-18-paired-reference-qualification-v1
```

A new versioned reference needs actual identity crossover across different
dependency families, paired/shared-family separation and appropriate independent
contexts. This failure is not repaired by relabeling actual agents as slots or
by overwriting the original evidence. Actual annotation infrastructure constraints
must be resolved before another reference execution is described as qualified.
