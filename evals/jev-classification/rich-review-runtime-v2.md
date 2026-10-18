# Rich-review runtime v2: initialize before reservation

This is a new preparation/execution version of the one-request rich-review
runner. It retains the same selected historical source view, independent review
task and one-attempt/token/byte limits. All runtime distribution metadata, source
inventory, receipt fields, response shell and exact reservation digest are
constructed before writing the exclusive dispatch lease. A metadata failure
therefore performs no POST and leaves the preparation unspent and retryable.
There is no fallible receipt initialization between lease creation and the
failure-recording try/finally. Post-reservation failures keep the reservation
and produce the existing incomplete response/transport receipt.

Use `rich_review_pilot_v2.py` for a future new preparation; the v1 runner remains
only for exact historical artifact replay. New v2 study, run and producer pins
cannot consume a v1 preparation or its old live authorization. No new live run
is authorized by this implementation or offline tests. A future `--live` action
still requires explicit approval of a fresh frozen request and its budget.

Tests force the runtime-inventory helper to raise before reservation, verify no
sender/lease/output is created, and then exercise the same staged preparation
through a synthetic successful dispatch. A separate post-lease failure retains
the lease and a diagnostic receipt. Historical v1 code, protocol, stored source
hashes, response and report remain unchanged.
