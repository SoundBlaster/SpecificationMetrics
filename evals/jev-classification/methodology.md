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

## Goal-grounded input contract

A semantic classifier must judge a candidate relative to the system's stated
architectural goal. Without that goal, a model can silently substitute a
generic code-quality objective, such as requiring reuse or an immediate
reduction in complexity before a rule seems suitable for a Specification.

Provide these evidence layers explicitly:

1. **Versioned project intent:** why the target architecture uses named
   Specifications, what durable benefits they provide (for example, uniform
   authoring and management, addressability, observation, or traceability), and
   what remains procedural. State that this profile describes the target style;
   it does not itself prove a code site is a domain rule or that a Specification
   already owns the rule.
2. **Bounded local task and code evidence:** source-grounded information about
   what behavior is being implemented and the exact candidate site. Avoid
   whole-repository context, proposed labels, or refactoring advice that could
   disclose the expected answer.
3. **Structural ownership evidence:** whether an existing Specification owns
   the decision. Keep this separate from semantic suitability. Positive static
   proof can establish ownership; failure to find a recognized constructor is
   unknown, not proof that there is no owner.

Keep classification axes distinct: `opportunity` asks whether a site expresses
a product/domain decision that fits the target Specification style;
`concern_kind` describes the kind of logic; ownership is a separate fact or
filter. Technical mechanics remain outside the opportunity set when they do not
express a product rule. Use `needs_review` when the bounded evidence cannot
resolve the question.

For Jev experiments that test project intent, prefer adding a frozen
`architecture_profile` object to the candidate state while leaving the prompt,
code, task evidence, model, rubric, and label set unchanged. Record the profile
version and digest. The [2026-10-05 intent-profile ablation](runs/2026-10-05-intent-profile-ablation/README.md)
is the first example of this input contract.

## Evidence stages

1. **Source collection:** immutable code, history, exact context and proposed
   annotations. The checked-in corpus is at this stage. Proposals are not gold.
2. **Independent annotation:** reviewers label before seeing model answers;
   retain disagreement, evidence and explicit adjudication. Revise ambiguous
   rubric definitions before freezing a benchmark.
3. **Prompt development:** group-related code into the same split. Use development
   cases to diagnose errors and change one factor per comparison. When testing
   the target architecture's influence, compare the same candidate with and
   without its versioned project-intent profile. Keep the prompt, model, local
   evidence, rubric, and candidate selection fixed. Context length/selection is
   a separate factor. Changing several factors at once cannot attribute the
   effect to one rule.
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

Include boundary controls in each goal-profile comparison: a known inline
product policy, an already-owned Specification, a technical mechanic, and an
ambiguous case where available. A profile is useful only if it helps express
the intended target style without treating every conditional as a Specification
opportunity or overriding ownership evidence. Labels created before the profile
existed answer the earlier question; agreement with them is sensitivity
evidence, not confirmation of the new goal. Obtain independent annotations under
the new profile before making accuracy or rollout claims.

Compare exact Choice labels with reviewed reference labels using deterministic
assertions. Jev probabilities and confidence stay separate and are diagnostic
until calibration is checked. Evaluate abstention using both coverage and error
among non-abstained results; abstaining on every case must not win. Repeated
calls on a fixed subset measure output repeatability, not additional independent
accuracy evidence. Jev's returned model identifier is recorded, but the API does
not provide an immutable checkpoint, so cross-date reproducibility is limited.

Exclude provider and contract failures from the label confusion matrix so a
failed response cannot count as a correct `needs_review` or `unknown` answer.
Report those failures separately, retain all requested cases as the denominator
for overall coverage, and report scored-case count so excluded failures stay
visible. A valid model-selected abstention remains a label and is scored normally.

## Run provenance and budget

Record dataset/split/rubric/prompt digests, exact contexts, requested/returned
model, provider/adapter version, timestamp, failures and token usage. Preserve
raw outputs before later human corrections. The current two-provider comparison
requires one API request per candidate/provider pair, each containing both axes:
60 cases would require **120 hosted requests** per run. The separate
[independent machine-reference experiment](independent-experiment.md) has now
screened 12 development sites with six prompts and confirmed two finalists on
10 held-out sites (92 requests). It did not evaluate all 60 corpus sites.
The corpus's provisional labels cannot support accuracy claims; the separate
machine reference is also not human-approved gold.

The original one-case run is an integration check and sensitivity observation.
Its original context also included a previous diagnostic label, so it is not a
clean independent quality experiment. The exact original input is archived next
to that run; the default smoke fixture now uses source code with labels and
previous classifications excluded from model state.
