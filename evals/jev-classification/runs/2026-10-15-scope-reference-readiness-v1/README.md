# Scope v3.1: готовность reference по всем 16 tasks

**Сводка готова; provider-scoring reference ещё не frozen.**
Это inventory существующих решений и source-backed предложений, не новая
разметка, human approval или запуск scorer. Дата UTC: 2026-10-15.

| Что считаем | Количество | Значение |
| --- | ---: | --- |
| Уникальные target/cell tasks | 16 | Для каждого сохранены точные state/task/rubric/scope hashes |
| Raw annotations | 48 | По 3 ответа на task, из 12 contexts; 4 rows одного context не независимы |
| Human-confirmed D1/D2 tasks | 7 | 5 decisive pairs и 2 подтверждённых abstention pairs |
| Предложение D3 | 1 | Label ещё не подтверждён человеком |
| Unconfirmed controls | 8 | Два семейства × четыре evidence/scope views; подтверждение в этом пакете не записано |
| Tasks с включённым provider scoring | 0 | Ни одна строка этой сводки не включает scorer и не объявляет reference frozen |

Два confirmed abstentions — **не пропущенные записи**: решение для них
`needs_review / unknown`. Не следует превращать его в `excluded` или молча
удалять из оценки coverage. Scoring treatment задаётся явно при freezing reference.

## Полная таблица

`E` = eligible, `X` = excluded, `R` = needs_review;
`P` = policy, `M` = mechanics, `?` = unknown.
Raw histograms двух осей считаются отдельно, со знаменателем 3 на каждой оси.
Правая пара — confirmed decision или явно обозначенное предложение; это не
перезаписанный raw outcome. Для **всех** строк provider scoring пока выключен.

| Target/cell | Scope | Документы | Raw opportunity (n=3) | Raw role (n=3) | Решение / предложение | Authority |
| --- | --- | --- | --- | --- | --- | --- |
| target-01/01 · Manifest path | общее определение | нет | X:3 | M:3 | `needs_review / unknown` | D1 · подтверждено |
| target-01/02 · Manifest path | общее определение | есть | E:1, R:2 | P:1, ?:2 | `needs_review / unknown` | D1 · подтверждено |
| target-01/03 · Manifest path | применение | нет | X:1, R:2 | M:1, ?:2 | `needs_review / unknown` | D3 · предложено |
| target-01/04 · Manifest path | применение | есть | E:3 | P:3 | `eligible / policy` | D1 · подтверждено |
| target-02/01 · Gate precedence | общее определение | нет | E:3 | P:3 | `eligible / policy` | Control · не подтверждено |
| target-02/02 · Gate precedence | общее определение | есть | E:3 | P:3 | `eligible / policy` | Control · не подтверждено |
| target-02/03 · Gate precedence | применение | нет | E:3 | P:3 | `eligible / policy` | Control · не подтверждено |
| target-02/04 · Gate precedence | применение | есть | E:3 | P:3 | `eligible / policy` | Control · не подтверждено |
| target-03/01 · BDD invalid-step | общее определение | нет | X:3 | P:3 | `excluded / policy` | D2 · подтверждено |
| target-03/02 · BDD invalid-step | общее определение | есть | X:3 | P:3 | `excluded / policy` | D2 · подтверждено |
| target-03/03 · BDD invalid-step | применение | нет | X:3 | P:2, ?:1 | `excluded / policy` | D2 · подтверждено |
| target-03/04 · BDD invalid-step | применение | есть | X:3 | P:3 | `excluded / policy` | D2 · подтверждено |
| target-04/01 · YAML newline | общее определение | нет | X:3 | M:3 | `excluded / mechanics` | Control · не подтверждено |
| target-04/02 · YAML newline | общее определение | есть | X:3 | M:3 | `excluded / mechanics` | Control · не подтверждено |
| target-04/03 · YAML newline | применение | нет | X:3 | M:3 | `excluded / mechanics` | Control · не подтверждено |
| target-04/04 · YAML newline | применение | есть | X:3 | M:3 | `excluded / mechanics` | Control · не подтверждено |

## Почему решения имеют именно такой статус

- **D1/D2 — 7:** authority — [human confirmation record](../2026-10-14-scope-binding-adjudication-v1/README.md),
  а не совпадение ответов моделей. Path shared/no-doc получил raw `X:3 / M:3`,
  но подтверждённая человеком трактовка — `R / ?`. Единогласие не стало gold.
- **D3 — 1:** [отдельный анализ](../2026-10-15-manifest-application-without-documents-analysis/README.md)
  предлагает `R / ?` для manifest application без документов. Запрос «своди»
  разрешает подготовить эту матрицу и не принят за подтверждение D3.
