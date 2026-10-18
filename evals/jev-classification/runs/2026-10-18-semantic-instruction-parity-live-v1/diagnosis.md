# Instruction-parity diagnosis

## Observed facts

The only native wire edits were question instructions: unchanged Sol semantic
guidance plus its category catalog were embedded into each question. All 16
new responses have verified local request/body/ledger/receipt consistency.
The old 16 responses and 24 Sol annotations remain immutable.

### Jev: support interpretation changed most

Five former `policy|mechanics + insufficient` conflicts became supported judgments:
R01 baseline, R02 both views and R03 both views. Existing Specification ownership
in R01 remained recognized in both views; parsing in R03 remained mechanics.
R04 baseline changed `unknown` to `policy`, adding one agreement but creating
the one remaining role/support conflict. Thus five old conflicts disappeared and
one new conflict appeared; the net conflict count fell from five to one.

R04 is the lexical path-admissibility rule from SpecGraph revision
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`,
`tools/product_workspace_next_moves_support.py:55–62`:

```python
def safe_workspace_path(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not (
        text.startswith(("/", "~"))
        or "\\" in text
        or ":" in text
        or ".." in PurePosixPath(text).parts
    )
```

It explicitly rejects forms of workspace paths. This does not establish symlink
containment, filesystem safety or ownership by an existing Specification. Sol's
role/support comparator is `policy/supported`, ownership unknown. Jev baseline
returns `policy/insufficient`; its native support distribution is insufficient
0.36, supported 0.34, limited 0.30, with provider confidence 0.04. The narrow
margin is a diagnostic, not calibrated error probability. Jev retrieval returns
`policy/supported`. The unchanged consistency Specification correctly routes
the baseline tuple to review; no label is repaired or probability renormalized.

### Luna Decision: more resolution, continued gaps

R01 baseline changed unknown → policy, but support stayed insufficient and
ownership stayed unknown, creating a new conflict. R01 retrieval changed
unknown/insufficient → policy/supported, while still missing explicit existing
Specification ownership. R02 retrieval kept policy/insufficient. R02 baseline,
both parsing views and both path views still abstain on role. Consequently
agreement rose but coherence fell from seven to six tuples. Agreement and
coherence are separate outcomes; neither should hide the other.

## Cause status and limits

**Confirmed pipeline asymmetry:** Sol previously received stronger guidance about
unresolved placeholders, whole-target judgment, caller/callee responsibilities
and missing definitions. The original rubric already contained the same labels.
This repeat transfers that guidance without changing the source state or Sol.

**Supported observation:** the new instruction condition coincides with a large
Jev agreement/coherence improvement and a smaller Luna agreement improvement.
The claim that Jev's earlier disagreements were solely intrinsic inability is
unsupported. The previous pipeline comparison did not isolate model capability.

**Not established:** which clause caused each change, whether placeholder anchoring
is the cause, whether internal question isolation causes contradictions, or how
these rates generalize. The catalog and semantic paragraph changed together;
provider backend/decoding revisions and stochastic/time effects are uncontrolled.
Sol's rationale/source-witness output also differs from native choice output.
Four targets are a development diagnostic, not a representative held-out sample
or semantic truth. R01's existing ownership is explicit; this cohort cannot
establish retrieval's ability to discover hidden ownership.

## Prevention and next experiment

Keep a shared semantic task and versioned per-provider rendering. Before using
model comparisons to justify backend architecture, audit task/rubric/evidence
parity. Record rendered-wire hashes and preserve prior failures, raw labels,
abstentions, coverage, consistency and token cost separately. No instruction should
contain author labels or newly inferred ownership.

The larger backend refactor is still deferred. A useful next diagnostic is a
frozen clause/catalog ablation that reduces repeated instruction tokens while
checking the observed Jev gains and the residual R04 conflict. Do not launch more
paid calls or rerun Sol implicitly. Hold state placeholders fixed in that ablation;
their removal is a distinct experiment.

## Replay portability defect discovered during preparation

PR #78 CI failed in exact comparison equality. The recorded comparison contains
analysis-host Python/dependency fingerprints as well as captured execution
inventories. The inspector deliberately allows analysis on another runtime, but
the test demanded those current-host diagnostic fields equal the historical host.

The narrow fix removes only `analysis_runtime_inventory`,
`analysis_runtime_matches_execution` and each row's analysis-time
`adapter_producer_sha256` from cross-host equality. Frozen files and their receipt,
captured execution inventory, portable producer sources, wire/body identities,
native outputs, labels and scoring stay strict. All diagnostics remain in reports.
No old producer source or historical receipt was edited. Tests simulate host-only
differences and reject execution/label mutations. The fixed test was pushed to
the existing PR #78 before the new experimental PR.
