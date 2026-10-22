# Authorized PR714 live route pilot v1

Authorization: user approved the proposed four first-stage Jev batches and up to
four conditionally selected ordinary Luna reviews: “Бюджет согласовываю. Ок”.
Use only the merged PR93 v2 source packets, frozen rubric/profile and existing
categorical bridge, routing Specifications and structured-review inspector.
This is a historical operational pilot, not an accuracy benchmark. No Sol calls,
new prompts, context expansion, semantic retry, accepted facts, S/U mutation,
Specification extraction, GitHub comment publication or reopened ablation study.

## Fixed budget and request identity

- Four independent first-stage batches, one per D01–D04, model `jev-1.13.0`, four
  original Choice questions per batch, exact CoreInfra TypeSafe endpoint.
- At most one ordinary rich review per case selected by the existing router:
  `gpt-6-luna`, reasoning `low`, 1,024 output tokens, existing Responses endpoint.
- At most eight logical dispatches and eight potentially billable POSTs.
- At most three TLS-connect attempts per dispatch (24 overall), with one/two
  second backoff **only** for recognized transient TLS failures before any POST
  may have started. Certificate validation stays enabled. Never resend after a
  possible POST, incomplete body, HTTP error, timeout, semantic/protocol failure
  or ambiguous outcome. HTTP 400/401/402/403/429 stops remaining dispatches.
- 30-second socket timeout, child process hard deadline of 100 seconds per
  logical dispatch, and a 900-second dispatch-phase deadline; each child is
  capped by remaining time. The parent kills its process group on timeout.
  Offline preparation/report processing is outside that dispatch deadline.
- Requests at most 96 KiB, captured response at most 1 MiB. The two largest rich
  review templates are 71,515 and 72,988 bytes: the existing 64 KiB transport
  cannot accept them. A new profile raises only the request-byte bound; old
  transports/producers and the prepared context are unchanged.
- The native endpoint has no requested output-token-cap parameter in this
  profile; its token cap is explicitly unknown, with the response-byte bound
  enforced. Input tokens and monetary cost are reported only when observed;
  there is no invented dollar cap or character-to-token billing estimate.

The producer freezes all four native wires and all four conditional review
templates before dispatch. Review template construction uses a synthetic unknown
assessment solely to select offline preparation. Those labels are not sent to
either model or used as a reference. A real selected review must be byte-identical
to its frozen template before it can be dispatched. First-stage answers are
preserved in resolution context but not fed to the ordinary reviewer.

## Lifecycle and provenance

Freeze the source receipt, complete local producer closure/protocol, SDK/runtime
versions and public provider source hashes, exact request bytes/digests and fixed
limits. Preparation alone sends nothing. Commit the preparation before live use.
Execution requires `--live` and an existing environment credential; neither
preparation nor receipts contain its value.

An exclusive preparation-level dispatch reservation prevents spending the same
preparation again, including with another output directory. An exclusive request
directory/ledger prevents repeating a selected dispatch. Durable attempt and
possible-POST markers precede connection/request effects. Each request runs in a
child with the parent's hard deadline. Raw successful HTTP bodies are preserved
with digest/base64 unless they reflect the credential; arbitrary error bodies
and child stdout/stderr are not published. No redirects are followed.

`local-execution.json` carries only a local preparation path needed by the child;
it is explicitly excluded from publication/inventory. All provider captures,
requests, attempt events, execution/transport receipts and reports are inventoried.
The result verifier replays SDK decoding, routing, conditional-review selection
and source/quote checks against those frozen inputs with zero new requests.
Local receipt/source hashes are integrity evidence, not remote attestation or
semantic truth. Native distributions, usage and returned identities remain
provider metadata. Unknown ownership is not an absence claim.

Incomplete, failed, not-run and unresolved cases remain visible. A retained or
resolved proposal is advisory; it never becomes an accepted Specification or a
clean current-main PR review. Root-cause observations and limitations belong in
the run README after capture, without changing a frozen producer or prompt.
