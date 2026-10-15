# Scope-binding adjudication v1: human confirmation

Пользователь подтвердил D1/D2 ответом «Ок» после отдельного пояснения обеих
рекомендаций. `decision.json` сохраняет контекст подтверждения, версию предложения,
source hashes и точные case/state/task/rubric/scope bindings. Timestamp означает
время записи решения, не независимо установленное время сообщения пользователя.

| Решение | Подтверждённая трактовка | Применимость |
| --- | --- | --- |
| D1 | Shared path definition: `needs_review / unknown` | target-01 cells 01/02: отсутствие и наличие документов соответственно |
| D1 | Documented manifest application: `eligible / policy` | target-01 cell04, только выбранное manifest binding с документами |
| D2 | Invalid-step predicate: `excluded / policy` | target-03 cells 01–04, включая выбранный direct findings binding |

Это семь уникальных target/cell tasks, каждый имел три raw annotations. Решение
назначено на task/evidence, не большинством голосов и не отдельно каждому
аннотатору. Different application bindings не создают дополнительные syntactic
candidates. SpecGraph source revision:
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`.

**Не покрыто:** target-01/cell03 (manifest application без documentary contract).
Для него новая confirmed label не установлена; он остаётся review-required.
Утверждение D1/D2 не означает, что все шесть прежних role-review notes закрыты.

## Authority

- Это human-confirmed adjudication описанных примеров, после model outputs;
  не blind independent annotation и не автоматическое доказательство истины.
- Raw labels, frozen semantic review, diagnoses и частоты ответов не меняются.
- Provider-scoring reference не frozen; решение не загружается в scorer.
- Rubric, classifier, production S/U не изменены. Новых model/provider calls нет.
- Исходное предложение pinned на commit `cb5b485`; текущее представление
  [таблицы](../../scope-binding-adjudication-v1.md) теперь показывает approved.

`SHA256SUMS` связывает два файла этого record. Source bindings в `decision.json`
указывают на неизменённые prep/result/review/repair artifacts; новый record
не переписывает их исторические pending статусы.

Следующий шаг: consistency review rubric и разбор remaining cell03, затем отдельное
решение о provider-scoring reference. Новая inference этим record не разрешается.
