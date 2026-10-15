# Intent-first evaluation contract v4.1

**Текущая версия — v4.1.** [Пакет v4](runs/2026-10-15-intent-first-v4-contract/README.md)
сохранён для historical replay с известным пробелом согласованности. Для новых
tasks используется [v4.1](runs/2026-10-15-intent-first-v4-1-contract/README.md).

## TL;DR

**Роль, уверенность и действие — три разных результата.** Спорный path-check
может получить `unknown / insufficient / formalize`: смысл ещё не доказан,
но архитектурный выбор уже задан человеком. Ранее `needs_review` смешивал
недостаток evidence с отсутствием практической рекомендации.

Основание — [четыре уточнения человека](runs/2026-10-15-scope-binding-adjudication-v2/README.md).
Это новая версия для будущих development evaluations. Старые tasks, ответы,
rubrics и reference не переименованы и не пересчитаны.

## 1. Сначала intent и существующие правила

1. Определить **точное решение**, alternatives и выбранный scope: shared definition
   или отдельное применение. Сохранять целиком выбранное выражение.
2. Изучить предоставленные intent, proposal и spec документы. Сохранить их authority:
   implemented proposal не становится canonical Requirement. Зафиксировать пробелы
   и конфликты. В authoring workflow документы ищут до подготовки packet;
   в frozen diagnostic используются только переданные документы.
3. Проверить, не выражено ли это решение существующей Specification, её простой
   композицией или rule set форматтера/линтера.
4. Выбрать действие. Для нового inline domain decision — формализация. Если после
   доступного intent lookup архитектурное решение остаётся неоднозначным — также
   предпочесть формализацию, сохранив неопределённость роли.

Цель SpecificationCore — единообразное управление, адресация, композиция,
наблюдение и контроль domain rules для человека и AI SDLC. Высокая CC, несколько
использований или немедленное сокращение кода для применения не обязательны.
Поведение продукта должно сохраняться. Рекомендация не даёт права автоматически
редактировать, публиковать или менять intent.

## 2. Три результата

| Поле | Значения | Что означает |
| --- | --- | --- |
| `concern_kind` | `policy`, `variant_behavior`, `mechanics`, `unknown` | Основная ответственность точного выражения |
| `evidence_confidence` | `supported`, `limited`, `insufficient` | Насколько предоставленные evidence обосновывают **concern_kind** |
| `recommendation` | `formalize`, `reuse_specification`, `use_tool_rules`, `keep_procedural` | Как представить решение при выбранном архитектурном подходе |

`policy` определяет допустимость, authority, lifecycle и приоритет обязательств.
`variant_behavior` выбирает, **как** выполнить уже установленную domain activity.
`mechanics` отвечает за представление, parsing, transport и adaptation без
самостоятельного domain decision. Enum, `not`, имя `unsafe`, отказ или расположение
файла сами по себе роль не устанавливают.

`supported` требует прямого code/contract witness; `limited` сохраняет неполное
или конфликтующее evidence; `insufficient` используется с `unknown`, когда
primary role установить нельзя. Это ordinal self-report, а не вероятность
правильности, confidence CoreInfra или откалиброванный между моделями score.

`basis` объясняет рекомендацию: `domain_contract`, `formalization_preference`,
`existing_specification`, `simple_composition`, `tool_responsibility`, `mechanics`.
Для каждой оси нужен rationale; для роли и действия — точные source quotes.
`intent_review` перечисляет прочитанные документальные fragments и missing context.
Отсутствие документа не мешает установить правило, если его смысл достаточен из кода.

В v4.1 `keep_procedural` допустим **только** при `mechanics / supported`.
`policy / supported → keep_procedural` противоречит заявленной роли;
`unknown / insufficient → keep_procedural` необоснованно объявляет проверку механикой.
Также отклоняется `mechanics / limited → keep_procedural`: уверенности пока
недостаточно для такого основания.

`formalization_preference` имеет узкий смысл: ограниченное или недостаточное
evidence для **роли** после bounded intent lookup. Когда доменное правило уже
подтверждено, основанием служит `domain_contract`. Сомнения в декомпозиции или
именовании реализации можно записать в uncertainties, сохранив `policy / supported`.

## 3. Переиспользование и композиция

- Существующая Specification должна владеть **тем же** решением через evaluation.
  Одного имени, импорта или Specification где-то рядом недостаточно.
- Производные и простые NOT/AND/OR-композиции распознанных Specifications сохраняют
  эту природу. Новый wrapper только ради оператора не требуется.
- В BDD-примере `step.valid` — Boolean fact; принадлежность проверке установлена
  цепочкой findings → evaluation. Любой `not flag` автоматически спекой не становится.
