# Candidate classification contract

Version 1 defines an optional, provider-neutral suggestion artifact for
System One classification of Specification adoption candidates. It is a wire
contract for a future `classify` command; the current CLI does not call Jev,
Laya, GLiNER or another model.

## Authority and metric boundary

The scanner discovers syntax candidates deterministically. A classifier may
suggest one of:

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

V1 reason codes are:

| Label | Allowed reason codes |
| --- | --- |
| `eligible` | `domain_decision`, `repeated_decision`, `stable_policy_boundary` |
| `excluded` | `mechanics`, `local_construct`, `already_specification_backed` |
| `needs_review` | `ambiguous`, `insufficient_context`, `unsupported_syntax`, `sensitive_context_omitted`, `provider_error`, `malformed_provider_output`, `close_decision` |

The rubric's reason-code descriptions have these meanings:

- `domain_decision`: a condition enforces a product or domain rule.
- `repeated_decision`: multiple sites appear to implement the same rule or
  dispatch over the same domain state.
- `stable_policy_boundary`: the rule has a durable responsibility/location
  boundary that could be named and reviewed.
- `mechanics`: the condition handles parsing, I/O, representation, or another
  technical operation without expressing a domain decision.
- `local_construct`: the branch is a small, local control-flow or cleanup
  construct with no independent reusable rule.
- `already_specification_backed`: a recognized Specification already owns the
  rule and this site only applies its result.
- `ambiguous`: available evidence reasonably supports more than one label.
- `insufficient_context`: needed enclosing or related source is unavailable.
- `unsupported_syntax`: the classifier cannot interpret this language
  construct under the current rubric.
- `sensitive_context_omitted`: redaction removed information needed for a
  reliable decision.
- `provider_error`: the provider failed for this candidate.
- `malformed_provider_output`: provider output could not be parsed or did not
  match the result schema.
- `close_decision`: a documented provider-specific abstention threshold was
  crossed. Scores remain provider-specific and are not treated as comparable
  confidence values.

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

The request carries the exact rubric label definitions and reason-code
descriptions alongside their ID, version and digest. This keeps provider
adapters from silently inventing their own label meanings. The position uses
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
- provider, model/checkpoint revision, adapter version, prompt digest,
  inference-configuration digest, run ID and generation time; and
- exactly one suggestion for each candidate submitted in the run.

Each suggestion binds to the scanner fingerprint and a digest of the complete
bounded context. It includes the label and a short rationale. `reason_codes`
are controlled, non-empty diagnostic tags; they supplement prose and do not
change the label's semantics. Optional provider scores retain their original
meaning and are accompanied by `score_semantics`. Do not normalize scores from
different providers into a shared confidence value or treat them as calibrated
probabilities without separate evidence.

Digests are lowercase, algorithm-prefixed hex (`blake3:<64 hex>` or
`sha256:<64 hex>`). The source digest is the scanner's BLAKE3 digest with its
algorithm made explicit. The scan-report digest hashes the exact scanner JSON
bytes read. Rubric, profile and prompt digests hash the exact versioned bytes
used. A context digest hashes the exact normalized candidate context sent to
the provider after truncation/redaction. The inference-configuration digest
hashes the effective allowlisted parameters; common sampling parameters are
also recorded directly. This lets a reviewer identify changed inputs without
copying source code into the result.

If a provider fails for an individual candidate, emit `needs_review` with the
`provider_error` reason code when an artifact can still be produced. Every
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
    "model": "configured-model",
    "model_revision": "checkpoint-or-api-revision",
    "adapter_version": "1.0.0",
    "prompt_digest": "sha256:...",
    "inference_config_digest": "sha256:...",
    "inference_parameters": {
      "temperature": 0.0,
      "top_p": null,
      "max_output_tokens": 256,
      "provider_options_digest": "sha256:..."
    },
    "data_boundary": "hosted"
  },
  "suggestions": [
    {
      "candidate_fingerprint": "blake3:...",
      "context_digest": "sha256:...",
      "label": "needs_review",
      "reason_codes": ["insufficient_context"],
      "rationale": "The enclosing behavior is not available in the bounded context.",
      "provider_scores": null,
      "score_semantics": null
    }
  ]
}
```

Digests in this illustrative example are placeholders, not valid verification
values.
