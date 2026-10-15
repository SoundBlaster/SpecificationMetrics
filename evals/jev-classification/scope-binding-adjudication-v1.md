# Scope binding: два решения для adjudication

Практический вход: [четыре примера с реальным кодом и пояснениями](scope-reference-code-examples.md).
Это объяснение выбранных expressions, а не только таблица меток.

**Статус: D1/D2 подтверждены человеком 2026-10-14 после пояснения обеих рекомендаций.**
Исходный автор предложения — nonblind model-integrator. Подтверждение и точные
case/task bindings сохранены в [отдельном adjudication record](runs/2026-10-14-scope-binding-adjudication-v1/README.md).
Этот документ не меняет raw labels, frozen review, rubric,
scoring reference или production S/U. Новых model/provider requests нет.

## Короткая таблица

| ID | Что именно оцениваем | Что установлено | Что остаётся спорным | Рекомендация |
| --- | --- | --- | --- | --- |
| D1 | Весь path predicate в общем `_safe_path`, с учётом показанных manifest и staging-prefix uses | Он отклоняет absolute paths, `..` и неканоническую POSIX-запись. Документы описывают manifest integrity и fail-closed traversal | Является ли **общее определение** носителем единой domain policy или техническим механизмом реализации контрактов callers | При нынешнем evidence сохранить `needs_review / unknown` для shared definition. Отдельное manifest-применение с документами рекомендовать как `eligible / policy`; не переносить это автоматически на helper |
| D2 | `not step.valid` внутри `BDDScenarioValuesSpec.findings`, при выбранном прямом вызове `policy.findings(context)` | Это выражение выбирает `invalid_value` findings для scenario steps; тот же `findings` определяет satisfaction через `_evaluate` | Меняет ли повторный сбор findings роль **этого предиката** на reporting mechanics | Рекомендовать `excluded / policy`: решение уже принадлежит Specification, а повторное получение его диагностик не меняет его доменную роль |

`excluded` в D2 означает отсутствие **новой возможности внедрения Specification**,
а не отсутствие domain policy. В D1 proposed abstention означает недостаточно
установленный primary contract; это не доказательство, что helper плох или
обязательно требует рефакторинга.

## D1 — общий helper и его manifest-применение

### Факты из сохранённого evidence

Источник: SpecGraph `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`,
`tools/static_artifact_incremental_stage.py:37`, весь BoolOp:

```python
path.is_absolute() or ".." in path.parts or value != path.as_posix()
```

В [packet annotator-04](runs/2026-10-14-scope-binding-v3-1-results-astra-high/delivery/annotator-04/packet.json),
case `target-01`: fragments 01/04 показывают определение и manifest binding
`_safe_path(row.get("path"))`; 06/07 — staging prefix и построение destination;
11 — implemented proposal, 12 — operator documentation.
Proposal требует fail-closed traversal и сохранения relative durable URL paths;
документация называет manifest authoritative artifact index. Proposal не объявлен
canonical Requirement. Static binding не доказывает runtime execution.

### Альтернативы и критерий выбора

| Вариант | Что должно его поддержать | Следствие для shared definition |
| --- | --- | --- |
| Общий contract — только техническая форма relative path; callers задают domain admissibility | Явный контракт helper и разбор показанных uses, отделяющие representation/enforcement от доменного решения | `excluded / mechanics` |
| Общий contract — допустимость publication artifact references и staging destinations | Явный общий intent, связывающий **весь** predicate и оба use с единым publication-integrity rule | `eligible / policy`, если same-decision Specification ownership не установлен |
| Общий primary contract пока не установлен | Нынешние фрагменты допускают обе трактовки; применение и определение различаются | `needs_review / unknown` — текущая рекомендация |

Не требуется доказательство отсутствия всех мыслимых domain meanings или полный
call graph. Нужен достаточный witness для выбранной роли в пределах **показанного**
контекста. Ни filesystem use, ни слово `unsafe`, ни факт, что helper общий, сами
по себе не решают вопрос. Наличие технической реализации не исключает policy.

**Что утвердить:** сохранить abstention для общего определения при этом evidence;
признать, что явный contract конкретного применения может поддерживать policy
без автоматического переноса её на shared definition. Если автор хочет задать
общий domain contract, это отдельное новое утверждение intent с provenance,
которого не было в frozen packet, и оно требует новой версии evidence.

## D2 — доменное решение и сбор его findings

