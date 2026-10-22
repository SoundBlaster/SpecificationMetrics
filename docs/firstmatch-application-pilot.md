# FirstMatch pilot: SpecGraph #787

Measured offline on 2026-10-22 at revision
`59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe`, with profile
`specification-metrics.python-decision-applications/v1`.
No SpecGraph changes or provider/execution/coverage claims.

## Preserved stages

| Files and measurement root | Calls | Direct | Mixed | Unresolved |
| --- | ---: | ---: | ---: | ---: |
| Original 17 `tools/traceability/*.py`; repository root | 3 | 1 | 0 | 2 |
| 27 files adding `tools/publication_evidence/*.py`; repository root | 3 | 1 | 0 | 2 |
| Same 27 files; explicit `tools/` import root | 3 | 2 | 1 | 0 |

Confirmed causes: two definitions were initially outside scope. Adding them was
insufficient under repository-relative `tools.publication_evidence` names:
application imports use `publication_evidence.*`. Selecting the actual import
root resolves them. The regression
`nonstandard_import_root_must_be_selected_explicitly` records this boundary.
These are different contracts, not a quality-improvement delta.

Final manifest, relative to `SpecGraph/tools`:

```toml
schema_version = 1
[[source_sets]]
role = "application"
paths = ["traceability", "publication_evidence"]
```

```text
source_digest: 298755afd8a37fc2c9e0771254a3e15c1ff03afb820095d75c86e0bbc8041d87
scope_digest:  62ddbbda5e48f7dca782fb30f078b8774c2cc1de898d4b4ed0ec65d08636fc54
```

Primary/diagnostic digests agree. Both final reports are non-provisional with no
role/parse/marker issues. Raw S/U is **23/89** in this scope; the original
17-file scope remains **11/86**. Call counts do not adjust either metric.

## Real examples

Paths relative to the final import root at the pinned revision:

| Site | Observation | Factory target |
| --- | --- | --- |
| `traceability/publication.py:238:21` | Direct `.value` binding to `binding_error` | `publication_evidence/bindings_spec.py:7:62` |
| `traceability/publication_execution_provider.py:138:9` | Mixed `.value if matched else None` | `publication_evidence/suite_spec.py:7:54` |
| `traceability/references.py:68:44` | Direct `.value` argument to ReferenceResolution | `traceability/reference_status_spec.py:7:58` |

All resolve to FirstMatch.with_fallback. Mixed means additional result gating,
not bad code or a proven policy leak. The later `if binding_error` is not linked
by this syntax-only profile.

## Verification

Materialize the tracked Python files from the exact Git revision, preserve their
bytes/relative paths, choose the documented root and manifest, then run
`application-sites --profile python-decisions-v1` and `measure --require-complete`
against that same snapshot. Snapshot IDs/digests must agree across machines;
the absolute root may differ. Earlier scopes remain separate artifacts.

The original 17-file Boolean-if JSON was byte-identical before/after the change.
CLI regressions preserve default/explicit python-if-v1 output and primary
measurement bytes. Tests cover factories/fallbacks, aliases/re-exports, wrong
method combinations, missing scopes, import roots, shadowing, cycles, mutation,
deferred expressions, parse issues, consumption shapes and snapshot-bound IDs.