- **Controls — 8:** предложены gate precedence `E / P` и newline `X / M`.
  Основания — содержательная роль `if/elif` и gate-first rank в первом случае,
  только добавление newline к сериализованному тексту во втором. Точные code
  quotes сохранены в `matrix.json`. Стабильность raw ответов — наблюдение,
  не источник human authority и не доказательство correctness.

## Проверка согласованности

1. Все 16 уникальных tasks покрыты; 48 raw rows привязаны к frozen assignments.
   Разные tasks не смешаны по одному только case_id; scope и документы учитываются.
2. Approved labels не конфликтуют для одного task. Shared-definition uncertainty
   и documented-application policy относятся к разным единицам оценки.
3. `excluded` не приравнено к mechanics: уже представленное BDD-правило остаётся
   policy. Для него opportunity и concern_kind — разные вопросы.
4. Отсутствие документов не означает автоматический abstention: domain priority
   gate control виден из кода. Наличие документов само по себе не даёт policy:
   newline control остаётся proposed mechanics по показанному formatting effect.
5. Предложения, approvals и raw votes хранятся раздельно. Ни большинство, ни
   формальный pass не повысили статус control или D3 до подтверждённого решения.

Это nonblind integrator consistency review. Оно не заменяет независимый blind
reference и не доказывает semantic truth. Матрица проверяет согласованность
выбранной трактовки и документирует authority.

## Что осталось решить — одним пакетом из трёх пунктов

| Пункт | Применимость | Предлагаемая пара |
| --- | --- | --- |
| Подтвердить D3 | target-01/cell03, manifest application без документов | `needs_review / unknown` |
| Подтвердить gate controls | target-02/cells01–04, exact `gate != "none"` | `eligible / policy` |
| Подтвердить newline controls | target-04/cells01–04, exact newline predicate | `excluded / mechanics` |

Это девять tasks в трёх смысловых группах, не девять отдельных интервью.
Если человек подтвердит пакет, сохранить versioned adjudication поверх D1/D2,
не переписывая raw и предыдущие records. Затем отдельно явно зафиксировать
reference mapping и scoring scope: обе оси, abstentions и coverage отдельно.
Не нужны новые модельные ответы лишь для заполнения этих authority-полей.

## Ограничения: учитывать, не превращать автоматически в новые блокировки

| Evidence / limit | Текущее состояние | Практическое следствие |
| --- | --- | --- |
| Task bytes и static bindings | 16 адресуемых tasks, original source pinned | Можно проверить, к чему именно относится каждое решение |
| Dispatch association | [Repair](../2026-10-14-scope-dispatch-provenance-repair-v1/README.md) связал 12 returned identities, UUID и outputs | Уникальность slot-derived строк больше не используется как доказательство |
| Prompt plaintext | Не подтверждён: журнал содержит encrypted tasks | Не заявлять независимое доказательство exact plaintext dispatch или причинный prompt effect |
| Runtime model / sandbox | Не аттестованы | Запрошенную Astra/high не выдавать за runtime attestation; не заявлять enforced filesystem isolation |
| Writer 09 shell exit | Numeric code не сохранён; tool completion и writer/raw match есть | Не дорисовывать exit code 0. Остальные 11 numeric codes сохранены |
| Повторения и порядок | 3 повтора task; rows вложены в contexts; target/cell×position не fully crossed | Не считать 48 независимых tasks и не выводить причинный order effect |
| Охват | 4 семейства; variant_behavior не представлен | Не выдавать этот корпус за весь SpecGraph или оценку отсутствующего класса |
| Известность примеров | Уже использовались в разработке rubric и обсуждении результатов | Первый разумный use — development diagnostic/regression corpus, не unseen holdout |

Эти ограничения остаются в provenance. Они ограничивают интерпретацию исходного
model experiment, но **сами по себе не аннулируют human-adjudicated source tasks**
и не требуют повторной Astra/Jev/Luna разметки. Чтобы применять reference к
конкретному исследовательскому выводу, его evidence limits должны соответствовать
этому выводу. Здесь новый experiment или paid inference не разрешается.

## Файлы и проверка

`matrix.json` содержит все 16 строк, обе raw histograms, source/raw hashes,
case/task bindings, decision authority, exact control witnesses и ограничения.
`SHA256SUMS` покрывает этот README и JSON. Сводка не является input-файлом scorer.
Исторические packets/raw/review/repair/adjudication не изменены. Rubric, classifier,
production S/U и provider-scoring reference не менялись; новых model contexts и
direct provider requests — 0.

**Следующий шаг:** подтвердить либо скорректировать три пункта выше; затем можно
зафиксировать полный mapping без нового annotation run.
