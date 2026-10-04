# SpecGraph source corpus

This purposively selected challenge corpus contains **60 Python code sites in
34 decision families** from SpecGraph history and a pinned current snapshot.
It is a source inventory for independent annotation, not a gold benchmark or a
representative sample of the scanner's production candidate population.

| Selection role | Cases |
| --- | ---: |
| Before a historical extraction | 15 |
| Already expressed with SpecificationCore at that extraction commit | 15 |
| Current parsing, representation, I/O and aggregation | 17 |
| Current inline domain/authority/lifecycle rules | 9 |
| Mixed or context-sensitive boundary cases | 4 |

The fifteen historical pairs include eight lifecycle-state functions,
pre-SIB, acceptance-criterion repair, unsupported-claim repair, preview-operation
dispatch, candidate-quality state, no-op handoff and ontology counts. Each pair
uses the actual refactoring commit and its first parent. Current code is pinned
to `a5ab64363d054bae759b81441da6b79dbd4a9e86`; the workspace-allocation
guard is pinned to PR #762 head `9b285a2e018331460c1a6bee46a697b24a26d3fb`.

Do not label a site eligible merely because somebody previously extracted it.
For example, the ontology-counting pair is provisionally mechanics/excluded
both before and after extraction. Preview-operation dispatch is provisionally
needs_review before extraction: routing graph mutations may belong to operation
types rather than policy specifications. Already-owned rules are negative
controls for *remaining opportunities*, although their concern kind may be policy.

## Source and reproduction

`selection.json` defines full commit SHAs, AST declaration/statement selectors,
explicit supporting declarations and agent-proposed labels. `cases.json` is a
Promptfoo dataset with exact code excerpts, line ranges, source links, source
file/excerpt/context SHA-256 digests and family IDs. Source imports and selected
supporting declarations form the model context. Unlisted callers and dependencies
remain omitted; there is no claim that bounded context includes the full program.

From the eval directory, verify every input against a local clone without
checking out a branch or executing SpecGraph code:

```bash
python3 build_specgraph_corpus.py --repo /path/to/SpecGraph --check
```

Omit `--check` to rebuild the source dataset. Git objects for the pinned revisions
must already be present. This command does not fetch, call Jev, or change the
SpecGraph checkout. Source links and history establish provenance; they do not
prove refactor parity or label correctness.

## Independent annotation

1. Give reviewers `review.md` and a separate copy of `review-template.json`.
   The packet shows exact source and supporting code, without proposed labels,
   history roles, family IDs or earlier classifier output.
2. Reviewers apply the opportunity and concern-kind definitions in the
   [classification contract](../../../docs/candidate-classification-contract.md),
   record both labels and evidence/missing context before seeing Jev answers or
   the agent-proposed labels in `cases.json`/`selection.json`.
3. Preserve disagreements and adjudicate them explicitly. The original source
   dataset still retains `pilot_hypothesis`, `unreviewed`, `unassigned` metadata.
   A separate [independent machine-reference experiment](../independent-experiment.md)
   records one blind model annotation and frozen family splits without promoting
   these original hypotheses. Human review/adjudication remains outstanding.
4. Partition by complete decision family after annotation. All lifecycle-state
   examples belong to one family because they call each other. Before/after
   pairs and related repeated checks must not cross development/holdout splits.
5. Freeze the reviewed labels, rubric and holdout manifest before tuning prompts.
   Add a separate naturally sampled candidate batch before estimating production
   precision, class prevalence or reviewer workload.

The hypotheses currently contain 22 eligible, 33 excluded and 5 needs_review
labels. These counts describe proposed labels, not model output or validated
class prevalence. The concern-kind hypotheses are 35 policy, 19 mechanics,
2 variant_behavior and 4 unknown; more independent variant examples are needed
before judging that class.

## Licensing

Source excerpts are from `0al-spec/SpecGraph` under **Apache-2.0**. A complete
copy of its license is provided as `LICENSE.SpecGraph`. Upstream has no root
NOTICE file at the pinned main snapshot. Excerpt code is unmodified; source has
been selected and packaged as evaluation fixtures with new metadata and proposed
annotations. SpecificationMetrics' MIT license covers its own tooling and
annotations and does not replace the source excerpts' Apache-2.0 license.
