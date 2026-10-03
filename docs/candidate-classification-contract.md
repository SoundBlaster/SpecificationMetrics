# Candidate classification contract

Version 1 defines an optional, provider-neutral request and suggestion artifact
for System One classification of Specification adoption candidates. It is a wire
contract for a future `classify` command; the current CLI does not call Jev,
Laya, GLiNER or another model.

## Authority and metric boundary

The classifier returns two separate dimensions. `opportunity` says whether
this scanner candidate should count as a Specification opportunity after
review. `concern_kind` describes what kind of logic the candidate appears to
express. They answer different questions and must not be collapsed into one
enum.

The `opportunity` dimension suggests one of:

- `eligible`: this site appears to express a stable domain decision or policy
  that could benefit from a named, reusable Specification.
- `excluded`: this site appears to be mechanics or a local construct outside
  the intended Specification opportunity definition.
- `needs_review`: the classifier abstains. Treat this as unknown, not as an
  exclusion. Use it for ambiguity, insufficient context, unsupported syntax,
  omitted sensitive context, provider failure, malformed output or a close
  decision.

Ordinary input validation and Swift scope-exit cleanup (`defer`) are likely
`excluded` when they implement mechanics. A validation branch can still be
`eligible` when it enforces a domain rule. The rubric asks whether the condition
expresses a named, stable rule, can be understood in its bounded object/module
context, and would benefit from reuse or centralized observation. It does not
label every syntactic branch as a useful Specification.

The opportunity result has no semantic `reason_codes` field. A Choice answer
provides a label and scores, not a free-text explanation. The adapter must not
invent a rationale from the chosen label or its probabilities. Rationale is a
nullable object with a source: Jev v1 uses `{ "text": null, "source":
"unavailable" }`. A future provider that returns an explanation may populate
`text` and set `source` to `provider`; an adapter-authored explanation must be
identified as `adapter`.

The independent `concern_kind` dimension suggests one of:

| Concern kind | Meaning |
| --- | --- |
| `policy` | A condition expresses a durable product rule, authority, trust, evidence, eligibility or lifecycle decision. |
| `mechanics` | A condition handles parsing, representation, I/O, adaptation or technical enforcement. |
| `variant_behavior` | A condition dispatches behavior over domain variants such as an enum, type or platform. |
| `unknown` | The available evidence does not support a reliable concern-kind classification. |

These dimensions are orthogonal. A rule already owned by a Specification may
be `policy` and `excluded`; a repeated enum switch may be `variant_behavior`
and `eligible`; a parser branch may be `mechanics` and `excluded`. A concern
kind alone never changes the denominator. `unknown` on the concern-kind axis
does not itself mean `needs_review` on opportunity if the eligibility decision
is otherwise clear.

`diagnostics` reports adapter conditions only: `provider_error`,
`malformed_provider_output` or `close_decision`. The first two explain why a
suggestion fell back to `needs_review`/`unknown`. `close_decision` is only used
when the run explicitly configures a provider-specific confidence threshold;
the threshold is recorded in effective inference parameters and is not a
cross-provider calibration.

Suggestions are not reviewed registry dispositions. They do not change the
registry, the live `S / U` counts, liveness, or stored metric snapshots. The
existing human-reviewed `eligible` and `excluded` registry entries remain
authoritative. A later explicit review action may accept or correct a
suggestion; that action must be represented as a human review, separate from
this artifact. Merely generating or caching suggestions never performs that
action.

This contract classifies opportunities to apply SpecificationCore. It does
not classify application policies as accepted business decisions, authorize
publication, or prove that a proposed refactor preserves behavior.

## Classification input

The future command consumes a scanner report plus a versioned architecture
profile, normalized as a request by
`schemas/candidate-classification-request-v1.schema.json`. It sends one bounded
`CandidateContext` per discovered candidate. The context contains:

- the scanner fingerprint, source language, relative path, source span and
  syntax kind;
- the candidate excerpt and enclosing declaration, when available;
- a bounded set of related decision sites selected from the same scan, so the
  model can notice repeated checks or dispatch spread across files;
- the applicable portion of the architecture profile; and
- the rubric ID and version defining the three labels.

Do not send an entire repository or full files by default. The initial source
context budget is 24 KiB per candidate: at most 12 KiB for the enclosing
declaration, 4 KiB for the candidate excerpt, and eight related sites of at
most 1 KiB each. The applicable architecture-profile excerpt adds at most
4 KiB. Enforce limits using UTF-8 byte lengths and the aggregate budget;
JSON Schema character limits alone do not guarantee a byte limit. Truncation
must be marked in the input metadata. If relevant context is missing or
redacted, the result should be `needs_review` when that omission prevents a
reliable label.

An architecture profile is project-owned input, not model output. It should
provide a stable ID/version, concise intent for using Specifications, desired
object and module boundaries, allowed/excluded source roles or locations, and
known mechanical exclusions with reasons. The profile is guidance for
classification; it does not alter scanner scope or metric configuration.
The exact profile bytes used for a run are identified by a digest in the
result.

The request carries the exact opportunity-label and concern-kind definitions
alongside their ID, version and digest. This keeps provider adapters from
silently inventing their own label meanings. The position uses
1-based lines and columns with an exclusive end position. Request schemas bound
individual strings and collection sizes; the adapter must additionally enforce
the aggregate UTF-8 byte budgets above.

The request's `CandidateContext` is one of the entries in `candidates`. The
top-level `source` ties all candidates to the same immutable scan, while
`architecture_profile` and `rubric` are shared by the batch. A batch may be
sent to a local or hosted provider; the output artifact records which boundary
was used.

## Suggestion artifact

The v1 request and result are validated by
`schemas/candidate-classification-request-v1.schema.json` and
`schemas/candidate-classification-suggestions-v1.schema.json`. The result contains:

