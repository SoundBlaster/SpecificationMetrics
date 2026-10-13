# Validity definition and owner-name diagnostic

**Status: prepared, not dispatched.** Sixteen distinct tasks, sixteen planned
fresh contexts, four cases per context: 64 annotations. All labels are blank.
This is independent-annotation preparation, not a Jev/Luna provider protocol.

The [preceding adjudication](../2026-10-13-bdd-step-item-adjudication/README.md)
found that the link-only `not step.valid` packet established existing
Specification ownership but omitted the validity definition. This preparation
audits that definition and crosses additional context with owner-name rewriting
under the unchanged expression-fit v2 rubric. The hypotheses remain outside
annotator packets.

## What the pinned source actually does

At SpecGraph commit `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`,
[`TextInput.valid`](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/native_bdd/context.py)
returns:

```python
return self.value is not None and bool(self.value.strip())
```

The [boundary adapter](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/native_bdd/boundary.py)
maps non-string scalars to `None` and builds each step through `text(s)`.
The type declarations bind `BDDContext.entries` to `ScenarioInput` and its
`steps` to `tuple[TextInput, ...]`. Consequently the selected check rejects
non-string, empty and whitespace-only steps. `strip()` is used to test content;
the original stored string is preserved. It does not inspect executable BDD
grammar or decide whether a nonempty step expresses meaningful behavior.

This settles the **operational criterion**. A reusable text-validity predicate
can participate in representation validation or implement a domain obligation.
The new context therefore does not assign `policy` or `mechanics` as gold.
No canonical requirement excerpt is added in any condition.

[source-audit.json](source-audit.json) records seventeen exact excerpts from
nine source files, their SHA-256 hashes and line ranges. These were checked
against the pinned Git objects before preparation. Offline replay pins that
audit's bytes; it does not independently authenticate remote source.

## Four targets and two factors

| Packet ID | Source decision | Additional context | Role in the diagnostic |
| --- | --- | --- | --- |
| `probe-a` | `not step.valid` | Typed BDD input declarations and the `text`/`entry` conversion definitions | Focal disputed task; explicit Specification evaluation path is always visible |
| `probe-b` | `gate != "none"` | Frozen gate actions, status constants and `SpecNode` declaration | Independent lifecycle family |
| `probe-c` | Lexical manifest-path predicate | Frozen pathlib import, error type and manifest consumer | Independent reference-validation family |
| `probe-d` | `not rendered.endswith("\n")` | The serializer's `yaml` import | Local-role control: the base function already visibly appends the newline |

Every target retains its exact expression and base containing declaration.
The additional-context bundles are target-specific, so their effects must be
reported per target. They must not be pooled as one universal treatment.

| Cell | Additional context | Selected owner names |
| --- | --- | --- |
| 01 | absent | original |
| 02 | present | original |
| 03 | absent | neutral aliases |
| 04 | present | neutral aliases |

For BDD, aliases replace the owning classes, policy registry and its local
iteration variable: for example, `BDDScenarioValuesSpec` becomes `RuleA` and
`BDDPolicy` becomes `RuleBase`. For the other targets, only the containing
function name and its supplied references change. The transformation edits
Python NAME token spans, preserving comments, whitespace and string literals.
Each inverse transformation must recover the original bytes; collisions with
existing names are rejected. This is a partial owner-name ablation, not removal
of all semantic vocabulary: field names, value types, rule addresses and the
explicit `Specification` marker stay visible.

The transformed snippets are source-derived diagnostic inputs. They are not
verbatim source or production refactorings. The integrator-only
[source-mapping.json](source-mapping.json) records every original fact, alias
mapping and supplied fragment digest. Packets have opaque case IDs and fragment
IDs and contain no mappings, hypotheses, prior judgments or condition fields.

## Assignment and prospective criteria

Each of sixteen fresh contexts sees all four targets and all four conditions,
one view per target. Every target-cell has four contexts; each target and each
condition occurs four times at every position. Four rotations rather than three
balance target position as well as condition position.

ID, title and step checks were deliberately not grouped as separate targets:
they share `TextInput`, so a supplied definition in one case would reveal a
withheld dependency in another. The selected families do not disclose that
shared definition. Case-local instructions and balance cannot eliminate broader
cross-case priming, which remains a limitation.

The integrator-only [study-plan.json](study-plan.json) freezes these criteria:

- **H_ownership:** all sixteen focal opportunity labels remain `excluded` with
  the explicit evaluation path, including neutral owner names.
- **H_names:** at each context level, focal concern-kind histograms match across
  original and neutral names, four judgments per cell. A difference records a
  name-associated observation; it does not establish causal model bias.
- **H_definition:** none of the eight extended-context focal rationales claims
  the operational validity criterion is unavailable or that `strip()` rewrites
  stored values. Remaining uncertainty about domain purpose is permitted.
- **H_local_control:** all sixteen newline judgments are `excluded / mechanics`.
  This is an authored development-control expectation from the local append
  operation, not independent annotation or human gold.

Report failed criteria, per-axis coverage and raw target-cell distributions.
Rationale support needs semantic review in addition to exact substring checks.
Small counts and these reused development targets do not establish population
accuracy or statistical significance. The annotation prompt and task identities
are new; this is not an unchanged-input repeat of the previous study.

## Offline verification and dispatch boundary

Use Python **3.10 or newer**, matching CI. From the repository root:

```sh
.venv/bin/python -m unittest discover -s evals/jev-classification -p test_prepare_definition_owner_names.py -v
.venv/bin/python evals/jev-classification/prepare_definition_owner_names.py
```

The seven focused tests cover full assignment balance and task hashes, exact
reversible renaming and collision rejection, hidden-definition leakage,
blank labels, prompt formatting, source predicate behavior, overwrite refusal
and detection of artifact drift. The real-source test checks scalar conversion
and preservation of surrounding whitespace. It fails explicitly on an older
interpreter rather than modifying the source to suit that runtime.

Preparation uses frozen local inputs and makes no provider requests or metric
writes. The producer's `--write` option creates a fresh output set exclusively;
the default invocation replays saved artifacts. The receipt binds inputs,
producer and all generated outputs. Model identity is not assigned or verified
by preparation. Actual dispatch must record assigned packet/template bytes,
the formatted prompt, fresh-context identity and original output receipt.

Next: review these inputs and prospective criteria, then perform fresh
independent annotation. A paid provider run requires a separate bounded
protocol and authorization under the evaluation instructions. The source
excerpts and their transformed derivatives retain the copied Apache-2.0
[upstream license](upstream-LICENSE.txt).
