# First live Jev comparison: `publication.site.069`

- Ran: 2026-10-04 00:30 MSK
- Promptfoo: `0.123.1`
- Requested and returned Jev model: `jev-1.13.0`
- Promptfoo eval ID: `eval-58A-2026-10-03T21:30:40`
- Requests: 2, one per opportunity prompt; each request contained both Choice questions.
- Dataset: one SpecGraph candidate with `pilot_hypothesis` labels `eligible` / `policy`.
- Original input: [`2026-10-04-publication-site-069.inputs.json`](2026-10-04-publication-site-069.inputs.json).

Subsequent source-corpus inspection found that the original model state included
`prior_diagnostic.category = "policy"`. That exposes a prior proposed label to
the classifier. These responses are integration/sensitivity observations, not
independent quality evidence; the unchanged `policy` result may reflect that
hint. The default fixture now contains pinned source instead and excludes prior
diagnoses. This run was not repeated on the new input.

| Prompt | Opportunity Choice | Opportunity distribution | Jev confidence | Concern kind | Concern distribution | Input / output tokens |
| --- | --- | --- | ---: | --- | --- | ---: |
| `baseline-v1` | `eligible` | eligible 0.64, excluded 0.21, needs_review 0.15 | 0.47 | `policy` | policy 0.99, mechanics 0.01, other 0.00 | 834 / 90 |
| `boundary-test-v2` | `eligible` | eligible 0.44, excluded 0.42, needs_review 0.14 | 0.16 | `policy` | policy 0.99, mechanics 0.01, other 0.00 | 911 / 90 |

Both prompts selected the pilot labels, so both Promptfoo assertions passed.
The boundary-focused wording did **not** make the opportunity decision
clearer in this run: the expected `eligible` probability fell by 0.20 while
`excluded` rose by 0.21. The concern-kind judgment stayed effectively
unchanged. The `confidence` field is shown separately from the Choice
probabilities and must not be read as the probability of the selected label.
The token counts above come from Jev response metadata; the initial Promptfoo
output did not aggregate them until the provider's `tokenUsage` mapping was
added afterward.

This is one provisional example and one call per prompt. It shows a difference
on this input, not general prompt quality or classifier accuracy. The prompt
comparison also used sequential requests, so a repeat or a balanced set of
independently reviewed examples is needed before drawing a broader conclusion.
