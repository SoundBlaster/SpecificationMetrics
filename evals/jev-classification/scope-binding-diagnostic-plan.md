# Scope-binding diagnostic v3 — offline preparation

## Вопрос

Различаем ли мы ответственность общего определения predicate и роль того же
predicate при конкретном применении? Мотивация — consumer-only разногласие в
[PR #56](https://github.com/SoundBlaster/SpecificationMetrics/pull/56), но v3 не
читает результаты #56 и не использует прежние метки в packets или критериях.
Никакой результат v2 не переименован и не объявлен новым gold.

Подготовка находится в `runs/2026-10-14-scope-binding-preparation-v3/`;
source witnesses — в `runs/2026-10-14-scope-binding-evidence-v3/`.

## Операциональное определение единицы

- `shared_definition`: оценить всё выбранное выражение как часть общего
  определения с учётом всех **показанных** применений. Полнота call graph не
  заявляется; неизвестные uses не нужно изобретать.
- `bound_application`: оценить то же выражение для указанного аргумента/receiver
  в одном статически привязанном вызове. Объект оценки не меняется на весь caller
  или на сам call expression. Другие uses видимы, но их роль не переносится
  автоматически на выбранное применение.

Binding содержит точные revision/path/line/column, AST identity, source code и
formal-argument expression. Это факты статического соответствия, не утверждение
о runtime execution, domain intent или рекомендованной метке. BDD receiver
привязан через явный член `POLICIES` и iteration `policy`; это условный static
member path, не доказательство реального вызова для конкретного документа.

| Семейство | Выражение | Выбранное применение |
| --- | --- | --- |
| Manifest path | Полный BoolOp в `_safe_path` | `_manifest_files`: `_safe_path(row.get("path"))` |
| Workspace gate | `gate != "none"` в `candidate_move` | `build_product_workspace_next_moves`: `candidate_move(node, ...)` |
| BDD values | `not step.valid` в `BDDScenarioValuesSpec.findings` | `evaluate`: `policy.findings(context)` при выбранном члене `POLICIES` |
| YAML formatting | Полный newline predicate в `dump_canonical_yaml` | `lint_file`: `dump_canonical_yaml(data)` |

Полные snapshots пяти Python-файлов сохранены как JSON data, не выполняются и
не передаются аннотаторам. Их хеши сверены с прежним catalog pinned SpecGraph
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`. AST связывает exact expression и
callsite с конкретным определением/caller, проверяет первый formal argument;
для BDD дополнительно проверяет member construction и receiver iteration.
Это не sound interprocedural analysis: imports, monkey-patching, runtime values
и все возможные dispatch paths не сертифицируются.

## Контролируемое сравнение

| Cell | Единица | Документы |
| --- | --- | --- |
| 01 | shared_definition | нет |
| 02 | shared_definition | есть |
| 03 | bound_application | нет |
| 04 | bound_application | есть |

Код, полный набор consumers и сами binding facts одинаковы во всех четырёх
вариантах одного target. Scope меняет только поле `unit`; documents добавляют
только documentary fragments. Исходные expressions, profile и наборы labels
не меняются. Новая rubric v3 добавляет одинаковую scope-инструкцию обеим осям;
это отдельная task version, а не правка прежней rubric v2.

12 свежих контекстов × 4 независимых семейства = **48 планируемых аннотаций**.
Каждый контекст получает все четыре cells на разных families, одну view на
семейство. Каждый target-cell встречается три раза. Также сбалансированы
маргинальные target-position и cell-position counts (по три).
**Target-cell×position полностью не покрыт**: три повторения не покрывают четыре
позиции. Следовательно, опыт не изолирует order effects и внутренний reasoning
модели. Agreement и больший decisive coverage не доказывают semantic correctness.

Сравнения 01↔03 и 02↔04 показывают различия между scope units; 01↔02 и 03↔04 —
между documentary contexts. Отчёт обязан сохранить обе оси, все abstentions,
разногласия и denominator 3 per target-cell. Нельзя pooling разных семейств в
общий treatment effect. Сравнение с v2 только описательное: изменены rubric и
факторный дизайн. Scope не меняет саму наблюдаемую логику приложения.

## Интерпретация и критерии

В `study-plan.json` заранее записаны neutral manual checks: assigned scope,
source-backed role witness, отдельная same-decision ownership и provenance.
Никакой cell не имеет желаемого или ожидаемого label. Ни документы, ни metadata
не должны гарантировать policy, eligible, mechanics или exclusion.

Если application scope сохраняет разногласие о manifest admissibility, scope
не объясняет проблему полностью — далее нужен review evidence sufficiency.
Если scope не меняет labels и аргументацию, это evidence против его практической
полезности в этом small-n опыте. Даже единогласие не заменяет reference/adjudication.
Производственные U/S не меняются: несколько role bindings одного expression
не превращаются в дополнительные кандидаты или Specifications.

## Текущая готовность

Выполнена **подготовка**, разметка не начата. Templates blank, agent IDs пусты,
provider requests = 0, gold/reference/metric effects отсутствуют.
`dispatch_ready` намеренно false: существующий handoff и attempt-validator
зафиксированы на v2, их нельзя применять к этим новым packets как будто задача
не изменилась. Следующий coding slice — scope-aware actual-file handoff и
retained-attempt validation; до него эти файлы не являются готовым запуском.

```sh
# Из evals/jev-classification, в repository virtualenv:
rtk proxy ../../.venv/bin/python prepare_scope_binding_diagnostic.py
rtk proxy ../../.venv/bin/python -m unittest -v test_scope_binding_diagnostic.py
```

`--write --run NEW_DIRECTORY` создаёт новый каталог эксклюзивно; существующие
пакеты не перезаписываются. Replay проверяет точный набор файлов и bytes,
producer/input hashes и статические source bindings. CI выполняет эти же
offline checks без SpecGraph checkout, сети, модели или credentials.

## Урок подготовки: AST identity и Python versions

До публикации воспроизведено различие сериализации:

- Python 3.10.19: `ast.dump` для `f(x)` включает `keywords=[]`;
- Python 3.14.8: тот же dump опускает это пустое поле.

Причина подтверждена двумя локальными AST probes: хеш текстового dump зависел
от форматирования backend, хотя выражение не менялось. Первую неопубликованную
сборку и её исходный producer сохранили локально, без raw annotations или
изменения какого-либо завершённого эксперимента.

Исправление — canonical AST fields с явным node type, без location attributes,
None и пустых списков; source span проверяется отдельно. Добавлен regression,
запрещающий зависеть от `ast.dump` и location для AST identity. Все девять
сохранённых anchors совпали в targeted Python 3.10/3.14 compatibility check.
Это не обещание совместимости со всеми будущими изменениями Python grammar.
