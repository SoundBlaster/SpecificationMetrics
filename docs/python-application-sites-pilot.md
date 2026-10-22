# Application-site pilot: SpecGraph #785–#787

## Frozen scope

Measured on 2026-10-22 using SpecGraph PR #787 head
`59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe`. The snapshot includes the #785
policy extractions and #786 provider contracts. It contains exactly the 17
tracked `.py` files under `tools/traceability/`, with no live-checkout changes.
This is a subsystem diagnostic, not a full-repository measurement or a PR delta.

The explicit source-role manifest was:

```toml
schema_version = 1
[[source_sets]]
role = "application"
paths = ["tools/traceability"]
```

Both `measure --require-complete` and `application-sites` used this snapshot
and manifest. Neither imports Python, runs the provider, or calls an LLM.

## Results

| Measurement | Value |
| --- | ---: |
| Raw Specification definitions, S | 11 |
| Raw remaining opportunities, U | 86 |
| Discovered candidates | 86 |
| Analyzed Python if candidates | 62 |
| Direct applications | 3 |
| Mixed expressions | 0 |
| Unresolved application calls | 0 |
| If candidates without examined application calls | 59 |
| Other discovered candidates outside this profile | 24 |

Both reports are non-provisional for the selected scope, with no scope,
parse or marker issues. Their source and scope digests match:

```text
source: 98ae2b305b90421439ae3ed2500a9cf46b5e11df0c5b82f135b8417b0eadf5e7
scope:  03a8c3926511442bff22019d279eb09892243a90069194076cfa4a846b948a9e
```

The direct applications are:

| Use at the pinned revision | Receiver | Resolved factory |
| --- | --- | --- |
| `tools/traceability/publication.py:319` | `POLICY_ATOM_BINDINGS_SPEC` | `policy_atom_bindings_spec.py:9:69` |
| `tools/traceability/publication.py:323` | `ATOM_ROLES_SPEC` | `atom_roles_spec.py:7:50` |
| `tools/traceability/publication_execution_provider.py:260` | `EXECUTION_BINDING_SPEC` | `execution_binding_spec.py:7:64` |

Factory paths in the last column are relative to `tools/traceability/`.
Columns are 1-based UTF-8 byte columns. Each factory is an imported synchronous
`specification_core.PredicateSpec`. The full JSON additionally retains the
existing candidate fingerprint and each call's source anchor.

## Interpretation and implementation correction

The first diagnostic attempt found the first two calls and left the third
unresolved because it rejected all class ancestors. Source inspection showed
that the third call is in a method and uses a module-level constant. Python
bare-name lookup in methods skips the class namespace. The implementation now
models that distinction, with a regression covering both method globals and
shadowing in an enclosing function.

The three guards remain in raw U=86 under counting rule v9. That is the
existing counting boundary, not a failed extraction: the new report now shows
their applications explicitly. This pilot does not establish an adjusted
U=83, semantic coverage, execution coverage, or permission to exclude them.

The 59 other if candidates are **not** 59 proven inline policies. V1 only
examines `.is_satisfied_by` calls; typed decisions and other styles need their
own diagnostic coverage. Likewise, zero mixed/unresolved cases in this small
scope is not a claim about the rest of SpecGraph.

## Reproduction

1. Materialize only `tools/traceability/**/*.py` from the exact Git revision
   above into an empty snapshot directory, preserving relative paths.
2. Save the manifest above outside that source directory.
3. Run both commands against the same snapshot:

```sh
specification-metrics measure SNAPSHOT --scope-manifest scope.toml \
  --require-complete --output primary.json
specification-metrics application-sites SNAPSHOT --scope-manifest scope.toml \
  --output applications.json
```

The absolute `root` changes across machines; selected-source digest, manifest
digest, counts, candidate fingerprints and relative anchors must agree.

Regression validation includes negative binding cases, condition/body isolation,
Boolean composition versus mixed syntax, and CLI measurement output identity.
The next useful extension is a separate typed-decision diagnostic, before any
proposal to change the denominator.
