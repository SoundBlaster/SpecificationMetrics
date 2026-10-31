# SpecGraph pilot after PR 843

On 2026-10-31 we compared SpecGraph `59ae0f661844db0fde5f64b7dd52ee24a7b8fcbe` (the original flow corpus revision) with `4add3afee736b9a97a0b6750c435e985959254cd` (PR 843). Both runs used the entire tracked application scope at repository root. The earlier selected-file corpus used narrower source and import roots.

| Repository-scope observation | Original revision | PR 843 |
| --- | ---: | ---: |
| Application files | 176 | 221 |
| Python files analyzed by flow | 174 | 219 |
| S, all classified live | 119 | 127 |
| U | 10169 | 10676 |
| S/U | 0.01170223 | 0.01189584 |
| Examined decide calls | 20 | 21 |
| Immediate bindings | 15 | 16 |
| Linked / unresolved / not linked (both profiles) | 4 / 11 / 0 | 4 / 12 / 0 |

At PR 843 the profiles produced identical call inventories and identical status for each binding. The alias profile recorded zero propagation events. Six rows lacked evidence for the origin, five stopped at control flow or an effect, and one stopped at an intervening expression. In the new SpecDraft display policy the analyzer recognizes the decision, then stops at the assertion before the return. The source shows that the caller consumes the payload. [SpecDraft display policy](https://github.com/0al-spec/SpecGraph/blob/4add3afee736b9a97a0b6750c435e985959254cd/tools/specdraft_preview/display_state.py#L21)

## Typed predicate factories

Three new named rules use `PredicateSpec[T](...)` and have explicit call sites. The v9 S inventory omitted their definition files. Two predicates govern the invalid/unavailable outcome in project ontology context capture. The third checks input compatibility for report freshness. [Context outcome](https://github.com/0al-spec/SpecGraph/blob/4add3afee736b9a97a0b6750c435e985959254cd/tools/project_ontology_context/capture.py#L291) · [Report freshness](https://github.com/0al-spec/SpecGraph/blob/4add3afee736b9a97a0b6750c435e985959254cd/tools/project_ontology_report_freshness.py#L269)

In two isolated, single-file scans using the head manifest, the following static fixture under v9 produced zero definitions with the subscript and one live definition after removing only `[ContextFacts]`. Both reports had empty parse and scope issue lists.

```python
from specification_core import PredicateSpec
class ContextFacts: pass
RULE = PredicateSpec[ContextFacts](lambda facts: bool(facts), name="probe")
def check(facts):
    return RULE.is_satisfied_by(facts)
```

## Remeasurement on the PR 843 snapshot

Counting rule v10 recognizes typed calls whose constructor resolves to `specification_core.PredicateSpec`. The repeat measurement used the same SpecGraph revision (`4add3afe`), source digest and scope manifest as the PR 843 column above. [SpecificationMetrics fix #113](https://github.com/SoundBlaster/SpecificationMetrics/pull/113)

| Counting rule | S | U | S/U |
| --- | ---: | ---: | ---: |
| v9 | 127 | 10676 | 0.01189584 |
| v10 | 130 | 10676 | 0.01217685 |

The three additional factory sites are `INVALID_SPEC`, `UNAVAILABLE_SPEC` and `REPORT_INPUTS_COMPATIBLE_SPEC`. Both runs found 10,700 candidates, including 24 inside recognized Specifications. The increase in S therefore measures the analyzer correction on identical application code.

## Reproduction

Use SpecificationMetrics `ac0996cb5485e3dba1b528d1f38a7c69ebae72a6` and export each SpecGraph revision with `git archive` into a fresh directory. For each snapshot run:

```sh
specification-metrics measure "$snapshot" --scope-manifest "$snapshot/scopes/specificationmetrics.toml"
specification-metrics application-sites "$snapshot" --scope-manifest "$snapshot/scopes/specificationmetrics.toml" --profile python-decision-flow-v1
specification-metrics application-sites "$snapshot" --scope-manifest "$snapshot/scopes/specificationmetrics.toml" --profile python-decision-flow-alias-v1
```

Both original measurements reported counting rule 9, zero reviewed exclusions and `provisional: false`. The two manifests shared digest `f7fe04b2f442ae87b91efc8257f297c0cda10a520796a8ec72dfd66f6cd8d73e`. The measured source digests were `4cfae437d55dd3aadc8663ebe70fb1cafdd89ed1650f9d13a9ffad114961a774` and `bfa650679971f2b64f18f6416dbe9fe6a91a994e19287670b3d81c9f535d8c68`. Revision provenance comes from the Git archives.

To reproduce the v10 row, build SpecificationMetrics at the merged fix `f2a114df0535daf9b6e0c02dafb31a392e38ca53` and repeat the `measure` command on the PR 843 snapshot.
