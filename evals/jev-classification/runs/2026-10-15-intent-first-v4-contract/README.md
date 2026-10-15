# Intent-first v4: offline contract examples

Four source-grounded development examples, not model answers or a scoring reference.
The examples apply the [human clarification](../2026-10-15-scope-binding-adjudication-v2/README.md).
See the [contract guide](../../intent-first-evaluation-v4.md) for semantics and limits.

Inspect `integrator-examples.json` to see the three independent fields: concern kind,
evidence confidence and recommendation. The no-document manifest example recommends
formalization while keeping unknown role / insufficient support. Gate precedence is
formalize; BDD is reuse_specification; newline is use_tool_rules.

Only packet/contract/template and prompt are prospective annotator inputs. Source
bindings, integrator examples, receipts and this guide are integrator-only. No
handoff, isolated execution, annotation dispatch or provider wire adapter is prepared.
The four examples were previously discussed and cannot be an unseen holdout.
No new model contexts/provider requests; production S/U and frozen history unchanged.
Structural/identity/quote validation does not establish semantic correctness.