Источник того же pinned SpecGraph: `tools/native_bdd/values_spec.py:27`, exact
predicate `not step.valid`; выбранное применение —
`tools/native_bdd/composition.py:36`, `policy.findings(context)` при выбранном
члене `POLICIES`, `BDDScenarioValuesSpec()`.

В [packet annotator-01](runs/2026-10-14-scope-binding-v3-1-results-astra-high/delivery/annotator-01/packet.json),
case `target-03`, fragments 01–05 показывают цепочку:

```text
not step.valid
  → scenario-step invalid_value finding
  → BDDScenarioValuesSpec.findings(context)
  → BDDPolicy._evaluate = not self.findings(candidate)
```

Caller сначала вызывает `is_satisfied_by`, затем получает findings. Сам вызов,
добавление готовых findings в коллекцию и сериализация отчёта могут быть mechanics.
Но target здесь — предикат, выбирающий нарушения scenario-values rule, а не
`findings.extend(...)` или весь reporting caller.

**Рекомендация:** для этого target/binding связь с admissibility и evaluation
достаточна для `policy`; same-decision ownership отдельно даёт `excluded`.
Подробная реализация `step.valid` нужна для проверки **какие** значения допустимы,
но не обязательно для установления роли показанного invalid-step решения.
Это вывод из содержимого findings и evaluation path, а не из имени класса или
самого факта наследования от Specification.

**Что могло бы изменить вывод:** evidence, что выбранное применение формирует
другой набор findings, переопределяет contract или только адаптирует внешний
вердикт, не выполняя показанный predicate. Такие факты сейчас не показаны.
Runtime identity и чистота `step.valid`/`transition` не сертифицируются.

**Что утвердить:** повторный диагностический вызов не превращает тот же domain
predicate в mechanics; оценка callers и оценка predicate остаются разными targets.

## Последствия и границы утверждения

- Даже после согласия человека этот документ сначала станет adjudication decision,
  а не автоматически frozen provider-scoring reference. Для reference нужны явный
  scope применения, версия, связи с case/task hashes и проверка согласованности
  rubric на остальных случаях.
- Исторические ответы и шесть pending role-witness judgments остаются как есть.
  Решение связывается с ними отдельным артефактом; `unknown` не исправляется в raw.
- Два role bindings одного выражения не создают два syntactic candidates. Этот
  документ не определяет агрегацию applications в S/U и не меняет счётчики.
- В [review PR #60](https://github.com/SoundBlaster/SpecificationMetrics/pull/60#discussion_r4270834339)
  выявлен P1: исторический retention синтезирует task names по slot. Проверенные уникальные
  строки в receipts ещё не доказывают 12 различных фактически возвращённых
  context identities. Отдельный [repair](runs/2026-10-14-scope-dispatch-provenance-repair-v1/README.md)
  связал actual returned identities с 12 различными UUID и writer/raw evidence;
  новый retention не строит identity по slot. Plaintext equality encrypted tasks
  не подтверждена, filesystem isolation не аттестована. Таблица опирается на сохранённый код и rationale;
  частоты ответов не используются для выбора рекомендаций. Исторические заявления
  о formal replay не следует читать как подтверждение isolation.

## Лист решения

| Решение | Предложено | Подтверждение человека | Применение к reference |
| --- | --- | --- | --- |
| D1 | Shared role `needs_review / unknown`; documented manifest application `eligible / policy` | approved 2026-10-14 | pending |
| D2 | Exact invalid-step predicate: `excluded / policy`, включая выбранный findings binding | approved 2026-10-14 | pending |

Подтверждение относится к описанным pinned примерам и их evidence. Для manifest
bound application **без документов** отдельная метка этим подтверждением не
установлена: target-01/cell03 остаётся review-required. Исходные шесть model-review
notes сохранены, не переименованы в закрытые или корректные задним числом.

Следующий шаг: проверить согласованность этих adjudication decisions с rubric и
разобрать оставшееся manifest-применение без documentary contract перед отдельным
решением о freezing provider-scoring reference.

Отдельный [разбор cell03](runs/2026-10-15-manifest-application-without-documents-analysis/README.md)
предлагает D3 `needs_review / unknown`: код подтверждает технические path uses,
но не определяет первичный contract всей проверки в этом применении.
Предложение ещё не подтверждено человеком и не дописывает ранее утверждённый record.

Все 16 tasks и их authority сведены в
[матрицу готовности reference](runs/2026-10-15-scope-reference-readiness-v1/README.md).
Остаётся пакет из трёх пунктов: D3 и два контрольных семейства; запрос на сводку
не превращён в их human approval. Подтверждённые abstentions учтены отдельно от
ещё не подтверждённых решений.
