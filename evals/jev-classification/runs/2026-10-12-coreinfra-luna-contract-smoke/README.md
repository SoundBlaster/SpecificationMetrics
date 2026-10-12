# CoreInfra Luna native contract smoke — 2026-10-12

## Result

One live mixed request returned HTTP 200 with model `gpt-6-luna`.
Predicate, Choice and Score answers passed offline structural/numeric validation.
Elapsed transport time: **3.019479 seconds**. One network attempt, one potentially
billable POST, no retries or ambiguous posts. Usage: 382 input tokens, zero output
tokens reported. Actual dollar cost and remaining balance are unknown.

This is a trivial compatibility smoke, not classifier accuracy, calibration,
production readiness or evidence of the gateway's internal upstream identity.
The comparison corpus was not sent. No S/U or registry changes.

## Contract and discovery

- Operation tested: `POST https://hub.coreinfra.ai/openai/api/v1/decisions`.
- Requested and returned model: `gpt-6-luna`.
- Native input: text `input`, array `questions` with `name` and typed fields.
- Native output: array `answers`, predicate `probability`, choice `choice` with
  string-valued probabilities, score with zero-based numeric level probabilities.
- CoreInfra's public frontend configuration at
  <https://hub.coreinfra.ai/modules/entrypoints/hydrate.js> advertises
  `https://hub.coreinfra.ai/openai/api/v1` as an OpenAI-compatible base.
  Build observed: `6dff99f7`. An authenticated GET to `/openai/api/v1/models`
  returned 25 catalog entries, including `gpt-6-luna` and `gpt-5.6-luna`.
  Catalog presence alone did not establish Decisions support.
- The operation suffix and native schema came from the
  [official Decisions guide](https://developers.openai.com/api/docs/guides/decisions),
  accessed 2026-10-12. Joining the advertised proxy base and documented native
  operation was initially a hypothesis; the successful live POST verifies this
  route for the frozen smoke. It is not a published CoreInfra support guarantee.
- Two authenticated read-only catalog GETs preceded the single inference POST;
  no credentials, headers or account data are retained in these artifacts.

## Evidence and replay

`manifest.json` freezes request bytes, their hash and producer digests before POST.
`attempts.jsonl`, `responses.jsonl` and `receipt.json` preserve the transport run.
`validation.json` binds the response and `validate_smoke.py` digests.
The validator checks all three named types, exact option coverage, finite unit
probabilities/confidence, normalization, level labels and weighted score.
Five corrupted controls were rejected: missing answer, wrong type, duplicate
option, nonfinite probability and inconsistent score.

```sh
python3 evals/jev-classification/runs/2026-10-12-coreinfra-luna-contract-smoke/validate_smoke.py
```

This validator is specific to the frozen smoke. A general strict decoder for the
comparison's two Choice questions and an executable matched wire manifest are
still required. Do not rerun this manifest live or overwrite the original run.
