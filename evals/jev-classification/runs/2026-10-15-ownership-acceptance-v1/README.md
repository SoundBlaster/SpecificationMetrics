# Ownership acceptance handoff

Offline counterfactual replay of the pinned SpecGraph BDD case: start from the
known role with ownership deliberately left unknown, verify the existing static
source witness, accept a new Facts snapshot and obtain `reuse_specification`.
This is not a new discovery or an accuracy improvement. No live calls or real
project-wide negative ownership approvals were made.

See the [contract and retrieval boundary](../../ownership-fact-acceptance-v1.md).
`report.json` retains before/acceptance/after values, trace and source/producer
digests. From `evals/jev-classification`, verify with:

```bash
../../.venv/bin/python replay_ownership_acceptance_v1.py
```

Generic approval/readiness and RAG cases are synthetic regression fixtures in
`test_ownership_acceptance_v1.py`; they do not authorize facts about SpecGraph.
