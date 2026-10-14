# Offline replay boundaries

Run from `evals/jev-classification` in the original checkout. The declared absolute delivery paths must continue to exist with the retained bytes. Moving or regenerating pristine copies elsewhere is not the same delivery replay. Another checkout can inspect this archived package, but cannot claim the original actual-file preflight without the original paths.

```sh
rtk proxy ../../.venv/bin/python validate_manifest_contract_factorial.py
for slot in 01 02 03 04 05 06 07 08 09 10 11 12; do
  rtk proxy ../../.venv/bin/python validate_manifest_contract_factorial.py \
    --assignment "runs/2026-10-14-manifest-contract-balanced-results-astra-high/attempt-receipts/annotator-${slot}.json" \
    --annotation "runs/2026-10-14-manifest-contract-balanced-results-astra-high/raw-attempts/annotator-${slot}-attempt-01.json" || break
done
```

The existing per-attempt validator rereads actual packet/template/prompt files. Every retained raw JSON is validated as written, not normalized or repaired. `validation/replay-records.json` records the concrete commands and exit codes from this run.

From the results directory, check the retained artifact bytes:

```sh
rtk proxy shasum -a 256 -c SHA256SUMS
```

The checksum inventory includes `semantic-review.json`, all raw attempts, delivery bytes, analysis, attempt receipts and the final execution receipt. It is an integrity check, not a semantic grader or authenticated signature. `execution-receipt.json` separately lists the exact raw/review hashes and producer/preparation identities.

There is no implemented batch-results semantic gate in this protocol. The recorded 60 review judgments were made by the nonblind model integrator. Their semantic truth is not established by either shasum or the per-attempt validator. Replay does not rerun inference, certify internal reasoning, verify runtime model identity, or create human gold. No validator code was added for this run.
