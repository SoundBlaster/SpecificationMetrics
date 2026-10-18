# Evaluation failure learning

- Treat a failing test or semantic criterion as evidence to investigate. Preserve
  its exact inputs, producer/reference versions and observed failure first.
- Reproduce a software failure with the smallest relevant case. Distinguish a
  confirmed cause from a hypothesis or an unresolved cause. A provider's label
  alone does not establish its internal reasoning.
- Record the lesson in `failure-learning.md` or the experiment's diagnosis,
  linking evidence, cause status, correction/prevention and verification.
- For a confirmed implementation defect, make a bounded prevention patch and
  add or name a regression check that exercises the original failure. Fix the
  shared cause where appropriate, rather than every observed symptom.
- For an unresolved semantic failure, prepare a controlled diagnostic before
  changing prompts, thresholds or context gates. Keep raw model outputs separate
  from an orchestration gate's effects. Missing context does not automatically
  imply a particular gold label.
- Preserve frozen experiments and references. A changed acceptance/scoring rule
  requires a new version; it must not rewrite historical failures as successes.
- Offline preparation does not authorize inference. Use explicit user approval
  and a frozen bounded run for paid provider calls.
- For context-ablation references, do not expose several evidence views of the
  same target to one annotator. Deliver one packet/template to each fresh
  annotation context, with a balanced mixture of evidence modes across targets;
  do not correlate one annotator with one evidence mode. Keep the combined
  catalog and mapping with the integrator. Document the actual isolation boundary.
- Annotation integrity is not design qualification. Before paired quality scoring,
  require a versioned qualification based on actual annotator identities/mode
  exposure; logical slots or fresh invocation IDs do not establish participant
  crossover. Preserve unqualified runs as diagnostics, and do not score H1/H2
  from their existence, agreement or a self-asserted reference status.
- When varying helper/type-definition visibility, do not group targets sharing
  that hidden dependency if another case reveals it. Balance evidence modes
  across distinct dependency families and check for direct definition leakage;
  case-local instructions alone do not prevent it.
