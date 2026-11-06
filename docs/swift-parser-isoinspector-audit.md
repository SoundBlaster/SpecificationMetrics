# Swift parser audit: ISOInspector

Compare source revision `14c161f6d3989f18e1a4d4c3af2bb495ea8b8c38`
in [SoundBlaster/ISOInspector](https://github.com/SoundBlaster/ISOInspector/tree/14c161f6d3989f18e1a4d4c3af2bb495ea8b8c38).
The cohort is `Sources/` and `FoundationUI/Sources/`, with tests and all
other paths excluded. Source digest is
`fabfcdff8d1642ab61e2f51796aadcfdd1b9234cb157c0b5feb053521afa0b71`.
The old analyzer is `38091108bc18056e345599ed8eb14bd0fb9e563a` (rule v10,
tree-sitter-swift 0.7.3); the new analyzer uses rule v11 and grammar 0.7.4.
Both snapshots have the same source revision, source digest and scope digest.

| Observation | v10 / 0.7.3 | v11 / 0.7.4 |
| --- | ---: | ---: |
| Application files | 290 | 290 |
| Files with parse diagnostics | 12 | 3 |
| S | 0 | 0 |
| U | 2120 | 2120 |
| U locations/fingerprints added / removed | — | 0 / 0 |
| Provisional | yes | yes |

All 12 files flagged under 0.7.3 were also checked using `swiftc -frontend
-parse` from Apple Swift 6.4 on macOS; all exited zero. This establishes
syntax acceptance by that compiler, not type checking, successful building or
cross-version compatibility. It supports classifying the flagged syntax as a
grammar limitation rather than an established ISOInspector defect.

The old grammar flagged, among other constructs, `as? Bool ?? true`,
`as? [String: Any] ?? [:]`, `#if` declarations inside types and multiline
binary operators. The 0.7.4 grammar parses the nine affected files without
errors. Regression tests cover conditional members and optional-cast
coalescing, while preserving ordinary decision discovery.

Three files remain flagged on `@available(...) #Preview(...)`:

- `FoundationUI/Sources/FoundationUI/Components/Badge.swift:237`
- `FoundationUI/Sources/FoundationUI/Components/Card.swift:416`
- `Sources/ISOInspectorApp/ResearchLogAuditPreview.swift:147`

The parser diagnostic is deliberately retained, and the collection remains
provisional. The regression test requires that boundary. No source change or
reformatting is requested from ISOInspector solely to improve this metric.

Equal U totals and recorded fingerprints are evidence for this particular
cohort only, not proof of unchanged counting behavior for every Swift project.
The global counting-rule version changes because a grammar update can change
the syntax tree. Historical v10 snapshots are preserved and cannot be
automatically compared under the v11 collection contract.
