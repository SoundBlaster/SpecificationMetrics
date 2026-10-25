# Search for real `not_linked` controls, 2026-10-25

## Outcome

**No new real `not_linked` example was confirmed in this bounded search.**
The original corpus and independent labels remain unchanged. Four close
candidates are explicitly unresolved, not accepted negatives. A fifth check
is a positive control. No analyzer, metric, provider or CI behavior was changed.

| Search / check | Observed scope |
| --- | ---: |
| Current matching Python files in local GitHub directories | 8 |
| Syntactic `.decide` calls in those files | 20 |
| SpecGraph commits selected by the history query | 24 |
| Unique historical `(path, source hash)` versions | 29 |
| Distinct historical paths | 19 |
| Historical call observations inspected | 42 |
| Selected source sites replayed through the analyzer | 5 |
| Replayed statuses | 1 linked, 4 unresolved, 0 not linked |

These counts overlap: current sources, historical observations and previous
corpus cases are not independent samples and must not be summed into a new
benchmark size. This is source discovery plus five author-labeled checks,
not an independent annotation run or an exhaustive proof that no such code
exists in any project or upstream history.

## Scope and provenance

The current-source search used `rg --hidden --no-ignore` for `FirstMatch` or
`.decide(` in Python under `~/Development/GitHub`, excluding `.git`, `.venv`,
`venv`, `.worktrees`, `node_modules`, `dist`, `build`, `target`, `site-packages`,
`.cache`, `evals` and `.0al`. It did not follow symlinks. All eight selected
files matched their recorded Git revision bytes. See
[current-discovery.json](current-discovery.json).

The hits were in SpycificationCore, SpecGraph and cctally. Library definitions
and exports can match `FirstMatch` without containing a `.decide` call. cctally
uses a different API; its method name does not prove FirstMatch identity.

The deeper history pass was specifically **SpecGraph's locally available
reachable history**, selected with:

```sh
git log --all --format=%H -G '\.decide\(' -- '*.py'
```

For each selected commit, inspect Python paths changed by `git diff-tree -r
--root`, reading their post-commit and first-parent versions. Retain versions
containing the literal `.decide(`; parse them with Python AST; deduplicate by
`(path, SHA-256)`. Record call anchors, statement/owner shapes, assignment targets
and following statements. The pass had **zero syntax errors**.

[history-discovery.json](history-discovery.json) preserves the exact 24 commit
identities and all 29 source-version hashes, observations and source excerpts.
There was no network fetch. This method does not enumerate every commit tree,
unreachable object, uncommitted worktree or alternate whitespace/dynamic-call
spelling. The deeper history totals apply to SpecGraph only.

Source material keeps its upstream license; the existing
[SpecGraph license copy](../../licenses/specgraph.txt) applies to its excerpts.
All source repositories were read only. No Python project code was imported
or executed; AST inspection is parsing, and analyzer runs inspect source bytes.

## Why the closest candidates are not negatives

### A reused variable can already have been consumed

At SpecGraph `2a4789e665a135664ea5096b220c5cd643316da8`,
`tools/publication_delivery_evidence.py:121–140` selects each test-case result,
saves it in a list at line 131, and then reuses the name for the suite result:

```python
        results.append({**item, "result": result})
    result = TEST_SUITE_SPEC.decide(
```

This is an exact adjacent source fragment. The earlier result is already
retained in `results`. Reassignment of the local name after the loop does not
prove a lost or unused decision. The current bounded analyzer stops at the
append call for the per-case binding and at `return` for the suite binding.
Both are **unresolved**, rather than false `not_linked` examples.

### A different intervening computation is still a barrier

At SpecGraph `e12a006dc4db24934454e3c73ddaa4050fbbd098`,
`tools/metric_packs/legacy_verifiability.py:47–49`:

```python
        status = SCORE_STATUS_SPEC.decide(ScoreThreshold(score, context.minimum_score)).value
        counts = Counter(item.status for item in context.observations)
        return VerifiabilityResult(
```

The returned result contains `status`. The analyzer does not propagate through
the intervening `Counter(...)` call or into the constructor arguments. This is
another **unresolved** supported-factory binding, not evidence of non-use.

### Scope-end syntax alone is insufficient

The last assignment in an `if` body at
`tools/publication_delivery_evidence.py:289` initially looks like a scope-end
negative. An origin nested inside that `if` is outside the supported direct
function/loop-body subset. It must remain unresolved for scope, even though
there is no following statement in that small block.

## Frozen checks and actual observations

[expected-checks.json](expected-checks.json) was committed as `0cfd47a` before
the five-site replay. It pins two source revisions, selected dependency files
and their hashes, and expected statuses/reasons. The analyzer binary hash
matches the previously recorded loop/enum implementation at `1bc73af`.

| Site | Source line | Actual status | Reason |
| --- | ---: | --- | --- |
| Delivery binding-error guard | 58 | linked | supported next if |
| Per-case result, then list append | 121 | unresolved | expression/call barrier |
| Suite result, then return | 132 | unresolved | return barrier |
| Result assigned in an if body | 289 | unresolved | unsupported origin scope |
| Legacy metric status, then Counter | 47 | unresolved | expression/call barrier |

All five expectations matched. [assessment.json](assessment.json) retains
application IDs, source/scope digests, exact stop anchors, report hashes and
binary hash. The two snapshots were non-provisional. Full unmodified source
snapshots and CLI reports remain in the task-scoped TB5 artifacts. This is not
a dynamic replay of all 42 historical observations.

`not_linked` only describes invalidation of a tracked definition or absence of
a supported next branch before the supported block ends. It is not a synonym
for dead code, dead specifications, unused values or absence of any semantic
consumer. `unresolved` is not a negative label. Raw S/U and the original corpus
remain unchanged.

## Next step

Keep real-negative availability at zero. For controlled negative evaluation,
derive explicitly marked **synthetic counterfactuals** from the unchanged real
positive examples: insert an overwrite or deletion between the original binding
and its branch. Keep source provenance and mutation identity, and report those
cases separately from real observations. The existing Rust regression tests
already cover invalidation syntax; such pairs would add a source-backed
evaluation dataset, not a new claim that real bugs were found.
