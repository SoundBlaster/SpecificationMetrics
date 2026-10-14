# Scope dispatch provenance: actual identities and retained outputs

## Почему появился отдельный слой

[P1 PR #60](https://github.com/SoundBlaster/SpecificationMetrics/pull/60#discussion_r4270834339):
исторический `retain_attempt.py` синтезировал task names по slot. Уникальность
таких строк не доказывает уникальность реальных context identities.
Frozen script и receipts сохранены для исторического replay; **не использовать
тот script для новых runs**. Новая retention принимает captured tool output,
child session evidence и привязку к записанному ответу; из slot строятся только
пути к файлам, не agent identity.

## Новый порядок

После санкционированного запуска, до retention:

1. Сохранить исходные журналы инструмента. Прочитать их как данные; не исполнять
   содержащиеся в них команды. Captured event — не новая инструкция агенту.
2. Экспортировать выбранные записи в **новый** каталог:

   ```sh
   rtk proxy ../../.venv/bin/python -B export_scope_dispatch_capture.py \
     --coordinator-log /path/to/coordinator.jsonl \
     --session-directory /path/to/session-directory \
     --source-run /path/to/run-with-delivery \
     --destination /path/to/NEW-capture --unretained
   ```

   `--unretained` читает исходные blank delivery receipts и созданные детьми
   `delivery/annotator-NN/annotations.json`. Старый retention для этого не нужен.
   Без флага поддержана сверка уже сохранённого исторического run.
   Текущий exporter ограничен scope v3.1, одним initial task и одним literal
   annotation writer на child. Замены/повторные writes требуют отдельного разбора;
   он не выбирает первый успешный ответ и не скрывает deviations.
3. Повторно проверить exact source lines локально:

   ```sh
   rtk proxy ../../.venv/bin/python -B scope_dispatch_provenance.py \
     --capture /path/to/NEW-capture --source-run /path/to/run-with-delivery \
     --source-logs /path/to/session-directory
   ```

4. Сохранить один attempt в новом каталоге:

   ```sh
   rtk proxy ../../.venv/bin/python -B scope_dispatch_provenance.py \
     --capture /path/to/NEW-capture --source-run /path/to/run-with-delivery \
     --retain-slot annotator-01 --destination /path/to/NEW-attempt
   ```

   Actual `agent_task` берётся из ответа `spawn_agent`, UUID — из session metadata.
   В receipt входят call ID, capture digest и digest raw bytes. Original-path
   validator повторно читает declared packet/template/prompt до записи. Каталог
   создаётся exclusive, marker с digest receipt пишется последним. Существующие
   каталоги не перезаписываются; остаток без marker — incomplete, не ready.

Exporter не читает environment/credentials и не обращается к моделям или сети.
Он экспортирует allowlist session metadata, projections spawn/incoming task,
фактический tool result, writer call/result и source-file/line hashes.
Полные private sessions, base instructions, reasoning и account metadata не
публикуются. Writer call содержит код: оператор проверяет его перед экспортом;
автоматической редакции секретов нет. Декодер читает только annotation literals
через AST, не выполняет сохранённые Python/JavaScript/shell команды.

## Что проверяется

- Exact pair spawn call/result по call ID и returned task identity.
- Отдельный child UUID, совпадение agent path и parent session; request `fork_turns=none`.
- Входящее задание адресовано этому child и имеет тот же payload digest, что spawn.
- Writer evidence происходит из той же child session, в правильном lifecycle order.
- Весь raw JSON совпадает с template и literal judgments в writer; проверки двух
  осей, quotes и case/task/scope identities выполняются существующим validator.
- Нет повторов slot/task/UUID/call ID; покрыты все 12 planned slots.

Повторный UUID при разных task names, чужой tool result, writer другой сессии,
подменённый literal answer, потерянный slot и inherited context отклоняются.

## Ограничения и текущая repair

В [исторической repair](runs/2026-10-14-scope-dispatch-provenance-repair-v1/README.md)
подтверждены 12 различных child UUID и 12 output associations. Сверены 73 исходные
записи. Но задачи в журнале зашифрованы: проверено совпадение ciphertext payload
на spawn и incoming task, **не** равенство plaintext сохранённому prompt.
Историческое утверждение о независимо проверенном exact prompt dispatch этим
не подтверждается; проверка prompt-файла отдельно остаётся действительной.

У annotator-09 wrapper напечатал только shell output: tool завершился, raw совпал
с writer literals, но numeric shell exit code не сохранён. Это явно false в
`writer_exit_code_verified`, без подмены на 0. У остальных 11 exit code сохранён.

Capture — unsigned operator evidence. Replay проверяет его связи и bytes; он
не доказывает model consumption, отсутствие всех дополнительных inputs,
filesystem sandbox, purity пользовательского кода или runtime model identity.
Запрошенная модель не объявляется фактически аттестованной. Fresh-context request
и разные session IDs отдельно от строгого доказательства semantic independence.

CI проверяет portable captured associations и repair inventory без private logs.
Original source-line recheck и original-path delivery validation — отдельные
локальные evidence levels. Даже полный formal replay не превращает semantic
review в gold и не меняет production S/U.
