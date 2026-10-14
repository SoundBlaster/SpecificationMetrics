# Layer 4 — offline handoff and later annotation/review

## Present state

The preparation stack freezes twelve tasks/assignments for one exact source
expression. No annotator has started. The handoff command creates scoped files
and genuinely blank attempt/manual-review receipts; file presence is not run
completion. Preparation or merging this stack does not authorize inference.

First replay from `evals/jev-classification`, Python >=3.10:

```sh
python3 prepare_manifest_contract_factorial.py
python3 validate_manifest_contract_factorial.py
python3 -m unittest -v test_manifest_contract_factorial.py test_manifest_contract_handoff.py
python3 prepare_manifest_contract_handoff.py
```

The last command previews the handoff without creating directories. To create
delivery files, pass a **new** directory:

```sh
python3 prepare_manifest_contract_handoff.py \
  --destination /private/tmp/specmetrics-manifest-delivery-UNIQUE
```

The command never calls a model, network, credentials or Git. Each annotator
folder receives exactly `packet.json` and `template.json`. Prompts and operator
receipts are outside those folders. Reusing an existing destination is rejected;
an interrupted write is not resumed. Retain failed artifacts and use a fresh
directory rather than treating partial presence as readiness.

## Later dispatch — only after user authorization

1. Check the frozen preparation again. Preserve its receipt, producer identity,
   rubric and all packet/template bytes. Do not change them after observing labels.
2. Spawn twelve **fresh contexts with no conversation inheritance**, one slot
   each, using its exact formatted prompt from `prompts/`. Inherit the configured
   model/effort unless the user explicitly chooses them. Record actual agent/task
   identity and any known runtime model identity; unverified identity stays
   unverified. Do not reuse a context for another view of this expression.
3. Follow interleaved assignment order. Three waves of four slots each keep all
   four conditions represented in each wave and fit the existing concurrency
   ceiling. This ordering is deterministic, not randomized.
4. The agent may read only its two assigned files and write `annotations.json`.
   Keep catalog, source mapping, hypotheses, audit suggestions and other results
   with the integrator. No recursive delegation or credentials. Use the shared
   event-aware agent wait rather than repeated status polling.
5. Retain exact raw bytes immediately, including invalid/failed attempts. Fill
   that attempt receipt with the actual context declaration, agent task and raw
   output SHA-256. The saved prompt/input bindings already identify its evidence.
   Do not assert isolation if a deviation occurred; record it and exclude that
   attempt transparently. A replacement needs a new context and new receipt.
6. Validate each retained attempt offline:

   ```sh
   python3 validate_manifest_contract_factorial.py \
     --assignment /path/to/filled-attempt-receipt.json \
     --annotation /path/to/retained-raw-output.json
   ```

   The blank receipt cannot pass validation. A valid receipt requires zero
   Jev/Luna provider calls and unchanged metric/reference authority for this
   independent-agent protocol. Direct paid-provider evaluation is a different,
   explicitly authorized run with its own request/budget receipt.
7. Keep all attempts in a separate results directory, never in frozen
   preparation. Update retained/excluded attempt records and report replacements,
   failure reasons and actual contexts used; twelve valid slots may require more
   than twelve attempted contexts. Never repair an agent's raw labels or quotes.

Input isolation remains scoped assignment plus fresh context and self-report;
it is not a filesystem sandbox or proof of a model's internal reasoning.

## Later manual semantic review

The generated `semantic-review.template.json` covers six document-present,
six consumer-present and all twelve target-fidelity judgments. Its judgments,
raw hashes and supporting notes are null until reviewed. Fill them from the
retained answers and link exact output hashes. The integrator is not blind and
does not create human gold by reviewing a model's answer.

- H_contract checks interpretation of the **supplied documentary requirement**.
  It does not demand canonical adoption or a particular label.
- H_consumers checks interpretation of supplied local read, scoped copy, HTTPS
  verification and shared staging-prefix evidence. Not every rationale must
  enumerate every use.
- H_target_fidelity distinguishes the whole lexical predicate from later
  consumer effects and rejects fabricated capabilities or narrowed boundaries.
- Formal quote/receipt validation supports H_traceability. It cannot establish
  semantic support for a rationale.

Do not mark complete while any slot, identity, required quote, raw attempt,
manual criterion or applicable review entry remains unaccounted for. Bind the
completed manual artifact and every contributing raw output into the future
results receipt and offline replay before reporting all criteria met. This is
the prevention lesson from PR #49, not an automatically implemented batch-results
grader in the present preparation.

## Result interpretation

Report four-cell per-axis label histograms and decisive coverage (denominator
three), all repetition disagreements, and all failed criteria. Compare document
effects at fixed consumer levels and consumer effects at fixed document levels.
`needs_review / unknown` is permitted when primary responsibility remains
materially mixed. Do not count abstention as exclusion or automatic failure.

Keep observation, manual interpretation and proposed adjudication separate.
Agreement does not prove correctness; twelve judgments of one source expression
are not a representative codebase sample. No automatic changes to reviewed S/U,
no scoring gold and no production classifier activation follow from this run.
New evidence, changed prompts/rubrics or acceptance criteria require a new
version and preserved historical outcomes.

The next deliverable after preparation review is the independently annotated
results package with all raw attempts and a separately bound manual review.
