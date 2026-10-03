# Jev candidate-classification evaluation protocol

## Objective

Evaluate whether Jev can triage real source sites into remaining Specification
opportunities, mechanical/already-owned exclusions and cases needing review.
The initial application is discovery assistance: human-reviewed registry entries
remain authoritative. Concern kind is evaluated independently; it never changes
the denominator on its own.

Primary outcome: recall of independently reviewed eligible opportunities.
Guardrails: eligible precision, false exclusions, abstention rate and reviewer
workload. Report a confusion matrix and per-class scores, including macro-F1,
for each axis. A deliberately balanced challenge corpus cannot estimate natural
production prevalence or workload without a separate representative sample.

## Evidence stages

1. **Source collection:** immutable code, history, exact context and proposed
   annotations. The checked-in corpus is at this stage. Proposals are not gold.
2. **Independent annotation:** reviewers label before seeing model answers;
   retain disagreement, evidence and explicit adjudication. Revise ambiguous
   rubric definitions before freezing a benchmark.
3. **Prompt development:** group-related code into the same split. Use development
   cases to diagnose errors and change one factor per comparison. Keep state,
   model identifier and label criteria fixed while testing instruction changes.
   Context length/selection is a separate factor. Changing several instructions
   at once compares complete prompts but cannot attribute the effect to one rule.
4. **Confirmation:** freeze prompt candidates, rubric, labels, group split and
   selection policy before evaluating the holdout. Compare candidates on paired
   cases and estimate uncertainty by resampling whole source families, not
   treating correlated before/after snippets as independent observations.
5. **Operational sampling:** assess the classifier on naturally sampled scanner
   candidates and human correction/review rates before adopting a threshold.

## Selection criteria

Define acceptable miss rate and review burden before unlocking the holdout.
Because discovery only proposes candidates, missed eligible rules are the
primary concern, while false positives mainly consume review time. These costs
change if classification later becomes a gate or performs writes. Do not invent
a target threshold from a single run or change it after seeing the holdout.

The first source batch diagnoses failure types and annotation disagreements;
its size does not guarantee enough statistical power for small prompt gains.
Expand independent families when comparison intervals are too broad. An
inconclusive difference remains inconclusive. Report operational errors separately
from semantic labels, rather than dropping failed requests from the sample.

Compare exact Choice labels with reviewed reference labels using deterministic
assertions. Jev probabilities and confidence stay separate and are diagnostic
until calibration is checked. Evaluate abstention using both coverage and error
among non-abstained results; abstaining on every case must not win. Repeated
calls on a fixed subset measure output repeatability, not additional independent
accuracy evidence. Jev's returned model identifier is recorded, but the API does
not provide an immutable checkpoint, so cross-date reproducibility is limited.

## Run provenance and budget

Record dataset/split/rubric/prompt digests, exact contexts, requested/returned
model, provider/adapter version, timestamp, failures and token usage. Preserve
raw outputs before later human corrections. The current two-provider comparison
requires one API request per candidate/provider pair, each containing both axes:
60 cases would require **120 hosted requests** per run. No corpus run has been
performed. The corpus's provisional labels cannot support accuracy claims.

The original one-case run is an integration check and sensitivity observation.
Its original context also included a previous diagnostic label, so it is not a
clean independent quality experiment. The exact original input is archived next
to that run; the default smoke fixture now uses source code with labels and
previous classifications excluded from model state.