- artifact and schema versions;
- source revision, source digest, scope-manifest digest and scan-report digest;
- rubric and architecture-profile IDs, versions and digests;
- provider, requested model, actual model/checkpoint revision per response,
  adapter version, prompt digest, inference-configuration digest, aggregate
  input/output token counts, run ID and generation time; and
- exactly one suggestion for each candidate submitted in the run.

Each suggestion binds to the scanner fingerprint and a digest of the complete
bounded context. It includes both classifications and an optional rationale
object for each axis. Diagnostics describe adapter or provider conditions, not
semantic reasons for a classification. Provider scores are preserved
separately for both Choice questions, with per-axis semantics. Do not normalize
scores from different providers into a shared confidence value or treat them as
calibrated probabilities without separate evidence.

The Jev adapter uses two fixed-label Choice questions in one System One request:
one for `opportunity` and one for `concern_kind`. The selected options map to
the contract enums. Preserve each returned probability distribution and
confidence under its own axis. Jev's Choice response does not provide free-text
rationale, so v1 records rationale as unavailable. Jev's API returns the actual
model name and usage; record the model for each suggestion and aggregate token
usage in run provenance. The adapter fails closed to `needs_review`/`unknown`
if either selected option cannot be mapped to the current rubric. See the
[TypeSafe System One API reference](https://api.typesafe.ai/redoc) for the
provider request and response shape.

Digests are lowercase, algorithm-prefixed hex (`blake3:<64 hex>` or
`sha256:<64 hex>`). The source digest is the scanner's BLAKE3 digest with its
algorithm made explicit. The scan-report digest hashes the exact scanner JSON
bytes read. Rubric, profile and prompt digests hash the exact versioned bytes
used. A context digest hashes the exact normalized candidate context sent to
the provider after truncation/redaction. The inference-configuration digest
hashes the effective allowlisted parameters; common sampling parameters are
also recorded directly. This lets a reviewer identify changed inputs without
copying source code into the result.

If a provider fails for an individual candidate, emit `needs_review` and
`unknown`, with a `provider_error` diagnostic when an artifact can still be
produced. Every
input candidate is accounted for once; failure must not silently remove it
from the result. A malformed whole response may fail the command and produce
no authoritative suggestion artifact.

The artifact records provenance, not source text. It must not contain API
credentials, authorization headers, or a duplicate of the candidate context.
Only allowlisted, non-secret inference options may be recorded. Hosted
classification requires an explicit opt-in because bounded code context is
still source code leaving the machine. Local and hosted runs identify their
data boundary in provenance.

## Reuse and freshness

A cached result is reusable only when all of these match: candidate fingerprint,
context digest, rubric ID/version, architecture-profile digest, provider and
model/checkpoint revision, adapter version, prompt digest, and effective
inference-configuration digest. Changed source, context, profile, rubric or
inference setup requires a new suggestion. A line number alone is never an
identity. Cache records remain suggestions and never become reviewed registry
entries automatically.

For each run, the producer must verify that suggestion fingerprints form a
one-to-one match with submitted candidates. JSON Schema validates record
shapes, while this cross-record completeness/uniqueness invariant is enforced
by the producer.

## Review flow

The future review flow presents the source context, profile excerpt, rubric,
suggestion and rationale together. A reviewer can accept, correct or abstain.
Only an explicit accept/correct action writes the existing human-reviewed
registry disposition; abstain leaves the site unreviewed. Preserve the
suggestion artifact and reviewer action as distinct records so later reports
can measure agreement, correction rate and false exclusions by language,
rubric and provider. Do not overwrite the model's original result with the
reviewed disposition.

The report should show model suggestions separately from formal `S / U` values.
Any later metric view that applies accepted registry updates must identify the
resulting registry digest and continue to calculate `S / U` from the current
source snapshot.

## Example

```json
{
  "artifact_kind": "candidate_classification_suggestions",
  "schema_version": 1,
  "run_id": "run-01J...",
  "generated_at": "2026-10-03T14:00:00Z",
  "source": {
    "revision": "0123456789abcdef",
    "source_digest": "sha256:...",
    "scope_manifest_digest": "sha256:...",
    "scan_report_digest": "sha256:..."
  },
  "rubric": {
    "id": "specification_metrics.candidate.v1",
    "version": 1,
    "digest": "sha256:..."
  },
  "architecture_profile": {
    "id": "example.product",
    "version": "3",
    "digest": "sha256:..."
  },
  "provider": {
    "id": "jev",
    "endpoint": "https://api.typesafe.ai/v1/systemone",
    "requested_model": "jev-latest",
    "model_revisions": ["jev-version-returned-by-provider"],
    "adapter_version": "1.0.0",
    "prompt_digest": "sha256:...",
    "inference_config_digest": "sha256:...",
    "inference_parameters": {
      "temperature": 0.0,
      "top_p": null,
      "max_output_tokens": 256,
      "provider_options_digest": "sha256:..."
    },
    "data_boundary": "hosted",
    "usage": {"input_tokens": 1, "output_tokens": 1}
  },
  "suggestions": [
    {
      "candidate_fingerprint": "blake3:...",
      "context_digest": "sha256:...",
      "model_revision": "jev-version-returned-by-provider",
      "opportunity": "needs_review",
      "concern_kind": "unknown",
      "diagnostics": [],
      "opportunity_rationale": {"text": null, "source": "unavailable"},
      "concern_rationale": {"text": null, "source": "unavailable"},
      "provider_scores": {
        "opportunity": null,
        "concern_kind": null
      },
      "score_semantics": {"opportunity": null, "concern_kind": null}
    }
  ]
}
```

Digests in this illustrative example are placeholders, not valid verification
values.
