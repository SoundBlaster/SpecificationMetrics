# Paired retrieval scoring v1

## Frozen scope and authority

This contract is fixed before observing responses to the frozen paired provider
schedule: 4 targets × 2 views × 2 providers = **16 logical responses**, reserving
at most **48 attempts** including initial attempts. Each provider has 8 response
slots, 32 axis slots and 4 target pairs. Providers are always reported separately.
No pooling of axes as independent samples, prompt tuning, relabeling or automatic
fact acceptance follows from this report.

The mandatory [reference qualification](paired-reference-qualification-v1.md)
currently rejects the eight-agent reference design. Therefore this scorer's real
H1/H2 outputs are **`not_evaluable_reference_design`**. The old provisional
reference status cannot override that decision. A new balanced reference needs a
new qualification/scoring version; no CLI switch enables it here. Existing labels
remain usable for expressly named **diagnostic label agreement**, not accuracy.
H3 measures operational evidence independently of that design failure.

## Denominators, missing responses and unknowns

| Item | Rule |
|---|---|
| Planned responses | Fixed at 8 per provider / 16 overall |
| Verified rows available | Only rows reconstructed by the local transport inspector; not a claim about how many requests physically executed |
| Native valid/invalid | Separate counts; invalid native envelopes are not wrong domain labels |
| Category consistency | Count `needs_review` separately; do not correct raw labels |
| Diagnostic agreement | Exact categorical matches out of 4 × native-valid rows; show the planned 32 axis slots alongside that conditional denominator |
| Confusion counts | Each axis's reference-label → predicted-label counts, including unknown |
| Absent/incomplete evidence | Report not-evaluable/coverage status; never turn missing rows into correct, incorrect, or definitely-unsent requests |
| Unknown | Unknown matching unknown is categorical agreement, not absence or a supported positive resolution |
| Zero denominator | `null` value and not-evaluable status, never zero accuracy or success |

For example, 7 native-valid responses can supply 28 compared axis slots, but the
report still says 8 planned responses and 32 planned axis slots. It does not hide
the unavailable eighth response. Category-valid but inconsistent answers may
appear in diagnostic confusion counts; they cannot contribute H1/H2 performance.
Numeric provider confidence and similarity scores do not affect these counts.

## H1 — supported fact resolution

The arithmetic is implemented and tested on **synthetic qualified fixtures**.
The real CLI does not apply it to the current unqualified reference.

For each complete, coherent, unambiguous target/provider pair and each arm:

1. Role resolution = 1 iff the view reference has a non-unknown role with
   `supported` evidence, the prediction has that role and also says `supported`.
   `limited` support receives no positive-resolution credit.
2. Ownership resolution = 1 iff the view reference establishes a non-unknown
   owner and the prediction matches it. Unknown ownership yields zero resolution
   credit even when it is an appropriate categorical answer. Role support is not
   silently reused as an ownership-confidence score.
3. Compute the retrieval-minus-baseline difference for each of these two fact
   units. Report gains and losses separately, then their net sum.
4. Divide the net by the number of adjudicable **target pairs**: those with at
   least one supported role or known ownership in either view. Conflicting known
   reference values require adjudication and are rejected. No adjudicable pairs
   means not evaluable.

The mean is **net supported fact resolutions per target pair**, in [-2, 2], not
an accuracy percentage. Positive net supports H1 within this pilot; zero or
negative net does not. H2 remains a separate no-regression criterion. An
appropriate baseline abstention can be categorically correct while retrieval
adds a justified fact. Partial/incoherent observations never select a convenient
subset of pairs: H1/H2 require the complete provider schedule and prerequisites.

## H2 — no newly unsupported ownership assertion

An ownership assertion is unsupported **in the supplied view** when it is
non-unknown and differs from that view's qualified reference. This is not proof
that no matching Specification exists anywhere in the repository.

A new unsupported retrieval assertion occurs if retrieval is unsupported and
baseline either was not unsupported or asserted a different owner category.
Thus changing one unsupported category to another does not disappear from the
new-assertion count. The same unsupported category in both arms is not new, but
remains visible in each arm's absolute unsupported flags and confusion counts.
H2's pilot no-regression criterion is zero new assertions, reported over all 4
target pairs per provider. Do not infer general safety from four examples.

## H3 — operational eligibility

The scorer calls the existing inspector on the original run, not on an
operator-selected JSON inspector report. The inspector reconstructs exact
manifest/wire/body/ledger/receipt bindings and native responses.

- All 16 responses verified, native-valid, no ambiguous posts or duplicate
  execution: `passes_pilot`.
- Complete evidence with ambiguity or native invalidity: operational failure.
- Incomplete run with a recorded stop reason: incomplete-execution failure.
- Missing/incomplete evidence without a verified stop reason: not evaluable;
  it does not prove no inference or billing occurred.

The full inspector evidence and producer/runtime inventories remain in the score
report. Native mass warnings are retained by the adapter under its frozen
contract, without re-normalization. H3 success says nothing about semantic
accuracy or reference qualification. This is local consistency, not provider
authentication or remote attestation. No report changes S/U, accepted Facts,
write authority or merge readiness.

## Commands and reproducibility

```bash
cd evals/jev-classification
../../.venv/bin/python paired_retrieval_scoring_v1.py --verify-contract

# Offline after an execution has been captured. Output must be a new path.
../../.venv/bin/python paired_retrieval_scoring_v1.py \
  --run /path/to/captured-run --output /path/to/new-score.json
```

The checked-in contract pins preparation/reference/qualification hashes, four
questions, denominators and the local producer import closure. Verification
reconstructs it rather than trusting edited metadata/checksums. Reports retain
native probabilities and operational observations through the embedded inspector
evidence. Existing run/refinement artifacts remain unchanged. This tool makes no
network requests or new model calls; exit 0 means the report was constructed,
not that a hypothesis passed. Bad provenance/inputs fail visibly.

Regressions cover justified abstention, positive resolution gains, limited/empty
support, missing/invalid/incoherent responses, old/new unsupported ownership,
identity conflicts, contract tampering and a full synthetic transport chain:
H3 can pass while H1/H2 remain blocked by the actual reference design.