- Предел сложности композиции пока не определён. Контракт не вводит численного
  порога и не начисляет новые opportunities только за Boolean operators.
- Форматирование относится к formatter/linter rule sets. `use_tool_rules` выражает
  ответственность: оно **не утверждает**, что конкретный rule уже настроен или
  исполняется в проекте.

## 4. Четыре примера из SpecGraph

Pinned source: `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.
Код, supporting fragments и scope сохранены; profile и все task identities новые.

| Выражение / выбранный scope | Роль | Support | Действие | Основание |
| --- | --- | --- | --- | --- |
| `_safe_path`: весь BoolOp, manifest binding без документов | `unknown` | `insufficient` | `formalize` | Утверждённое предпочтение строгой формализации при сохраняющемся сомнении |
| `gate != "none"`, shared definition | `policy` | `supported` | `formalize` | Gate work имеет приоритет над status-based refinement |
| `not step.valid`, selected findings binding | `policy` | `supported` | `reuse_specification` | Решение уже в `BDDScenarioValuesSpec` evaluation path |
| `not rendered.endswith("\n")`, shared definition | `mechanics` | `supported` | `use_tool_rules` | Управление правилами форматирования |

[Текущий пакет](runs/2026-10-15-intent-first-v4-1-contract/README.md) содержит
**integrator examples после человеческого уточнения**, а не ответы новой модели
или независимый gold. Эти примеры известны разработчикам контракта и подходят для
regression/development диагностики. Они не измеряют качество или generalization.
`variant_behavior` в этих четырёх примерах не представлен.

Для documented manifest view proposal 0215 даёт witness fail-closed traversal;
он не добавлен задним числом в no-document пример. Отдельный regression test
проверяет обязательное признание переданных documentary fragment IDs.

## 5. Исполняемые проверки и границы

[Python contract](intent_first_contract_v4_1.py) экспортирует JSON Schema типов и
валидирует межполевые ограничения, точные task/state/scope/contract identities,
документальные IDs и совпадение quotes с источником. Hash контракта включает
profile, schema, инструкции и prompt; изменение любого из них меняет task hash.
JSON Schema описывает структуру, Python validator дополнительно проверяет связи
полей и evidence. Даже PASS означает только
`contract_valid_not_semantically_adjudicated`: смысл quotes и верность labels
требуют semantic review. Приём `simple_composition` не доказывает, что конкретный
source действительно использует Specification composition API.

Schema описывает **полный response** `{"annotations": [...]}`. Template имеет
ту же оболочку; `validate_response` проверяет её, точный набор case IDs и каждую
строку. Отдельная annotation без оболочки, лишние metadata, пустой список,
пропущенные или повторённые cases отклоняются. Integrator examples содержат
внешний `status` provenance; consumer получает их `annotations` в строгой оболочке.

[Producer](prepare_intent_first_v4_1.py) пишет только новый каталог с `--write`,
в обычном режиме воспроизводит bytes и проверяет полный file set. Receipt связывает
producer, Pydantic version и все входы; SHA-256 inventory покрывает артефакты.
Template остаётся пустым. Integrator examples и source mappings не входят в
разрешённые annotator inputs. Delivery/изоляция/dispatch этим пакетом не реализованы.

Используется Pydantic `2.13.5`, уже закреплённый в repository CI:

```bash
rtk proxy uv pip install --python .venv/bin/python pydantic==2.13.5
```

Из корня репозитория:

```bash
rtk proxy .venv/bin/python -m unittest discover -s evals/jev-classification -p 'test_intent_first_v4*.py' -v
rtk proxy .venv/bin/python evals/jev-classification/prepare_intent_first_v4_1.py
```

## 6. Совместимость и следующий этап

v3.1 и v4 используют разные задачи и выходные поля. v4.1 сохраняет четыре state,
scope, code, profile и example labels/actions из v4, но меняет contract/task IDs
из-за исправленных acceptance rules и response schema. Старые IDs не принимаются.
v4 producer, validator и артефакты сохранены побайтово; tests воспроизводят их
историческое принятие противоречивых ответов и отклонение тех же комбинаций в v4.1.

Прямое сравнение accuracy
потребует отдельно зафиксированного reference mapping; `formalize` не переводится
автоматически в production `eligible`, S или U. Старый native Jev/Luna wire adapter
ожидает две Choice questions; v4.1 к нему пока не подключён. Нельзя отправить этот
пакет через прежний runner и считать это v4.1 experiment.

Следующий этап — bounded handoff и reference mapping для v4: независимая
семантическая проверка новых примеров, отдельный учёт role support и architecture
action, затем согласованный provider wire mapping для текущей v4.1. Текущая подготовка не запускает
модели, не меняет classifiers и не включает scorer.
