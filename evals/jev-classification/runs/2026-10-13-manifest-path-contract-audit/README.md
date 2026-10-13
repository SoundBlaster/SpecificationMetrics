# Manifest-path contract recovery

## Result and authority

The missing evidence exists in SpecGraph's **implemented proposal 0215** and
its publication consumers. It was omitted from the annotation packets, not
demonstrated absent from the repository.

Source revision: `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`, fetched `main` on
2026-10-13 and the same revision used by the frozen experiment. The selected
helper's whole-file SHA-256 and exact excerpt match the original source audit.

The proposed classification with this recovered evidence is
**`eligible / policy`**, specifically publication-namespace path admissibility.
This is an **integrator inference**, not a new independent annotation, adopted
gold label or metric update. The prior sixteen `needs_review / unknown` answers
remain unchanged. No new inference agents or provider calls were launched.

There is no canonical Requirement ID claimed by this audit. A bounded keyword
search under tracked `SPECS/` found no direct static-manifest/path-traversal
contract reference; this is not proof of semantic absence across all specs.
The implemented proposal, runtime registry, documentation and tests provide
source-grounded design evidence without being promoted to canonical authority.

## Exact target

```python
path.is_absolute() or ".." in path.parts or value != path.as_posix()
```

The target remains the entire Boolean expression in `_safe_path`, including
canonical spelling. It is not silently replaced with only the traversal clause
or with the entire publication workflow.

## What supplies the contract

### 1. A stated publication requirement

