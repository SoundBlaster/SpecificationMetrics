# Intent-first native smoke: результаты 2026-10-15

## Что проверили

Четыре известных development-примера SpecGraph × два провайдера. Перед запуском
проверены PR [#62](https://github.com/SoundBlaster/SpecificationMetrics/pull/62),
его head `7b33dbaf6f042daf7ecd8f3d878682bd7a78e2bb`, четыре зелёных CI job,
отсутствие review threads, 12 focused-тестов и воспроизводимость frozen preparation.
Пользователь разрешил запуск: «Проверь и запусти»; запись — [authorization.json](authorization.json).

Состояние и вопросы взяты побайтно из
[подготовленного пакета](../2026-10-15-intent-first-native-preparation-v1/README.md).
Это native-проекция трёх категорий: роль, поддержка роли свидетельствами,
архитектурная рекомендация. Полная rich Annotation v4.1 не запрашивалась.
Integrator labels в wire отсутствуют; это известные разработчику примеры,
а не blind gold или независимый scoring reference.

| Уровень проверки | Наблюдение |
| --- | --- |
| Transport | 8/8 HTTP 200 с JSON, 8 сетевых попыток, 0 повторов |
| Native format / model ID | 8/8 валидны; запрошенные model ID совпали с возвращёнными |
| Probability mass | 0 предупреждений, ничего не нормализовано |
| Совместимость трёх меток | 4/8 согласованы, 4/8 нарушают frozen contract |
| Время batch | 16.010231 s по локальному receipt, последовательно |
| Семантическая accuracy | Не вычислялась; production S/U не менялись |

Использованы `jev-1.13.0` через CoreInfra Typesafe и `gpt-6-luna` через CoreInfra
Decisions. Совпадение ID — свидетельство ответа API, не независимая аттестация
исполненной модели. Разрешённый предел был 8 запросов / максимум 24 попытки.
Неиспользованный запас повторов не расходовали на новые запросы.

## Все восемь результатов

Во всех ответах `evidence_confidence = supported`. Это выбранная ordinal-категория,
а не независимо подтверждённая достаточность контекста и не numeric confidence.

| Target | Провайдер | Роль | Рекомендация | Совместимость меток |
| --- | --- | --- | --- | --- |
| Manifest path, bound application, без документов | Jev | policy | formalize | Да |
| То же | Luna | mechanics | formalize | Нет: established mechanics не обосновывает formalize |
| Gate precedence, shared definition | Luna | policy | formalize | Да |
| То же | Jev | policy | keep_procedural | Нет: keep_procedural требует supported mechanics |
| BDD invalid step, bound findings | Jev | policy | keep_procedural | Нет: keep_procedural требует supported mechanics |
| То же | Luna | policy | formalize | Да; ниже отдельная семантическая проблема |
| YAML newline, shared definition | Luna | mechanics | formalize | Нет: established mechanics не обосновывает formalize |
| То же | Jev | mechanics | keep_procedural | Да |

У каждого провайдера 2/4 согласованных tuples. Это **не 50% accuracy** и не
сравнение качества на генеральной совокупности. `reuse_specification` и
`use_tool_rules` не выбраны ни разу.

## Проблемы на коде

### 1. Противоречивая рекомендация для gate

В `candidate_move` выбран target **`gate != "none"`**. Сокращённая схема исходника:

```python
if gate != "none":
    # gate work имеет precedence
    ...
elif node.status in status_order:
    # обычный refinement
    ...
```

Jev: `policy / supported / keep_procedural`. По принятому контракту это
противоречие: модель признала установленную доменную policy, но выбрала действие,
разрешённое только для mechanics. Formal checker его обнаружил без новой inference.
Luna выбрала согласованное `policy / supported / formalize`.

### 2. Согласованные метки ещё не означают правильную рекомендацию

BDD target — `not step.valid` внутри `BDDScenarioValuesSpec.findings`:

```python
class BDDScenarioValuesSpec(BDDPolicy):
    # findings выбирает invalid steps
    ...

class BDDPolicy(Specification[BDDContext]):
    def _evaluate(self, candidate, recorder):
        return not self.findings(candidate)
```

Это поясняющие сокращения; точные pinned-фрагменты и evaluation path — в
[примерах кода](../../scope-reference-code-examples.md#4-уже-оформленная-policy-невалидный-bdd-step)
и в исходном packet. Цепочка наследования и findings → evaluation присутствует
в supplied context. Здесь уже существует Specification того же решения;
принятая рекомендация — `reuse_specification`, без дополнительной обёртки.

Luna: `policy / supported / formalize`. Tuple формально допустим, но не учитывает
показанную принадлежность существующей Specification. Это отдельное расхождение
с текущим архитектурным решением, которое три метки сами по себе не доказывают.
Jev: `policy / supported / keep_procedural` — уже пойманное противоречие.
У Jev action probabilities близки: keep .43, reuse .39; это наблюдение,
не доказательство причины или внутреннего reasoning.

### 3. Formatting control

```python
if not rendered.endswith("\n"):
    rendered += "\n"
```

Jev: mechanics + keep_procedural; Luna: mechanics + formalize. У Jev решение
согласовано с основным human intent «не создавать новую Specification», хотя
отличается от более точной рекомендации `use_tool_rules`. Это различие granularity,
не основание объявить оба решения одинаково ошибочными. Конфигурация конкретного
formatter для этого правила не проверялась.

Path остаётся отдельно обсуждаемым intent-sensitive примером: выбранный wire
содержит manifest application без документов. Нельзя подставить документы из
другого evidence view и посчитать модель ошибочной по новому контексту.

## Причины: что установлено, а что пока гипотеза

**Факт:** API вернул три отдельных Choice; связь между их выбранными значениями
проверяется после ответа. Wire не передаёт выбранную роль как установленный факт
следующему вопросу. **Не установлено:** как backend совместно или независимо
вычисляет эти ответы. Native format пригоден для транспорта, но сам по себе не
гарантирует ни совместимость меток, ни соблюдение ownership/evaluation path.

**Гипотезы для следующего контролируемого опыта:**

1. Условный выбор действия с явно зафиксированной ролью/support уменьшит
   противоречия относительно текущих одновременных вопросов.
2. Явный проверяемый witness существующей Specification и её evaluation path
   позволит отделить reuse от создания ещё одной спеки.
3. `keep_procedural` модель может понимать как «оставить текущий код», включая
   тело существующей Specification. Контрастные вопросы могут отделить эту
   трактовку от формальной категории «supported mechanics».

**Предлагаемый следующий шаг:** новый versioned offline-пакет с теми же четырьмя
targets и неизменными scope, source и intent: baseline, условная рекомендация,
условная рекомендация с явным ownership witness. Сначала проверка, что witness
действительно следует из supplied source; затем отдельный bounded live budget.
Измерять противоречия и избыточную формализацию уже существующей спеки раздельно.
Не выбирать «лучший prompt» по этим четырём примерам без дальнейшего held-out
набора. Новый опыт в этой задаче **не запускался**, prompts/thresholds не менялись.

Практическое направление: семантические факты получает модель, доступную
принадлежность Specification подтверждает AST/evaluation path, а architectural
recommendation выводит формальная policy. Это будущий вариант дизайна, ещё не
реализованный и не подтверждённый этим smoke.

## Usage и воспроизводимость

Provider-reported tokens: Jev input 12 540 / output 609; Luna input 11 268 /
output 0. Нулевой output у Luna не означает бесплатный вызов. Стоимость API
не предоставлена; billing и фактическое исполнение не аттестованы.

Первичные [responses.jsonl](responses.jsonl), [attempts.jsonl](attempts.jsonl),
[receipt.json](receipt.json) и [native-report.json](native-report.json) сохранены
без исправления ответов. Native inspector намеренно оставляет
`transport_ledger_verified=false`: он не проверяет ledger. Отдельный
[analysis.json](analysis.json) воспроизводится run-specific offline script:
он связывает ровно восемь локальных success lifecycle groups с response rows,
receipt, wire hashes и frozen preparation. Это локальная проверка записей,
не независимое доказательство выполнения или списаний у провайдера.

Из `evals/jev-classification`, без API key и сетевых запросов:

```sh
../../.venv/bin/python runs/2026-10-15-intent-first-native-smoke-v1/verify_results.py
```

`SHA256SUMS` включает весь набор файлов кроме самого inventory. Script сверяет
native replay, производные числа и полный inventory; CI выполняет только offline replay.
