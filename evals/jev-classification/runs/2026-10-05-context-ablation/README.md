# Jev context ablation — 2026-10-05

## Result

Task context corrected one already-owned false positive. It **did not fix the
two false exclusions**. Adding explicit structural facts did not help Jev use
existing Specification ownership, even after a factual extractor limitation was
corrected. The preregistered combined success criterion was not met.

| Input, unchanged baseline prompt | Opportunity agreement | Eligible recall | Eligible precision | Already-owned false positives | Mechanical false positives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Code | 4/8 | 1/3 | 1/3 | 2 | 0 |
| Code + task evidence | 5/8 | 1/3 | 1/2 | 1 | 0 |
| Code + task evidence + structural facts | 4/8 | 1/3 | 1/3 | 2 | 0 |

Each arm was run twice with fresh responses. Opportunity and concern-kind
labels were identical between the two repeats; probability/confidence values
were not assumed identical or calibrated. Repeats do not double the independent
sample size. No provider/contract errors or abstentions occurred.

All eight references are inherited independent model annotations, not human
gold. Three are eligible policies, two are excluded policies already expressed
as Specifications, and three are excluded mechanical controls. Six source
families are represented. The sample was chosen using prior disagreements and
paired implementations; this is diagnostic development evidence, **not a new
holdout**. Other original corpus families are not confirmed by these results.

## Source and task boundary

- `sg-017`/`sg-018` and mechanical `_dict`/`_text` controls use the promotion-gate
  proposal's business summary at each exact source commit.
- `sg-019`/`sg-020` and the mechanical `_slug` control use the repair-loop
  proposal's summary and documented repair behaviors at the source commit.
- `sg-033` uses the subject-publication contract's original purpose and exact
  bootstrap-allocation clause, including both authorizations and scope binding.

These are source descriptions of the business task, not an accepted canonical
Requirement mapping or the refactoring PR author's requested classification.
The model receives verbatim text, file/excerpt hashes, source spans and immutable
links. Implementation/refactor guidance, previous labels, reference rationale
and prior model output are omitted. The code excerpt, supporting declarations,
provider instructions, model and criteria are unchanged across the three arms.

The third arm adds narrow AST facts: selected construct, constructor/factory
calls resolved to `specification_core`, and positive direct library construction.
Aliases are supported; shadowed/mutated/local-parameter bindings produce no
positive claim. Missing recognition is **unknown**, not evidence of no owner.
Runtime monkey-patching, arbitrary wrappers, module aliases and complete
cross-module identity/liveness resolution are outside this experiment.

## Input correction, kept visible

The first 48-request run did not recognize `FirstMatch.with_fallback` as a
direct library factory. It reported direct construction false for that case;
that field was unsuitable as a negative ownership inference. All initial
inputs and responses are retained in `initial-study.json` / `initial-run.json`.

The extractor was corrected to recognize this factory and use null for missing
positive recognition. A new study was frozen before another 48 requests. Tests
cover factory imports, aliases, rebinding, attribute mutation and local
parameters. Only the facts arm changes between study versions; the code/task
arms and prompt configuration remain byte-identical. Final classifications
are unchanged. Consequently, the first result cannot be attributed solely to
this extractor limitation. Both versions remain diagnostic experiments.

## Concrete observations

- `sg-018`, a named `FirstMatch` composition, remains eligible in every arm.
- `sg-020`, `FirstMatch.with_fallback`, changes to excluded with task context
  alone, then back to eligible when AST facts are added. The direction repeats
  in both runs, including corrected facts. Jev gives no rationale, so a cause
  such as attention to additional metadata remains a hypothesis.
- `sg-019`, the acceptance-criterion coverage repair, stays excluded.
- `sg-033`, six-condition workspace allocation, stays excluded despite its
  documented authorization purpose. Missing task text alone therefore does
  not explain this error under the tested baseline prompt/context format.
- All three mechanical controls remain excluded.

## Separate static-filter diagnostic

A deterministic positive filter recognizes the two direct library expressions
in the corrected inputs. In a separately reported evaluation view it assigns
those exact declarations excluded and leaves all other predictions unchanged.
This removes both already-owned false positives: agreement becomes 6/8 and
eligible precision 1/1. Recall stays 1/3: the static filter does not solve
missed inline rules. These numbers are **not raw Jev performance**.

This is an evaluation-only filter, with positive evidence and explicitly narrow
coverage. No production classifier, scanner registry, S/U counters or adoption
authority is changed. Do not infer exclusions from a missing constructor, or
apply a declaration-level fact to unrelated inline rules in the same function.

## Provenance and reproduction

The final study/receipts are `study.json`, `run.json` and `summary.json`.
The baseline prompt is copied unchanged from the recorded prior run and its
digest is verified during scoring. Model requested/returned: `jev-1.13.0`;
immutable model revision unavailable. Both runs use no cache/retries and
concurrency one. API-reported usage: 111,024 initial + 111,106 corrected =
**222,130 tokens over 96 hosted requests**. Monetary cost is not inferred.

Offline score, from the eval directory:

```bash
python context_ablation.py score \
  --study runs/2026-10-05-context-ablation/study.json \
  --run runs/2026-10-05-context-ablation/run.json \
  --output results/context-rescore.json
```

To verify extraction against local SpecGraph Git objects, generate a fresh
study with `context_ablation.py prepare --repo /path/to/SpecGraph --output
results/new-context-study.json` and compare it with the final study. This
executes no SpecGraph code. `run_context_ablation.mjs --study ...` prints a
request plan without hosted calls. Actual calls additionally require
`--allow-hosted --output results/new-context-run` and `TYPESAFE_API_KEY` from
the shell environment. Run directories are exclusive; previous evidence is
never overwritten. Source excerpts retain Apache-2.0 attribution.

## Next experiment

Keep formal ownership detection separate from semantic candidate assessment.
Adjudicate the two missed inline rules before changing references. On development
data, compare concrete questions about the exact predicate's product effect and
technical enforcement with the current broad opportunity question. Task text
and static facts need a versioned input contract; a longer context alone is
insufficient. Confirm any revised approach on new families before deployment.
