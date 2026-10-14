# Scope v3.1: actual-file handoff и retained-attempt replay

## Текущее состояние

Поддержан исправленный контракт v3.1 из [подготовки](scope-binding-diagnostic-plan.md).
Доступны materialization, preflight и проверка сохранённого ответа. Этот слой
не запускал аннотаторов и не обращался к provider API. Модели, разметка и semantic
review — последующий запуск. Historical v3.0 и v2 handoff не используются для
новых пакетов.

Поле `dispatch_ready: false` в frozen preparation фиксирует состояние **слоя
подготовки** до появления handoff. Оно не переписывается. Текущие команды
сообщают `scope_handoff_available_not_dispatched` или preview, а новая delivery
сохраняет и исходное stage-поле, и `scope_handoff_available: true`. Наличие
готовой выдачи не является запуском, одобрением protocol или semantic pass.

## Проверить и материализовать

Из `evals/jev-classification`, в repository virtualenv:

```sh
rtk proxy ../../.venv/bin/python prepare_scope_binding_v3_1.py
rtk proxy ../../.venv/bin/python validate_scope_binding_annotations.py
rtk proxy ../../.venv/bin/python prepare_scope_binding_handoff.py
rtk proxy ../../.venv/bin/python -m unittest -v test_scope_binding_handoff.py
```

Preview не создаёт файлов. Чтобы выдать входы, указать **новый** каталог в
retained run storage, который сохранится до replay:

```sh
rtk proxy ../../.venv/bin/python prepare_scope_binding_handoff.py \
  --destination /absolute/path/to/NEW-delivery
```

Команда отказывает при существующем каталоге; промежуточные остатки не являются
ready. Каждый `annotator-NN/` получает только `packet.json` и `template.json`.
Prompts, receipts и blank manual review находятся снаружи. Создание файлов не
читает credentials, не вызывает модели и не меняет Git.

Receipt содержит:

- protocol `scope-binding-v3.1` и SHA frozen preparation receipt;
- SHA handoff, scope validator и переиспользованного frozen structural validator;
- slot, case/cell/position, unit, state/task/rubric/binding hashes;
- реальные absolute paths и прочитанные с диска hashes packet/template/prompt;
- пустые agent/context/model/output поля и сохранённую metric/reference authority.

Форматированный prompt должен читаться из `prompts/annotator-NN.txt` именно этой
выдачи. Нельзя заменить его путь чистой копией после изменения оригинала; это
проверяется так же, как declared packet/template paths.

## Перед каждым разрешённым запуском

```sh
rtk proxy ../../.venv/bin/python validate_scope_binding_annotations.py \
  --check-delivery --assignment /absolute/path/to/NEW-delivery/receipts/annotator-01.json
```

Preflight читает реальные файлы, сравнивает bytes с frozen v3.1 и hashes с
прочитанными bytes. Проверяет protocol/preparation/implementation/case bindings.
Он может пройти с незаполненными agent/output полями: это проверка выдачи,
не завершение аннотации. Старые v3.0/v2 packages и stale receipts отклоняются.

Для будущей разметки: 12 fresh contexts, по четыре cases, одна view на dependency
family, три волны по четыре slots в заданном порядке. Передать каждому ребёнку
точный проверенный prompt, без mapping, hypotheses, author labels, других
ответов или inherited history. Предыдущий опыт и его labels не являются gold.

## После ответа

1. Сохранить exact raw bytes, в том числе malformed/failed output и deviations.
2. Заполнить **копию** исходного receipt реальным agent task, context inheritance,
   requested model/effort и raw output SHA. Неподтверждённый runtime model оставить
   null; этот validator не сертифицирует runtime identity. Не исправлять raw JSON.
3. Повторить проверку реальных файлов через attempt replay:

   ```sh
   rtk proxy ../../.venv/bin/python validate_scope_binding_annotations.py \
     --assignment /path/to/filled-attempt-receipt.json \
     --annotation /path/to/retained-raw.json
   ```

4. Учесть каждый retained/excluded/failed attempt отдельно. Замена — новый
   контекст и отдельный receipt, с сохранением исходного неуспеха. Materializer
   сам не заменяет и не adjudicate ответы.

Проверяются exact case/state/task/rubric identity, **явные scope_unit и
scope_binding_sha256**, labels обеих осей, непустые rationale, точные цитаты из
своего case и объяснённое abstention. Returned scope должен совпадать с выбранным
unit и full binding digest. Отсутствие одного case или дубликат — hard failure.

Authority receipt остаётся informational: provider requests = 0, human gold =
false, metric effect = none и reference-for-provider-scoring = false. Здесь
provider requests означает прямые внешние Jev/Luna/API calls; agent inference
в будущем должен отражаться отдельным количеством contexts. Этот инструмент
не предоставляет разрешения на прямой платный provider run.

## Что формальный pass не доказывает

`scope_acknowledgments_verified: true` означает совпадение полей, а не понимание
scope моделью. `scope_semantic_fidelity_verified: false` и pending manual review
остаются даже для structurally valid ответа. Хорошо оформленная, но неверная
rationale не превращается в semantic pass.

Переиспользован чистый structural/quote validator v2; его source bytes включены
в receipt и не изменены. Scope checks и versioned delivery реализованы отдельно,
поэтому исторический replay сохраняет исходный validator identity.

Изоляция остаётся scoped assignment + fresh context + self-report. Нет filesystem
sandbox или доказательства model consumption. Pre/post byte checks не обнаружат
изменение с последующим восстановлением между проверками. Replay требует
оригинальных declared delivery paths и зафиксированных implementation bytes;
другой checkout не может утверждать original-path dispatch verification только
по наличию похожих copies.

## Manual review и итоговый пакет

`semantic-review.template.json` содержит три независимые группы по 48 entries:
`scope_fidelity`, `role_witness`, `ownership`. Все judgments, reviewer, raw hashes
и quotes обеих rationale-осей изначально null. Отдельно формальный traceability
раздел ожидает 12 проверенных attempts. Факт создания 144 blank entries не
является результатом review.

После разметки отдельно проверить:

- rationale говорит о назначенном definition/application и целом выражении;
- вывод о роли подкреплён показанным evidence, не одним metadata или отсутствием
  документов; не перенесён автоматически из другого use;
- same-decision Specification ownership отделён от concern_kind и suitability.

Сохранить точные supporting rationale quotes, их оси и raw hashes. Для итогового
пакета связать manual review и все contributing raw bytes в execution receipt.
Автоматического batch semantic grader этот слой не добавляет. Нельзя объявить
все критерии выполненными только по per-attempt formal passes.

Отчёт: обе оси, все 16 target-cell histograms, denominator 3 per axis/cell,
abstentions и disagreements без pooling разных families. Target-cell×position
не fully crossed; согласие не является correctness или доказательством causal
order/scope effect. U/S, production classifier и scoring reference не меняются.
