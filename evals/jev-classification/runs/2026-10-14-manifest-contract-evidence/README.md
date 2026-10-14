# Layer 1 — manifest contract/consumer evidence

This is the source-selection layer of a four-PR preparation stack. It freezes
four parser fragments, two document fragments and six consumer fragments for
one unchanged Python expression:

```python
path.is_absolute() or ".." in path.parts or value != path.as_posix()
```

The baseline is exactly the original-name parser view from the prior frozen
`packet-annotator-13.json`, probe-c. The architecture profile and rubric will be
held fixed in the packet layer. Source revision remains
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.

## Evidence boundaries

| Bundle | Contents | Purpose |
|---|---|---|
| Base | `_safe_path`, pathlib import, exception, `_manifest_files` | Hold the parser view fixed |
| Documents | Implemented proposal 0215 contract and operator artifact-authority guidance | Add the stated publication requirement |
| Consumers | Local manifest loading, prefix use, copy loop, HTTPS verification setup/body and workflow staging step | Add the actual path uses |

Consumer selections use exact function/statement spans. They are intentionally
bounded excerpts, not complete modules. Both manifest-row paths and the shared
`staging_prefix` use are visible. The workflow excerpt contains all three stage
calls and both workspace prefixes, following the PR #50 repair.

Documents are kept as document text with explicit source authority. They must
not be misrepresented as Python code or a canonical Requirement. The selected
predicate itself does not verify symlinks, hashes, public-safe content, manifest
membership, URL encoding or publication approval. Consumers performing other
checks do not expand the exact target's responsibility.

## Provenance and next layers

`evidence-bundles.json` contains byte-preserving selections with source revision,
path, line coordinates and file/excerpt SHA-256. `evidence-receipt.json` binds
all source audits, the unchanged prior parser packet and selected artifact bytes.
Apache 2.0 source attribution is preserved in `upstream-LICENSE.txt`.

The catalog is **integrator-only**. A future annotator receives its single
packet and blank template; never this catalog, the source audit's proposed
labels, study hypotheses, other cells or earlier results.

The remaining layers will freeze four conditions and twelve fresh-context
assignments, validate preparation/output provenance offline, then provide the
dispatch and manual-review handoff. No annotation or provider API call is
performed by any preparation layer. No reference/gold or production metrics
are changed.
