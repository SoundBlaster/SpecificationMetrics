# Manifest application без документов: разбор cell03

**Предложение D3: `needs_review / unknown` для данного task/evidence.** Это
nonblind model-integrator analysis после знакомства с прежними ответами и D1/D2,
не новый независимый reference и не human-confirmed label. Пользователь разрешил
разбор; подтверждение его результата ещё не получено. Новых аннотаторов и
provider requests нет.

## Какой вопрос решаем

Exact target — **вся** проверка в `_safe_path`, применённая к
`row.get("path")` в `_manifest_files`, а не весь parser или publication workflow:

```python
path.is_absolute() or ".." in path.parts or value != path.as_posix()
```

SpecGraph source `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`,
`tools/static_artifact_incremental_stage.py:37`, callsite — строка 49.
Task `target-01/cell03`, `bound_application`, без documentary fragments.
Task SHA:
`e758b093cf1bab5408483eb7b18a0a333e1d4e9c75c5227310bbf3269ca468b1`.

## Что действительно показывает код

Ссылки на fragment IDs относятся только к этому case в
[packet annotator-03](../2026-10-14-scope-binding-v3-1-results-astra-high/delivery/annotator-03/packet.json).

| Evidence | Установленный факт | Чего он сам по себе не устанавливает |
| --- | --- | --- |
| 01: `_safe_path` | Reject absolute paths, `..` components и неканоническую POSIX-запись; принятый `value` возвращается без изменения | Единый domain contract всей проверки. Это validation canonical spelling, не нормализация возвращаемого значения |
| 04: `_manifest_files` | Проверка вызывается для manifest row path до помещения его в `files` | Почему именно этот accepted path set является product rule, а не техническим precondition адаптера |
| 05: `_load_local_manifest` | Эти paths используются для bundle-relative reads; проверяется наличие файла и digest | Первичную роль **этого** predicate. Digest comparison — отдельное решение |
| 07/09: consumers | Path участвует в staging destination и remote request | Что вся проверка принадлежит только mechanics или обязательно domain policy |
| 06: staging prefix | Есть другое применение helper | Роль выбранного manifest binding: она не переносится автоматически из prefix use |
| 10: workflow | Инструмент вызывается для staging artifact payloads | Достаточный contract о допустимости manifest references; имя job не заменяет его |

Никакой отдельный fragment не показывает same-decision Specification ownership.
Неизвестное ownership само по себе не заставляет abstain. Material ambiguity
здесь — **primary responsibility**, а не ownership или отсутствие runtime trace.
Лексическая проверка также не доказывает физическое filesystem containment.

## Две совместимые трактовки

Это объяснения неопределённости, не новые утверждения intent о SpecGraph:

| Трактовка | Смысл | Возможная классификация при достаточном witness |
| --- | --- | --- |
| Adapter precondition | Вход должен иметь форму relative canonical POSIX path для выбранных file/URL операций | `excluded / mechanics` |
| Artifact-reference contract | Продукт допускает только определённые ссылки на bundle artifacts, а predicate реализует это ограничение | `eligible / policy`, если существующее ownership не установлено |

Оба объяснения совместимы с показанными reject/return и downstream uses.
Это не доказательство формальной неразрешимости и не оценка их вероятностей.
Но один факт «дальше идёт filesystem join» не выбирает между ними. Аналогично,
тот факт, что условие отбирает accepted values, ещё не делает всякую проверку
domain policy: такой accepted set есть и у технического parser.

Не нужно доказывать отсутствие всех мыслимых policies или получать полный call
graph. Требуется достаточная опора для **первичной роли выбранного решения**.
Здесь показанные constraints сочетают reference-safety и representation concerns,
а их общий contract остаётся существенно спорным. Нельзя решить вопрос, выбрав
только traversal clause и забыв `value != path.as_posix()`.

Поэтому рекомендованы обе abstention-метки. Это не общее правило
`concern_kind=unknown ⇒ opportunity=needs_review`: при иной неоднозначности,
например между двумя подходящими domain roles, opportunity может быть ясной.
В этом case конкурирующие роли ведут к разным suitability labels.

## Почему это не требование «без README всегда unknown»

Code-only evidence может быть достаточным. В `target-02/cell03` показаны gate
actions, status-based refinement, mutually exclusive `if/elif` и rank, который
помещает refinements после gates. Эти domain alternatives и их priority видны
в коде без documentary fragments. Это calibration contrast, не дополнительный
semantic input для path-case и не новое утверждение gold для control.

Документация — один из возможных witnesses intent. Им также может быть явный
typed contract, содержательная domain decision в коде или связанное требование.
Наличие Specification не требуется для признания нового кандидата, а имя класса
или `unsafe` не являются самостоятельным доказательством роли.

## Сопоставление с documented application

В рамках v3.1 cell03→04 сохраняет target, architecture profile, scope и binding.
Первые десять fragments идентичны. Добавлены только 11/12:
implemented proposal и operator documentation. Они связывают path constraints
с fail-closed traversal, durable relative paths и authoritative artifact index.
Именно это supporting evidence участвует в ранее подтверждённом D1 для cell04.
Оно **не подставлялось** как отсутствующий fragment в cell03.

Это анализ различий входов. Он не доказывает, почему модель дала конкретный
ответ, причинный эффект документов или правильность unanimous labels.

## Разбор трёх исходных ответов

| Slot | Raw labels | Оценка аргумента |
| --- | --- | --- |
| 03 | `needs_review / unknown` | Указывает конкретную неоднозначность между artifact-reference integrity и generic adapter constraints. Формулировка об «exclusively mechanical contract» сильнее необходимого; для решения важна primary role, а не исключение всех других смыслов |
| 07 | `needs_review / unknown` | Объясняет material gap и сохраняет весь predicate; рекомендация поддержана этим аргументом, не числом голосов |
| 11 | `excluded / mechanics` | Демонстрирует техническое применение, но делает из path-to-filesystem adaptation решающий вывод о primary role. Это правдоподобная гипотеза, пока недостаточно подтверждённая для эталонной decisive label |

Нет вывода «2 из 3 значит истина» или «ответ 11 доказанно ошибочен».
Raw JSON, прежний pending review и human-confirmed D1/D2 не изменены.

## Рекомендация и следующий шаг

Предлагается D3: принять для **этого неизменённого cell03 task**
`needs_review / unknown`. Если человек подтвердит, записать отдельное bounded
adjudication decision и проверить consistency со всем 16-cell пакетом до
отдельного решения о scoring reference. Пока статус — proposed, не confirmed.

Для будущего поиска evidence нужен конкретный вопрос: является ли ограничение
формы manifest reference частью artifact-publication contract или только
техническим precondition адаптера? Найденный либо заново заданный человеком
contract потребует новой версии evidence, а не исправления старого packet.
Новая inference для принятия этого решения не требуется и не запускалась.

`analysis.json` связывает case/task, raw hashes и точные quotes, input comparison
и calibration source. `SHA256SUMS` покрывает два файла этого analysis. Rubric,
scorer, classifier, production S/U и provider-scoring reference не изменены.
