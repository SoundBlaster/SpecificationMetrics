# Source-bound conditional action v2

Active preparation for live execution: v2 supersedes the retained, **unexecuted**
v1. Review [P1 in PR64](https://github.com/SoundBlaster/SpecificationMetrics/pull/64#discussion_r4284229650)
correctly identified that a free-standing `_evaluate` snippet did not prove its
membership in `BDDPolicy`. V1 AST shape checks alone could not establish that claim.

V2 captures contiguous `policy.py`, `values_spec.py` and `composition.py` from
SpecGraph commit `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`. Offline verification
pins the snapshot SHA-256, each file SHA-256 and Git blob SHA-1. It locates
`BDDPolicy` in the module and `_evaluate` directly in that class, compares the
method AST to fragment-03, and also binds the base prefix, child class, membership
and consumer loop to their contiguous declarations. Path/symbol/source span/digest
bindings are included in the witness. Source facts and verdict are unchanged.

A negative regression relocates the same method body to another class: the
original free snippet still has the expected AST shape, but v2 refuses the
witness. Snapshot tampering and stale source/wire identities are rejected.
This is static evidence, not runtime execution or a general Python resolver.

The 18-request / 54-attempt budget, three Choice axes, known development premises,
and preregistered H1/H2 criteria are unchanged. The eight baseline and eight
conditioned wires remain byte-identical to v1; only two ownership-witness wires
gain source-containment provenance. Old v1 source and preparation remain intact
for reproducibility; do not select v1 as the current live artifact.

From `evals/jev-classification`:

```sh
../../.venv/bin/python conditional_native_action_v2.py
../../.venv/bin/python conditional_native_action_v2.py --stage /tmp/specmetrics-conditional-v2-NEW
../../.venv/bin/python coreinfra_retry_run.py --run /tmp/specmetrics-conditional-v2-NEW --live
../../.venv/bin/python conditional_native_action_v2.py --inspect /tmp/specmetrics-conditional-v2-NEW
```

Live requires the separately approved bounded batch and a recorded authorization
before any POST. No semantic retry, scoring/accuracy claim or production S/U change.
