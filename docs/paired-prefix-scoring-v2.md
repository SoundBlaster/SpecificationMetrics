# Completed-prefix operational scoring v2

Use `paired_retrieval_scoring_v2.py --run <path> --output <new-file>` for new
incomplete-run diagnostics. The frozen v1 producer and its contract remain for
historical replay; its early incomplete return is a known historical limitation.

V2 verifies the preparation, producer/runtime binding and file hashes, then each
completed prefix record against its scheduled request, full local ledger and
captured body. It stops at the first failed or unverifiable record and retains
earlier verified rows. An unterminated final JSONL fragment is reported separately;
bad interior or newline-terminated malformed records are rejected, never repaired.
Missing receipt/binding files still provide no verified rows. A complete receipt
continues through the original full-cohort verifier.

The prefix contributes diagnostic row/axis counts only. Planned denominators stay
16 responses / 64 axes; H1/H2 remain ineligible and H3 cannot pass an incomplete
execution. Local prefix verification is not remote attestation or a complete run.
The synthetic regression fails request eight after seven successes: all seven
verified rows / 28 diagnostic axes remain visible while H3 fails. No hosted call,
historical output rewrite or change to the original scoring qualification occurs.
