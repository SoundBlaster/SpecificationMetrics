# Intent-first v4.1: consistency repair

Supersedes [preserved v4](../2026-10-15-intent-first-v4-contract/README.md) for future tasks.
The four integrator examples keep their source, state, scope, profile and labels/actions.
Contract/task identities change; the template drops integrator-only status metadata.
No new model outputs or scoring reference.

`keep_procedural` now requires `mechanics / supported`. Policy, unknown or limited
support cannot justify this recommendation. The output schema is the strict
`{"annotations": [...]}` response used by prompt/template/consumer.
`formalization_preference` means uncertainty in primary role; supported domain
rules use `domain_contract` even if implementation details remain undecided.

See [contract guide](../../intent-first-evaluation-v4.md) and
[failure diagnosis](../../failure-learning.md#intent-first-v41-consistency-repair-2026-10-15).
Only packet, contract, template and prompt are prospective annotator inputs.
Integrator examples/source mappings are not annotator inputs. Dispatch remains
unprepared; no provider requests, classifier/SU changes or semantic accuracy claims.
