# Independent Astra Medium review of real decision-flow examples

## Scope and qualification

One new subagent, configured as **gpt-6-astra / medium**, with
`fork_turns: none`, reviewed all **29 cases** (19 authored families) from the
real-source corpus. Input contracts came from Metrics revision
`8165dd6620a09582dcd27332cedd8df71ac95cc5`, before the clarifications below.

The reviewer received exact source excerpts, 38 full pinned source files,
explicit import roots and two written contracts. Its packet omitted author
expectations, semantic labels, rationales, family/tier labels, old analyzer
results and conversation history. The reviewer was instructed to read only
that packet, not the implementation or repository labels; it reports doing so.
The filesystem was shared: this is instruction-based access separation,
**not an OS-enforced blind-review sandbox**.

The reviewer did not run the analyzer or execute/import source projects. It
used source/contract reading and digest verification only. The main agent
checked all 41 input-file hashes before and after review and required all
29 unique, matching case IDs before comparing the two labels per case.

## Results

| Comparison with frozen author labels | Agreement |
| --- | ---: |
| Call category | 29 / 29 |
| Flow status | 29 / 29 |
| Cases requiring label adjudication | 0 |

Independent categories: **6 direct, 1 mixed, 16 unresolved, 6 absent**.
Independent flow statuses: **1 linked, 8 unresolved, 14 no immediate binding,
6 outside API**. Reasons are free-text judgments; the agreement comparison
covers category and status, not equality of rationale wording or internal
analyzer reason codes. Family labels were joined only after review.

Agreement confirms one independently obtained reading of the bounded contract.
It does not establish population precision/recall, independent statistical
observations, runtime correctness, semantic coverage or eligibility to exclude
opportunities from U. The corpus still has just one accepted link and no real
`not_linked` example. It remains development data reviewed by one model, not
human gold or a held-out benchmark.

## Findings and disposition

### 1. `assert` was not an explicit barrier

Case `specgraph-01`, source `tools/idea_to_spec_promotion_gate.py:213–215`:

```python
    result = _PRE_SIB_STATE_DECISION.decide(context, recorder=recorder)
    assert result.matched and result.value is not None
    return result.value
```

Astra chose `direct_application / unresolved` but marked its confidence medium
because the permitted subset excluded `assert` only implicitly. Source review
confirmed that the analyzer stops on this statement; the existing
`barriers_and_unsupported_conditions_never_create_links` regression already
contains `assert value`. **Disposition:** name `assert` explicitly in the flow
contract and say that its success is not a supported if-candidate link.

### 2. Inventory presence and supported scope were conflated

Cases `specgraph-02`, `specgraph-03`, `specgraph-04` assign a result to an
identifier inside a loop. They are inventoried, but their scopes do not support
a link. The phrase "unresolved or outside the immediate-identifier inventory"
did not say which alternative applied. **Disposition:** distinguish the
identifier-origin inventory from supported direct-function-body scope. Nested,
module/class and global/nonlocal origins retain unresolved rows; calls without
an immediate identifier origin remain in the call inventory only.

The existing `scopes_unknown_origins_raw_truthiness_and_missing_uses_remain_explicit`
regression already covers the distinction for nested/module/global scopes.
No analyzer behavior, counting rule or frozen label changes are needed.

### 3. Useful boundaries confirmed

- Obvious local FirstMatch constructors still exceed the module-constant
  resolver contract; visible Python types are not a reason to label them direct.
- Direct local consumption and branch-flow provenance are separate questions.
  Passing a result as an argument can be direct consumption without a flow row.
- cctally's unrelated `.decide` remains inventoried but unresolved. Ordinary
  Flask/FastAPI snippets have no `.decide` call and remain outside the API.

## Retained evidence

- [independent-labels.json](independent-labels.json): exact raw reviewer output,
  including its access statement, evidence, confidence and contract findings.
- [comparison.json](comparison.json): two-axis comparison and raw-output hash.
- [review-request.json](review-request.json): requested configuration, packet
  receipt hash, allowed access and comparison scope.
- [packet-receipt.json](packet-receipt.json): original input filenames/hashes and
  source corpus hash; full source files remain recoverable from pinned Git blobs.
- [input-contracts.json](input-contracts.json): exact pre-clarification contract
  texts, keyed by the original packet filenames. Decode each JSON string and
  encode UTF-8 to verify its receipt hash; retain the original terminal blank
  lines. The JSON container avoids treating frozen input payloads as current
  Markdown documents or rewriting their whitespace.

The neutral `cases.json` input can be reconstructed from the frozen corpus:
retain `id`, `project`, `path`, `analysis_path`, `call_anchor`, `excerpt`; rename
`excerpt_lines` to `inspection_lines`; retain snapshot fields `repository`,
`revision`, `import_root`, `files`. Serialize with Python
`json.dumps(..., indent=2) + '\n'`, preserving original field/project/case order.
The full packet and verified original source material remain in the run-specific
TB5 artifact directory. No old corpus or assessment bytes were changed.
Their original `independent_review_pending` status is historical preparation
metadata; this additive review record reports the later completed review.

## Verification

- All 29 reviewer IDs are unique and match the original corpus exactly.
- Raw-review, packet-receipt and original-corpus hashes match their receipts.
- The neutral cases input reconstructs byte-for-byte to its packet hash.
- All 41 input hashes were unchanged before/after the agent's review.
- Original corpus and first-assessment bytes match `main` exactly.
- Five focused Rust decision-flow regressions and five Python replay-harness
  checks passed. No analyzer code or model/provider adapter was changed.

Next: test bounded support for loop-local origins and verified enum-member
comparisons using the two unchanged SpecGraph examples; keep U exclusion
separate from this diagnostic work.
