# Real SpecGraph context-evidence preparation

**Status: prepared; independent annotation pending; no executable provider run.**

This packet follows the withheld-context failures recorded in
[PR #40](https://github.com/SoundBlaster/SpecificationMetrics/pull/40). It changes
the evidence intervention from authored scenarios to exact production source.
It is a purposively selected development diagnostic, not a random sample or a
confirmation holdout. No expected labels or provider predictions are included.

## Six source targets

Source: `0al-spec/SpecGraph`, full commit
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.

| Target | Declaration | Selected expression |
|---|---|---|
| target-01 | `tools/spec_yaml.py:dump_canonical_yaml` | `not rendered.endswith("\n")` |
| target-02 | `tools/static_artifact_incremental_stage.py:_safe_path` | `path.is_absolute() or ".." in path.parts or value != path.as_posix()` |
| target-03 | `tools/evidence_claim_gate.py:source_claim_reason` | `not requested <= covered` |
| target-04 | `tools/ontology_term_binding_gate.py:_has_reviewable_gap` | `gap.get("canonical_mutations_allowed") is not False` |
| target-05 | `tools/product_workspace_next_moves.py:candidate_move` | `gate != "none"` |
| target-06 | `tools/native_bdd/values_spec.py:BDDScenarioValuesSpec.findings` | `not entry.steps_is_list or not entry.steps` |

The selection spans representation, path validation, source evidence, ontology
review, action selection and an existing Specification. These descriptions are
sampling rationale, **not assigned concern-kind/opportunity labels**. Path safety
can have architectural meaning; validation is not automatically mechanics, and
existing Specification ownership must be supported by the supplied evidence.

## Three evidence views per target

1. **Expression only:** the exact expression and architecture profile/rubric.
2. **Containing declaration:** the full source function/method containing it.
3. **Evidence bundle:** exact selected imports, declarations, typed data or direct
   consumer/helper code in addition to the target. For the BDD case this includes
   the enclosing class and the Specification base's evaluation path.

Every view preserves the same target bytes. There are **18 annotation cases**;
IDs are deterministically shuffled, with view/target identities kept outside
the provider state in [source-mapping.json](source-mapping.json). Native code
names and comments remain intact. The views are related observations, not 18
independent code families.

The selected bundle is **not assumed semantically complete**: unlisted callers,
dependencies and runtime bindings remain unproved. Neither a minimal view nor
an enlarged bundle automatically determines a label. Independent annotation
must decide each axis from the supplied evidence and preserve uncertainty.

## Artifacts and verification

- [selectors.json](selectors.json): explicit paths, scopes, expressions and
  supporting declarations; no semantic labels.
- [source-evidence.json](source-evidence.json): unmodified source quotes with
  file/fragment/expression hashes and UTF-8 byte/line spans.
- [case-packet.json](case-packet.json): the isolated annotation packet, with no
  author proposals, source-mode mapping or provider predictions.
- [annotation-template.json](annotation-template.json): blank labels, evidence
  quotes and uncertainty fields. This file is not an accepted reference.
- [preparation-receipt.json](preparation-receipt.json): producer/input/artifact
  digests; zero inference and zero metric effects.

Full files and fragments were verified against the pinned Git commit during
preparation. Offline replay checks saved fragment/target integrity and exact
artifact reproduction; full Git verification is a separate explicit mode.
No source was executed or edited. Context is bounded to 8 KiB of code and
16 KiB per canonical state. Oversized or ambiguous selections fail visibly;
they are never silently truncated.

From `evals/jev-classification`:

```sh
python3 prepare_context_evidence.py
python3 prepare_context_evidence.py --source-repo /path/to/SpecGraph
python3 -m unittest -v test_prepare_context_evidence.py
```

Default and verification modes are offline and do not write artifacts. New
preparation uses `--collect --write --source-repo ... --run <new-directory>` with
explicit selectors and refuses existing preparation outputs. Reusing this
completed preparation as a mutable scratch directory is not supported.

## Next experiment and failure learning

1. Independently annotate only the packet and blank template, without this
   sampling rationale, mapping, source selectors or previous provider results.
2. Review disagreements and distinguish evidence insufficiency from a genuinely
   interpretable minimal expression. Do not force every smaller view to unknown.
3. Freeze a new provider protocol after the reference is reviewed. Keep raw
   model judgments and any formal context-evidence gate as separate experiment
   arms. Do not claim a gate override improved raw Jev/Luna classification.

The root cause of the original semantic failure is still unresolved. This packet
is the discriminating investigation; it is not a semantic fix, new classifier
default or authority to perform inference. See [failure-learning.md](../../failure-learning.md).

## Source attribution

Unmodified excerpts originate from SpecGraph at the commit above and are
licensed under Apache-2.0. The upstream [license](upstream-LICENSE.txt) is included;
the copied excerpts retain that license. Selection, metadata and evaluation
tooling do not relicense the upstream source. No upstream NOTICE file was present
at that revision.
