# Single rich review and report: pilot v1

Date: 2026-10-18. Freeze this protocol and producer closure before inference.
Authorization: the user requested the report and a live review after seeing
the first-stage and rich-review adapter results.

- Select only Jev R04/baseline from the pinned native instruction-parity run.
- Reuse its unchanged evidence and four original question definitions; no Sol
  answer or first-stage prediction is copied into the model input.
- Use the existing rich-review v1 strict Responses body, ordinary `gpt-6-luna`,
  reasoning `low`, at the exact CoreInfra HTTPS Responses endpoint.
- One logical review, one network attempt, at most one potentially billable POST,
  no TLS/HTTP/semantic retry, no fallback, no prompt expansion. A preparation-wide
  exclusive dispatch reservation prevents spending it via another run directory.
- Maximum output: 1,024 tokens; response bound: 1 MiB; request bound: 64 KiB.
  Socket timeout: 30 seconds. This is not a hard end-to-end wall-clock deadline.
- Persist/fsync dispatch events before HTTP; never save credentials or headers.
  Store an exact safe HTTP-200 body with a digest. Drop non-200 bodies and any
  response reflecting the supplied credential. Save safe status/counter metadata.
- Frozen artifact/producer/request identities must verify before dispatch.
  Artifact presence is not successful execution or semantic readiness.
- Report all three inspector outcomes: resolved_proposal, needs_review and
  analysis_incomplete. Preserve citations, unresolved evidence, first-stage and
  reviewer labels, timing scope, usage, null unknown monetary cost and receipts.
- The Markdown report is informational and bound to the historical SpecGraph
  revision. It is not a review of current main, a merge gate, canonical fact
  acceptance or an S/U change. No GitHub comment is posted by this runner.
- Verify report replay without inference. Keep any failed/partial attempt;
  do not overwrite it or fix a model answer to turn a failure into success.

This one development view tests the transport/schema/quote-resolution pipeline,
not general accuracy, repeatability, model ranking or production qualification.
The rich response contract differs from the earlier label-only Responses pilot;
do not retroactively reinterpret those answers as rich reviews.
