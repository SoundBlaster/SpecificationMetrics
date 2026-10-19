# Final instruction-placement check v1 — preregistration and stop rule

Authorization: **«Сделай проверки ещё, но потом глубже копать не хочу уже»**.
This is the final bounded investigation. Complete and report this cohort; no
additional ablation, corpus expansion or root-cause search follows it.

Use the same three baseline controls R01/R02/R03, public Codex 0.156.1 template,
CoreInfra Responses endpoint, requested `gpt-6-luna` / medium, strict four-axis
schema and limits as the previous public-envelope study. The generic template
stays unchanged in top-level `instructions` in **both** conditions.

Both requests have two explicit input messages in the same order: the unchanged
canonical question instructions/criteria, then the unchanged source state. The
**only within-pair JSON difference** is the first message's `role`: `developer`
or `user`. Thus this checks message priority directly without changing the text,
schema, evidence, model, effort, envelope or provider. It is not an exact CLI
reconstruction; the public template differs from the old server-cached one.

Two repeats per case/condition, balanced AB/BA order and reversed second case
block: **12 logical requests**, at most **36 network attempts** with the existing
three-attempt verified-TLS/incomplete-body retry protocol. Same request bytes on
transport retries; no HTTP/schema/refusal/semantic retries, no new Sol calls,
fallbacks, tool execution, session history or automatic fact/metric updates.
No hard currency cap is claimed. A failed cohort stays partial; it is not rerun.

Freeze the producer closure, prior evidence/reference/fixture hashes and exact
12-request manifest in Git before dispatch. Existing CoreInfra transport owns
durable attempt accounting; public Jev4Mellea SDK replays response decoding
offline. The SDK's minimal decoder wire is not the actual role-treatment wire.
Captured provider JSON objects preserve values, not original HTTP bytes/headers.

Reuse the unchanged Sol labels solely as empirical comparators. Report all 48
planned axis slots, six planned responses per condition, ownership by repeat,
consistency checks from the existing Specifications, within-condition repeat
agreement, reported usage and attempt ambiguity. Invalid outputs stay failures,
not fabricated abstention labels. Partial cohorts receive no complete-cohort
quality conclusion. Requested/echoed model settings are not remote attestation.

Narrow prediction: R01 is `existing_specification` in both developer-rule repeats
and `unknown` in both user-rule repeats. That pattern supports a priority-associated
abstention on this selected control. Identical stable answers do not support the
prediction here; mixed answers are inconclusive. No result identifies the exact
old CLI cause or establishes general semantic accuracy.

The conclusion will close the investigation regardless of outcome. Keep the
earlier CLI disagreement visible and state remaining uncertainty. Further work
returns to ordinary delivery/review and classifier integration, not new probes.

```sh
../../.venv/bin/python -B -m unittest -v test_instruction_placement_v1.py
../../.venv/bin/python -B instruction_placement_v1.py prepare
../../.venv/bin/python -B instruction_placement_v1.py run --live
../../.venv/bin/python -B instruction_placement_v1.py analyze
```
