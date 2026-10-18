# Configuration qualification v2 and repeatability pilot

Follow-up: the user subsequently authorized
[24 Sol 6.1 Medium repeats](runs/2026-10-18-sol61-medium-repeatability-v1/README.md).
That separate cohort completed with 8/8 unanimous views and source-checked
witnesses. The frozen v2 assessment below remains the pre-execution assessment;
new explicit model settings do not retroactively attest the historical backend.

## Correction of the identity unit

[Qualification v1](paired-reference-qualification-v1.md) treated every fresh
agent ID as a different stable annotator and rejected the eight-context run
because no ID received both evidence modes. That is appropriate for tracking
exposure of persistent participants, but **does not establish LLM configuration
confounding**. A new invocation is an execution/context, not necessarily a new
annotation policy. Reusing a context to make its ID cross modes would introduce
evidence carryover instead of fixing this.

V2 groups the controlled annotation configuration: model selection, reasoning,
decoding parameters, context policy, common brief, rubric and prompt shape.
Agent IDs remain execution provenance. Case IDs, packet hashes, evidence modes,
results and task-specific paths are excluded from the configuration fingerprint:
otherwise the experimental treatment itself would manufacture different raters.

For the recorded run, all eight dispatch events requested the same inherited
settings without overrides. The one **requested configuration** group contains
4 baseline and 4 retrieval contexts. Actual model ID, reasoning, backend revision
and decoding parameters were not exposed. Null fields mean unavailable, not
equal verified backend settings. V2 therefore removes the identity-only rejection
without claiming runtime equivalence, repeatability, absence of all bias, or
semantic truth. Historical baseline-first waves also leave time/order effects
unestimated. The existing 0/16 cross-view differences are **not** repeated
observations of the same input.

Frozen output: [qualification v2](runs/2026-10-18-paired-reference-qualification-v2/qualification.json).
The raw annotations, qualification v1 and scoring v1 remain byte-for-byte intact.
The current assessment is `requested_configuration_balanced_repeatability_pending`.
H1/H2 scoring stays unavailable on this provisional reference. V2 supersedes the
identity-unit interpretation, not past scoring receipts. A later accepted
reference needs a new consumer contract; scoring v1 still consumes qualification
v1 by design. H3 transport checks are independent of this correction.

## Prepared study: 8 views × 3 fresh repeats

[Plan and receipt](runs/2026-10-18-paired-reference-repeatability-v1/plan.json)
freeze **24 new contexts**, with no automatic retries, dispatch or provider calls.
The historical eight results do not count as repeats: their backend settings are
opaque, and their outputs are hidden from the new annotators.

Before dispatch, bind one explicit requested model and reasoning effort plus all
controlled settings for the entire cohort in a new execution record. Freeze it
before the first output; use its canonical SHA-256 on every result. Record
available provider/model revision, actual settings, tool/runtime information and
seed separately from requested settings. Unsupported fields stay explicitly
unavailable. Do not invent temperature/seed defaults. A settings change requires
a separate cohort/version, not pooling. Unavailable runtime metadata limits the
claim to repeatability under the recorded requested configuration.

Each task gets only its copied prompt and four assigned files: the original
brief, rubric, packet and blank template. Neither integrator mapping nor old
results/adjudication go into the prompt. Every context is fresh (`fork_turns=none`)
and handles one view; no memory search, other files, tools executing source,
cross-task messages or delegation. The shared filesystem is instruction-bounded,
not an OS sandbox. Record that limitation rather than assert audited isolation.

There are three deterministic blocks, each containing all eight views and equal
mode counts. V1 intended per-case first-mode alternation, but its frozen schedule
kept R03 baseline-first and R04 retrieval-first in every block. For future runs,
use the [portable, counterbalanced v2 preparation](../../docs/portable-repeatability-v2.md).
The historical schedule and labels remain unchanged; order effects are unestimated.
This interleaves modes across time. Separate fresh contexts prevent direct
cross-view memory; block effects can still be described, not estimated reliably
from this small cohort. The frozen task order and all exact input/prompt hashes
are integrator-only. Reuse of original view IDs is harmless because annotators
see no mapping or previous labels.

## Measurements and decisions, fixed before observation

| Measurement | Definition | Planned denominator |
|---|---|---:|
| Primary stability | All three labels agree on `concern_kind` and `ownership` within each view | 8 views |
| Per-axis pair agreement | Equal labels in each of the three same-view repeat pairs | 24 pairs per axis |
| Primary pair agreement | The preceding counts for the two primary axes | 48 axis pairs |
| All-axis agreement | Also includes support and tool responsibility | 96 axis pairs |

Primary stability passes this **pilot criterion** only when all eight views have
unanimous primary labels. This is a conservative rule for reusing a small
reference, not a statistical reliability guarantee. Secondary differences remain
visible even when the primary criterion passes; inspect every disagreement.
Unknown-to-unknown can be stable without resolving any fact. Identical wrong
answers can also be perfectly stable. Do not infer accuracy, calibrated error
probability, population effects, or 96 independent observations: these are eight
views nested in four targets, including the shared R02/R03 dependency family.
This control cohort already has a baseline-sufficiency ceiling; repeatability
will not turn it into a stronger test of retrieval gains.

An incomplete/invalid cohort is not evaluable; preserve planned denominators and
failed attempts rather than silently replace or drop results. No majority vote
automatically changes a reference. Seal raw outputs against execution identity,
input hashes and configuration binding; verify categories, quotes, physical line
spans and consistency, then review differences against supplied evidence.

`agreement(plan, rows, configuration_sha256)` is **label arithmetic only**. It
rejects repeated contexts, unplanned/duplicate tasks, input/configuration drift
and invalid categories. It exposes incomplete denominators and per-view distinct
labels; it does not verify raw output receipts, source witnesses or runtime
attestation, and always returns `paired_quality_scoring_allowed=false`. Its
synthetic tests are not completed annotations. There is intentionally no CLI
that promotes these diagnostics into an authoritative reference.

## Offline verification

Use the repository virtual environment and TB5 cache environment as required by
the workspace instructions. From `evals/jev-classification`:

```bash
../../.venv/bin/python -W error -m unittest -v \
  test_paired_reference_qualification_v2.py test_paired_reference_repeatability_v1.py
../../.venv/bin/python paired_reference_qualification_v2.py \
  --verify runs/2026-10-18-paired-reference-qualification-v2
../../.venv/bin/python paired_reference_repeatability_v1.py \
  --verify runs/2026-10-18-paired-reference-repeatability-v1
```

Both CLIs only freeze/verify local artifacts. Neither imports a model runtime nor
dispatches agents or accesses credentials/network. CI runs the same offline
checks. Next: authorize/bind the annotation configuration, execute the 24 prepared
tasks, audit their evidence, and adjudicate disagreements before proposing a new
reference/scoring version.
