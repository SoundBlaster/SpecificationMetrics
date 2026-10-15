# Conditional native action v2: live results, 2026-10-15

## Результат в двух словах

**Улучшения есть, полного выполнения H1 нет.** Явное связывание с ролью помогло
части решений; видимый ownership witness помог Luna выбрать существующую BDD
Specification. Обе модели не соблюли заданные premises path-примера, поэтому
строгий критерий H1 не выполнен. Acceptance после наблюдения не меняли.

| Уровень | Результат |
| --- | --- |
| Завершение / HTTP JSON | 18/18, HTTP 200 |
| Native shape / returned model ID | 18/18 валидны, model IDs совпали с запрошенными |
| Network attempts / TLS retries | 18 / 0, в пределах 18 requests / max 54 attempts |
| Probability mass warnings | 0, нормализации не было |
| Согласованные returned tuples | 12/18; это не semantic accuracy |
| Локальное wall time | 42.2383 s, последовательный batch |

Jev: `jev-1.13.0` через CoreInfra Typesafe; Luna: `gpt-6-luna` через CoreInfra
Decisions. Ни chat completion, ни отдельный LLM-reviewer не использовались.
Model IDs и usage — сведения ответа API, не независимая аттестация backend.

## Preflight и исправление до первого POST

Пользователь разрешил «Прогони через api» после запроса бюджета 18/54; запись
[authorization.json](authorization.json) создана до первого POST. Preflight
обнаружил P1 в PR64: v1 проверял форму отдельного `_evaluate`, но не доказывал
принадлежность методу `BDDPolicy`. Платный запуск v1 **не проводился**.

Исправление `ed975a1` добавило [source-bound v2](../../conditional-native-action-v2.md):
полные pinned-модули, direct class containment, source path/symbol/span и hash/blob
bindings. 26 focused-тестов прошли; исходный вариант и его frozen-пакет сохранены.
Во время запуска CI исправления ещё выполнялся; CI предыдущего head был зелёным.
Шестнадцать baseline/conditioned wires остались прежними. Только два ownership
wires получили проверенную provenance. Критерии H1/H2 и budget не изменились.

Run использовал исключительно
[v2 preparation](../2026-10-15-conditional-native-action-preparation-v2/README.md).
Копия manifest сохранена побайтно. После 18 ответов дополнительных POST не было;
неиспользованный запас повторов не расходовали на semantic retries.

## H1: явно заданные role/support

| Показатель: baseline → conditioned | Jev | Luna Decision |
| --- | --- | --- |
| Согласованные собственные tuples | 2/4 → 3/4 | 2/4 → 3/4 |
| Action violations относительно общих development premises | 2/4 → 1/4 | 1/4 → 0/4 |
| Соблюдение заданных role/support в conditioned | 3/4 | 3/4 |
| Новый YAML formalization / потеря gate formalization | Нет / нет | Нет / нет |
| Строгий preregistered H1 | **Не подтверждён: echo failed** | **Не подтверждён: echo failed** |

В baseline premises не задавались, поэтому echo там **не оценивается**, а не равен
нулевому качеству. При проверке action относительно общих premises мы сохраняем
raw labels и отдельно подставляем одинаковые development premises в formal check;
это диагностический контраст, не исправление ответов и не blind-gold accuracy.

Все восемь пар baseline/conditioned доступны; native failures и пропусков нет.
Наблюдаемое уменьшение action violations полезно, но не заменяет требование
echo 4/4. Для подтверждения H1 не стали удалять неудобный path case.

### Конкретные действия

| Target | Jev: baseline → conditioned | Luna: baseline → conditioned |
| --- | --- | --- |
| Manifest path | formalize → formalize | formalize → formalize |
| Gate precedence | keep_procedural → keep_procedural | formalize → formalize |
| BDD invalid step | keep_procedural → reuse_specification | formalize → formalize |
| YAML newline | keep_procedural → keep_procedural | formalize → keep_procedural |

Восемь baseline label-tuples совпали с предыдущим smoke. Это одно дополнительное
наблюдение стабильности на этих inputs, не доказательство детерминированности.

### Почему path не прошёл

```python
if path.is_absolute() or ".." in path.parts or value != path.as_posix():
    raise IncrementalStageError(...)
```

Selected scope — manifest application без документов. Conditioned state задавал
**`unknown / insufficient`** как experimental premises; задача была выбрать действие
условно на них, а не заново определять primary role.

