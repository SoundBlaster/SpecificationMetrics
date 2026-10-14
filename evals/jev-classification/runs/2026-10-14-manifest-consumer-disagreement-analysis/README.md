# Разбор consumer-only разногласия

Статус: post-run integrator analysis / proposal, не human adjudication и не gold.
Исходные 48 ответов, review и hashes не изменены. Новых inference-запусков нет.

## Что именно разошлось

Один и тот же case-task `target-01/cell03` получил `needs_review / unknown`
от annotator-03 и `excluded / mechanics` от annotator-07/11. У них одинаковы
state, task, rubric и факты focal case. Полные packets не идентичны: порядок
четырёх cases меняется. Focal target занимает позиции 1, 2 и 3 соответственно.

Выбран весь BoolOp, не функция и не одно из трёх условий:

```python
path.is_absolute() or ".." in path.parts or value != path.as_posix()
```

| Вопрос | annotator-03 | annotator-07/11 |
| --- | --- | --- |
| Что делает код? | Запрещает absolute, parent traversal, noncanonical spelling | То же |
| Где используются результаты? | Bundle/staging paths и remote URL | То же; подчёркнут shared staging prefix |
| Что дают эти uses? | Доказывают operational role, не основной контракт | Достаточны для generic adapter responsibility |
| Что остаётся неизвестным? | Domain admissibility или mechanics для всего BoolOp | Возможный отдельный domain contract; его отсутствие в packet не препятствует exclusion |

Спор находится в переходе от наблюдаемого dataflow к primary responsibility.
Цитаты и полные rationale трёх ответов привязаны к source hashes в
[evidence ledger](evidence-ledger.json). Там наблюдаемые факты отделены от
интерпретационных переходов I1/I2.

## Что доказано, а что нет

**Доказано кодом:** helper возвращает принятую строку; его вызывают и для
manifest entry, и для staging prefix. Manifest path затем участвует в чтении,
копировании и формировании fetch URL. Проверки лексические; из них не следует
полная файловая изоляция, symlink safety или URL safety.

**Не следует только из этого dataflow:** что helper выражает исключительно
mechanics или исключительно domain policy во всех применениях. Shared
implementation может обслуживать разные семантические решения. Повторное
использование технического predicate не доказывает единственность его intent.

**Документы добавляют:** manifest является authoritative index, relative durable
paths сохраняются, traversal должен fail closed. Это реализованный proposal и
operator documentation, не canonical Requirement. Контракт является содержательным
основанием рассмотреть manifest application как policy. Он не доказывает сам по
себе отдельное нормативное основание каждого ограничения canonical spelling или
что staging-prefix application принадлежит тому же доменному правилу.

В документ-содержащих cells все шесть ответов дали eligible/policy. Это наблюдение
о разметке, а не доказательство её истинности или причинного эффекта документов.

## Более глубокая неоднозначность: единица решения

Формальная граница target задана хорошо: точное выражение внутри `_safe_path`.
Семантическая граница задана слабее: инструкции требуют primary role выражения,
но не выбирают, оценивается ли shared definition во всех uses или application
этого predicate для конкретного subject.

| Единица | Вопрос |
| --- | --- |
| Shared definition | Каков контракт общего helper, пригодного и для manifest path, и для staging prefix? |
| Manifest application | Как правило проверяет допустимость `files[].path` при построении manifest index? |
| Staging application | Как правило ограничивает prefix при сборке staging destination? |

Это не три новых синтаксических кандидата. Определение остаётся одним; применения
могут иметь несколько role bindings. Будущая метрика не должна превращать
дополнительные role bindings в дополнительные места U или дополнительные Specs.
Предложение не утверждает, что такой binding уже реализован в scanner.

## Предлагаемое решение для текущего пакета

Сохранить `needs_review / unknown` как **консервативную позицию интегратора** до
adjudication. Это не замена трёх raw labels и не доказательство ошибки большинства.
Основание — показанная двойная роль helper и неразрешённый scope primary role,
а не абстрактная возможность придумать неизвестное требование.

`excluded / mechanics` имеет положительное основание: generic relative-path
usage и representation checks. Поэтому оно не объявляется ошибкой автоматически.
Но переход к «без distinct domain decision» остаётся интерпретацией; generic
I/O usage также совместим с реализацией доменного ограничения.

Отсутствие документов не должно автоматически давать ни exclusion, ни abstention.
Код или typed contract иногда уже однозначно устанавливает роль. Здесь вопрос
конкретен: общий helper обслуживает разные subjects, и разные admissibility
contracts остаются совместимы с показанным кодом.

Оси остаются независимыми. Возможен `excluded / policy`, когда то же решение уже
оценивает Specification: BDD control показал эту комбинацию 12/12 раз. Не нужно
сводить пригодность извлечения к одному concern label.

## Проверка достаточности evidence — предложение для review

1. Зафиксировать точный target, semantic subject и единицу definition/application.
2. Отделить факты исполнения/dataflow от утверждений о назначении правила.
3. Указать witness назначения: различаемые доменные исходы, typed contract,
   документированное требование или достаточно явная decision role в коде.
   Документ не является обязательным видом witness.
4. Проверить, что witness относится к выбранной единице и всему решению.
   Representation clause может поддерживать общую policy; не требуется
   отдельное доменное правило на каждую строку или clause.
5. Отдельно проверить evidence same-decision Specification ownership.
6. При альтернативной роли назвать конкретный показанный факт, который делает
   её материальной. Не требовать доказательства отсутствия всех воображаемых
   policy и не включать автоматическое воздержание для любого I/O helper.

Это review checklist, не новый scoring contract и не формальный semantic oracle.
Изменение prompts/rubric/acceptance требует отдельной версии и frozen подготовки.

## Root cause и следующий diagnostic

Подтверждена причина различия **написанных обоснований**: разные переходы от uses
к evidence sufficiency. Внутренняя причина различия ответов модели неизвестна.
Конкурируют scope interpretation, порог affirmative mechanics evidence,
положение/порядок cases и обычная вариативность одной model family. Три повторения
не идентифицируют причинный механизм; нельзя приписать его только слабому prompt.

Следующий шаг — [отдельный scope-binding diagnostic](next-diagnostic-plan.md),
сохраняющий этот run неизменным. До нового опыта не менять production classifier,
reviewed S/U, frozen labels или scoring reference.
