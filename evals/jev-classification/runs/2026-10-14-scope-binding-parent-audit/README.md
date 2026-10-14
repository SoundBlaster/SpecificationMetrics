# Parent audit: scope-binding v3.1

## Уточнение после review PR #60

Открытый [P1 о context identities](https://github.com/SoundBlaster/SpecificationMetrics/pull/60#discussion_r4270834339)
ограничивает описанный ниже audit: он проверяет уникальность **заявленных строк**
agent task в receipts, а retention выводит их из slot. Это ещё не подтверждение
уникальности реально возвращённых инструментом contexts или их isolation.
Сохранённый `parent-verification.txt` с формулировкой «12 unique contexts» следует
читать с этим ограничением. Нужны сверка dispatch evidence и отдельный provenance
repair; frozen run здесь не переписывался. Новая
[таблица adjudication](../../scope-binding-adjudication-v1.md) не использует частоты
ответов как основание для semantic recommendations.

## Результат

Родитель отдельно проверил [завершённый пакет](../2026-10-14-scope-binding-v3-1-results-astra-high/analysis/report.md):
141 checksum, 12 уникальных заявленных annotation task строк, 48 raw rows,
144 уникальных review bindings и точные rationale quotes обеих осей. Повторный
`replay_package.py` прошёл на исходных declared paths. Все retained raw bytes
совпадают с первоначальными `annotations.json`.

Проверки `test_scope_binding_diagnostic.py`, `test_scope_binding_v3_1.py` и
`test_scope_binding_handoff.py`: **29 passed**, repository Python 3.10 virtualenv.
Это отдельное validation evidence; результаты тестов не являются semantic gold.
`verify_parent.py` проверяет байты, identities, уникальное покрытие review и
пересчитывает гистограммы. Он не проверяет истинность semantic judgments.
Команда из `evals/jev-classification`:

```sh
rtk proxy ../../.venv/bin/python -B runs/2026-10-14-scope-binding-parent-audit/verify_parent.py
```

Сохранённый stdout — `parent-verification.txt`. Исходный result package после
передачи ownership не редактировался. Его active freeze revision 2 отличается
от сохранённой revision 1 уточнением: 48 rows вложены в 12 contexts, поэтому
независимость всех 48 наблюдений не заявляется.

## Содержательная оценка

Родитель прочёл обе rationale-оси всех 48 строк и отдельно разобрал шесть
pending notes в `review/semantic-review.json`. Это второй **nonblind model**
проход, а не независимый reference, human gold или оценка accuracy.

- **Scope:** обоснования действительно различают общий definition и выбранное
  применение, включая весь path predicate. Совпадение acknowledgment-полей само
  по себе не было основанием semantic pass. Подтверждённого нарушения scope
  в прочитанных rationale не найдено; остаются ограничения model-based review.
- **Path без документов:** единогласное `excluded / mechanics` для общего helper
  не снимает вопроса. Filesystem/URL use подтверждает техническое применение,
  но не доказывает отсутствия domain integrity role. Три таких shared rows и
  один decisive bound row обоснованно оставлены pending по достаточности witness.
- **Path с документами:** выбранное manifest-применение получило 3/3
  `eligible / policy`. Для общего helper документы поддерживают manifest integrity,
  но перенос primary contract на staging-prefix use спорен. Поэтому ни 1/3
  decisive policy, ни 2/3 abstentions не назначены gold по голосованию.
- **BDD:** все 12 opportunity-ответов правильно ссылаются на показанный
  same-decision Specification evaluation path. Это сильнее совпадения имени
  класса. Ответ `unknown` для direct findings collection оставлен без замены:
  нужно отдельно решить, достаточно ли связи findings → satisfaction для primary
  responsibility именно reporting application при неизвестном `step.valid`.
- **Остальные controls:** gate precedence стабильно `eligible / policy`, newline
  formatting — `excluded / mechanics`. Их rationale указывают на код и роль
  выбранного решения, а не только на название или соседнюю Specification.

Итого proposed review: scope 48 met, ownership 48 met, role witness 42 met и
6 needs_review. В исходном review `criterion_met=false` вместе с
`judgment=needs_review` означает **поддержка критерия не подтверждена**, а не
доказанный неверный label. Это не шесть ошибок классификатора и не accuracy 42/48.
Raw labels, эти review judgments и прежние результаты сохранены.

## Сравнение с v2

`cross-version-input-audit.json` фиксирует 16 сравнений source evidence:
четыре targets × consumer-only / documents+consumers × два scope units.
Target expressions, architecture profile и мультимножество code/text/authority
fragments совпадают. Но rubric, разрешённый scope input, binding facts, output
acknowledgments, fragment IDs и местами kind metadata изменились; в v3.1 документы
идут после consumers, тогда как в v2 они были перед ними. State/task bytes различны.

Следовательно, нельзя приписывать отличие от v2 только scope или называть его
ростом качества. Контролируемые scope contrasts существуют **внутри v3.1**:
01↔03 и 02↔04 держат code, bindings и evidence ordering фиксированными.
Три повтора на target/cell и неполный cross с position не устанавливают
изолированный order effect или причинный механизм модели.

## Следующий шаг

Подготовить короткую decision table для human adjudication двух оставшихся
семантических вопросов: definition-level path contract и роль direct findings
application. До решения сохранить спорные случаи как review-required, не менять
rubric/gold/production S/U и не запускать новую серию ради согласия.

Direct provider API requests = 0; дополнительный parent context не включён в
13 contexts делегированного run. Runtime identity остаётся unverified. Replay
требует исходных declared paths и implementation bytes; перенос checkout сам
по себе не воспроизводит исторический dispatch.