- Jev вернул `policy / supported / formalize`: своё tuple согласовано, но обе
  заданные premises проигнорированы.
- Luna вернула `policy / insufficient / formalize`: support повторён, role не
  повторена; tuple также нарушает unknown ⇔ insufficient.

Само действие formalize согласуется с предпочтением формализовать неоднозначное
решение. Нельзя считать, что это успех всей интервенции, когда модель изменила
предпосылки. Неопределённость view не устранена документами из другого эксперимента.

### Оставшийся Jev gate

```python
if gate != "none":
    # gate work имеет precedence
    ...
elif node.status in status_order:
    # ordinary refinement
    ...
```

И baseline, и conditioned Jev: `policy / supported / keep_procedural`. Premises
соблюдены, действие противоречит контракту supported mechanics. У Luna оба варианта
`policy / supported / formalize`. Это воспроизводимый ограниченный failure,
не transport или schema problem.

## H2: сделать существующую Specification заметной

Selected `not step.valid` находится в `BDDScenarioValuesSpec.findings`. Проверенный
source path связывает verdict с этим методом:

```python
class BDDScenarioValuesSpec(BDDPolicy):
    # findings включает selected invalid-step predicate
    ...

class BDDPolicy(Specification[BDDContext]):
    def _evaluate(self, candidate, recorder):
        return not self.findings(candidate)
```

Это поясняющее сокращение; полный pinned source и spans — в v2 preparation.
Witness повторяет уже предоставленные факты с доказанной provenance. Готовое
действие `reuse_specification` в metadata witness не задавалось.

| Провайдер | Baseline | Conditioned | Ownership witness | H2 по заявленному критерию |
| --- | --- | --- | --- | --- |
| Jev | keep_procedural | reuse_specification | reuse_specification | Добавочный эффект не показан: reuse уже выбран |
| Luna | formalize | formalize | reuse_specification | **Поддержана в одной паре** |

В обеих BDD-парах conditioned/witness модели соблюли заданные policy/supported,
все четыре native-ответа валидны. У Luna только witness-arm дал reuse; у Jev
conditioning уже дал reuse. Это показывает полезность явного ownership в одном
наблюдении, а не универсальный выигрыш Luna или готовность production classifier.
Numeric action confidence для BDD reuse невысокий: Jev .21/.23, Luna witness .24.
Эти числа не калиброваны; пороги после результата не подбирались.

## Что узнали и следующий шаг

**Установлено:** native shape не обеспечивает ни выполнение заданных premises,
ни согласованность recommendation. Проверка ownership должна связывать symbol
с declaration в исходнике; одинакового AST отдельного snippet недостаточно.
Formal checker сохранил failures видимыми и не превратил их в успешные метки.

**Открыто:** почему модели меняют premises, что именно в witness вызвало сдвиг и
будет ли он повторяться. Conditioning объединяет новые инструкции и metadata;
witness увеличивает контекст и повторяет evidence. Отдельного length-matched
control и независимого holdout нет. Внутренний reasoning моделей не наблюдался.

**Следующий предложенный шаг:** структурно отделить установленные role/support и
AST ownership от тех фактов, которые ещё должна классифицировать модель. Не просить
LLM заново выбирать уже заданные значения; architectural recommendation ограничивать
формальной policy на этих фактах. Raw provider action хранить отдельно. Это будущий
вариант дизайна, не реализованный в данном прогоне; новых API calls не требуется
для подготовки контракта и offline-проверок такого разделения.

## Evidence, usage и replay

Исходные [responses](responses.jsonl), [attempt ledger](attempts.jsonl),
[receipt](receipt.json), [native report](native-report.json) и authorization
сохранены без правок. [analysis.json](analysis.json) отдельно связывает manifest,
восемнадцать локальных lifecycle groups, response attempts и receipt; native
inspector по-прежнему честно пишет `transport_ledger_verified=false`.
Локальное связывание записей не аттестует provider execution или billing.

Provider-reported usage: Jev input **30 636**, output **1 372**; Luna input
**27 378**, output **0**. Стоимость не сообщалась; нулевой reported output Luna
не означает бесплатность API.

Из `evals/jev-classification`, offline, без API key:

```sh
../../.venv/bin/python runs/2026-10-15-conditional-native-action-live-v2/verify_results.py
```

Replay проверяет frozen source/preparation, native report, локальные ledger
associations, preregistered comparisons и полный SHA-256 inventory. Семантическая
accuracy не вычислялась; scoring reference, full v4.1 Annotation и production S/U
не менялись.
