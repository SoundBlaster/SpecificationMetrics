# Semantic instruction parity diagnostic v1

## Question and scope

Does giving native Jev and Luna Decision the semantic analysis guidance already
given to Sol change their agreement and internal consistency on the same eight
SpecGraph evidence views? This is an instruction-condition diagnostic, before
the configurable-backend refactor. It does not measure semantic accuracy or
isolate model capability from provider execution differences.

The user authorized this repeat and explicitly requested reusing Sol when its
instructions remain substantively unchanged. There are **zero new Sol calls**.
The existing 24 fresh-context Sol 6.1 Medium annotations, their source witnesses,
configuration, eight-view consensus and receipt are verified without modification.

## Controlled change

The preparation embeds paragraph 2 of the exact original Sol annotation brief
verbatim into each native question's instructions. It also embeds the original
category definitions for all four axes, which Sol could read together in
`annotation-rubric.json`. The original per-question instructions remain intact.
The rubric filename in the transferred paragraph refers to this embedded catalog;
native providers need no file access.

Frozen inputs:

- [Original evidence preparation](runs/2026-10-18-paired-retrieval-preparation-v1).
- [Original annotation instructions](runs/2026-10-18-paired-blind-reference-v1/annotation-brief.txt).
- [Sol 24-response run](runs/2026-10-18-sol61-medium-repeatability-v1/README.md).
- [Previous native comparison](runs/2026-10-18-jev-luna-sol-comparison-v1/README.md).

Only `questions.*.instructions` changes in the native wire bodies. State strings,
accepted unknown fact placeholders, source revision, retrieval hits/ranking,
model names, endpoints, native criteria, scheduling order and evaluation rules
stay identical. No new retrieval or embeddings are generated. A reconstruction
check rejects other changes even if checksums are rebound.

Sol's request for rationale and source quotes and the native choice-distribution
output remain different. Agent file/tool restrictions are not native API options.
Internal provider question isolation, backend revisions and decoding are not
attested. Semantic guidance parity does not imply identical execution or prove
that a remaining disagreement is a model defect.

## Budget and evidence

16 logical requests: four targets × two evidence arms × two providers. Reserve
at most 48 transport attempts, using the existing bounded TLS retry protocol.
No semantic retries, no repeat of a completed/partial directory, no extra Sol
calls. Keep exact successful HTTP JSON bytes, request wires, attempt ledger,
receipts and execution source/runtime inventories. A non-successful run remains
incomplete; captured response count is not verified quality evidence.

The specialized inspector retains the old strict manifest/ledger/body checks
without changing frozen historical producer files. Shared-runner extraction is
deliberately deferred. Native parsing and the two SpecificationCore consistency
rules are reused unchanged; adaptation metadata refers to the actual new wires.

## Predeclared evaluation

For each provider report all four axes (32 planned slots), primary role/ownership
(16 slots), valid-native coverage, eight per-view decisions, abstentions and
coherence conflicts. Compare new and old decisions against the same Sol labels,
showing every gained/lost agreement and every conflict change. Never drop an
invalid/missing response from the planned denominator or count it as a semantic
wrong answer. Do not compute a complete-cohort delta for incomplete native coverage.

Keep unknown agreement separate from positive evidence. Do not normalize away
native mass warnings, repair labels using the consistency gate, accept model facts,
or change production metrics. Four targets and one temporal repeat cannot support
a general ranking or a causal clause-level explanation.

Interpretation: improvement suggests the earlier pipeline comparison was sensitive
to task specification; no improvement means this instruction change did not resolve
the observed discrepancies. Neither result alone approves a large refactor. First
inspect remaining per-target disagreements and decide the next bounded experiment.

## Commands

From this evaluation directory, using the repository environment and configured
TB5 cache paths locally:

```sh
../../.venv/bin/python instruction_parity_v1.py freeze
../../.venv/bin/python instruction_parity_v1.py stage
../../.venv/bin/python instruction_parity_v1.py execute --live
../../.venv/bin/python instruction_parity_v1.py score
# Write the result diagnosis/README, then seal all run files.
../../.venv/bin/python instruction_parity_v1.py seal
../../.venv/bin/python -W error -m unittest -v test_instruction_parity_v1
```

Only the explicit `execute --live` command sends hosted requests. CI replays
captured evidence and synthetic transports offline.