[Proposal 0215](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/docs/proposals/0215_incremental_static_workspace_deployment.md#L17-L73)
is marked as an implemented bounded optimization. Its acceptance criteria say:

> Path traversal and local digest mismatches fail closed.

It also requires changed payloads to retain relative durable URL paths. Its
authority boundary forbids publishing files absent from a public-safe manifest;
remote manifests are planning hints rather than final publication authority.

The [operator documentation](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/docs/static_artifact_publish.md#L38-L62)
states that the manifest/checksums are the authoritative artifact index, while
files left in the shared webroot need not remain authoritative.

These are concrete contracts concerning the publication surface. The word
`unsafe`, a helper name or an import alone would not establish this role.

### 2. The checked strings become actual publication paths

The call chain is visible in
[the staging tool](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/static_artifact_incremental_stage.py):

```text
local or remote artifact_manifest.json
  → _manifest_files: _safe_path(row["path"])
  → local: bundle_dir / relative_path, file existence and SHA-256
  → changed local payload: staging_dir / prefix / relative_path
  → HTTPS verification: base_url / relative_path
```

`stage_changed_files` also calls the same helper for `staging_prefix`; the
workflow passes fixed workspace prefixes for two separate bundles. The helper's
role therefore covers publication path and prefix admissibility, not exclusively
manifest-row parsing. This shared use must remain visible in a future packet.

Local manifest entries determine copied payload. Remote-only entries contribute
to the removed-path report, not to extra local payload publication. Neither the
selected predicate nor a remote manifest grants publication authority by itself.

### 3. Producer and test evidence agree with the path role

The bundle producer generates relative POSIX paths and puts copied-file entries
into `manifest.files`. `iter_publish_sources` separately filters symlink
components in its ordinary source enumeration. This is another responsibility,
not protection implemented by the selected predicate.

`test_stage_rejects_unsafe_manifest_path` supplies `../private` and expects
`IncrementalStageError`. Another test checks that changed payload is copied to
`stage/workspaces/example/runs/b.json`. These tests document traversal rejection
and scoped destination composition. They were inspected, not rerun by this
research task, and do not constitute a complete path-security proof.

The proposal's runtime registry lists the exact tool, tests and workflow as
its implemented surfaces; its promotion registry records the originating draft
and bounded scope. Tracking is provenance, not a canonical Requirement link.

## What this changes for interpretation

| Evidence layer | Established fact | Remaining limit |
|---|---|---|
| Original packet | Lexical absolute/traversal/canonical-spelling rejection during manifest parsing | Why these restrictions govern this product surface was not supplied |
| Implemented proposal | Publication requires fail-closed traversal rejection and stable relative URL paths | Does not independently specify every canonical-spelling edge case |
| Consumers | Accepted paths select bundle input, staging destinations and HTTPS artifact addresses | The predicate does not select public-safe content or authorize publication |
| Producer/tests | Relative path production, a traversal-rejection test and scoped-copy test | Does not prove all runtime path-resolution or URL behavior |

Under the frozen rubric, a permitted-reference contract can establish
path-integrity policy even inside a parser. The recovered proposal and consumers
now supply that positive witness. The proposed `eligible` concerns defining a
named admissibility rule: the inspected helper path shows no Specification
evaluation ownership of this same decision. This is not a claim that no owner
exists anywhere else in the project.

Two ambiguities still deserve independent review:

1. **Canonical spelling is part of the exact target.** `value != path.as_posix()`
   rejects representations such as duplicate separators and `./`. It helps keep
   path keys and generated paths consistent, but this purpose is an implementation
   inference; proposal 0215 does not explicitly require each spelling restriction.
   A reviewer must decide whether the whole expression has a settled primary
   admissibility contract or retains materially mixed policy/mechanics roles.
2. **Generic helper versus contextual policy.** The implementation is generic
   lexical path validation and is reused for the workspace staging prefix.
   Its publication-specific use and stated contract support policy classification
   here; generic reuse alone neither proves nor disproves that classification.

The audit does not settle those questions by changing target boundaries or
making the desired label a new acceptance criterion.

## Operational limits and verification

The helper establishes lexical properties. It does **not** resolve symlinks,
prove physical filesystem containment, encode a URL, check allowed file roots,
verify file digests or make a file public-safe. Some of those responsibilities
are implemented elsewhere. No exploit or end-to-end deployment defect is
claimed by this audit.

Using the Metrics repository's Python 3.10 environment, an offline check compiled
only the pinned `_safe_path` function AST, supplying `PurePosixPath`, `Any` and
its exception. The source module was not imported and no network/deployment code
ran. All eight expected observations passed:

| Input | Result |
|---|---|
| `runs/a.json` | Accepted unchanged |
| `workspaces/team-decision-log/runs/a.json` | Accepted unchanged |
| `/runs/a.json` | Rejected |
| `../private` | Rejected |
| `runs/../private` | Rejected |
| `runs//a.json` | Rejected |
| `./runs/a.json` | Rejected |
| `runs/a.json/` | Rejected |

[source-contract-audit.json](source-contract-audit.json) preserves seventeen exact
excerpts from ten files, line ranges, full-file/excerpt SHA-256, commit permalinks,
search scope, verification observations and advisory status. Every saved excerpt
was checked against its pinned Git object; the copied Apache 2.0 license is
included in [upstream-LICENSE.txt](upstream-LICENSE.txt).

## Lesson and next diagnostic

The confirmed context-construction omission was stopping at parser neighbors:
`_safe_path`, an import, its exception and `_manifest_files`. Those fragments
did not contain the documented publication requirement or the path consumers.
The prior abstentions were appropriate to that bounded evidence; they are not
demonstrated classifier failures.

For contract-sensitive candidates, collect three separate witnesses:

1. The exact expression and its immediate implementation.
2. A source-grounded statement explaining what references the subsystem permits.
3. The consumer showing how the accepted value is used.

Keep the authority level of each witness explicit. A requirement can be a
documented implemented contract without a canonical ID; an ID must not be
invented to make the packet appear stronger. Supplying only additional code
does not guarantee that normative context has been recovered.

A useful next experiment would cross **documented contract present/absent** with
**path consumers present/absent**, holding the original expression, base packet,
rubric, profile and names fixed. Use four cells with three fresh contexts each
(twelve contexts, one target per context). Include the shared staging-prefix use
in the consumer bundle. This isolates contract evidence from ordinary code
expansion and avoids cross-case leakage.

Before dispatch, freeze those packet bytes and criteria: report raw per-axis
distributions; require supported path-role explanations; reject any claim that
the lexical predicate itself verifies symlinks, digests, manifest authority or
publication approval. An `unknown` answer remains allowed when the whole-target
primary role is materially unsettled. No packets or new labels are dispatched
by this audit, and no prior result or S/U counter is changed.
