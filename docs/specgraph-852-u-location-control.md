# SpecGraph PR 852: U location and interpretation control

This record uses the historical report for [SpecGraph PR 852](https://github.com/0al-spec/SpecGraph/pull/852),
not a measurement of its evolving branch. On 2026-10-31 the published
[comment](https://github.com/0al-spec/SpecGraph/pull/852#issuecomment-6545721491)
and the six files in the [CI artifact](https://github.com/0al-spec/SpecGraph/actions/runs/41217049458/artifacts/13048817262)
were inspected. Its `provenance.json` identifies:

- Base: `e1fbacd02d5be1201109f480bdd3c1d55f8e6e18`.
- Head: `219e674f0ec6df514bbe1bae6a491bde4f07a31a`.
- Analyzer: `332348dc86ebd9cfc9d1db15c37afbae9c2546d0` (counting rule v10).
- Collection run: `41217049458`, attempt 1; upstream CI: `41216459837`.
- Collection contract in the comment: `6553cfdaacef` (displayed prefix).

## Observed measurement

| Metric | Base | Head | Delta |
| --- | ---: | ---: | ---: |
| S | 130 | 130 | 0 |
| U | 10676 | 10697 | +21 |
| Python CC sum | | | +42 |
| Python Cog sum | | | +46 |
| Python SLOC | | | +141 |

Both collections are complete and the primary results are not provisional.
The JSON contains 23 added locations, 2 removed locations and no ambiguous
groups. Added locations split into 1 in `tools/artifact_json.py`, 14 in
`tools/publication_path_coverage.py` and 8 in
`tools/static_artifact_incremental_stage.py`. Both removed locations are in
the last file. The full inventory, rather than the truncated comment, gives:

```text
Location comparison complete.
Added 23, removed 2, ambiguous groups 0 (contribution to ΔU: +0).
Total ΔU: 23 − 2 + (+0) = +21.
```

The comment displays at most 20 location rows. That display limit must not
change the totals. These are changes to the syntactic candidate inventory;
an edited condition can appear as a removal and an addition. The 23 additions
do not establish 23 independently introduced business rules.

## Proposed interpretation, pending semantic adjudication

The PR describes an opt-in capture of observed HTTPS paths and an offline
audit against retained build and deployment evidence. That intent supplies
context for interpreting the branches. The following examples come from
[`publication_path_coverage.py` at the measured head](https://github.com/0al-spec/SpecGraph/blob/219e674f0ec6df514bbe1bae6a491bde4f07a31a/tools/publication_path_coverage.py).

| Location | Concrete code | Proposed interpretation and reason |
| --- | --- | --- |
| L15 | `if not isinstance(rows, list)` | Mechanics: input shape validation before decoding records. |
| L22 | `if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)` | Mechanics: lexical validation of a SHA-256 representation. |
| L56 | `if run_id is not None and (execution["provider"], execution["run_id"]) != ("github_actions", run_id)` | Policy candidate: defines which execution evidence may support this requested audit. |
| L74 | `if any(receipt[key] != witness[key] for key in ("execution_context", "remote_base_url", "attempt"))` | Policy candidate: defines the required shared provenance of receipt and observations. |
| L83 | `"verified" if not (errors or missing or extra) else "unverified"` | A composition/use of earlier checks: first inspect whether an existing decision already expresses this result; it does not by itself justify a wrapper Specification. |

The distinction depends on the decision's intent, not the presence of `if`,
`not` or several boolean operands. A lexical check becomes a policy if product
intent gives it independent acceptance semantics. Likewise, matching two
values can enforce a trust boundary even though the operation is mechanical.
For the proposed policy candidates, inspect the governing spec/proposal and
existing Specifications before deciding whether to reuse a rule, compose
existing rules or introduce a named policy with its own tests.

These are author-proposed interpretations of selected sites, not independent
gold labels, classifier results or a complete classification of all 23 sites.
The report supplies coordinates and provenance; it does not automatically
exclude mechanics from U or count policy candidates as S. No SpecGraph
implementation changes follow from this record.

## Regression use

The CLI integration test in `tests/collection_cli.rs` creates a synthetic
2 → 23 inventory comparison. It checks the same 23 − 2 + 0 = +21 arithmetic,
the explicit ambiguous-contribution label and the 20-row truncation. Its
existing repeated-condition case checks a negative ambiguous contribution.
This tests reporting behavior, without claiming to replay or adjudicate the
historical source. The historical artifact remains the source for the real
PR numbers and coordinates.
