# PR #60: dispatch provenance repair

Исправление [P1](https://github.com/SoundBlaster/SpecificationMetrics/pull/60#discussion_r4270834339)
сохранено отдельно от frozen scope-v3.1 run. Raw answers, исходные receipts,
judgments, histograms и SHA256SUMS старого пакета не изменялись.

## Результат

- 12 фактически возвращённых `spawn_agent` task names сопоставлены с 12 различными
  child-session UUID и parent UUID координатора.
- Сверены 73 выбранные source records из исходных журналов: metadata координатора
  и по шесть записей на каждого child. Полные private sessions не экспортировались.
- Каждая пара call/result связана по call ID. Incoming task адресован этому child;
  его ciphertext payload hash совпадает со spawn request.
- Raw answer каждой сессии целиком совпадает с её template и literal judgments
  в captured writer call; сохранён source-session/file/line binding. Commands
  при replay не выполняются.
- У 11 writers сохранён numeric exit code 0. У annotator-09 сохранены завершение
  tool call и только shell output; numeric shell exit code **не подтверждён**.
- Plaintext prompt equality, runtime model identity, filesystem isolation и
  фактическое model consumption **не подтверждены**. Это не semantic gold.

`dispatch-capture.json` содержит фактические связи; `source-verification.json` —
результат локальной повторной сверки. Источник capture — unsigned operator logs,
не cryptographic runtime attestation. `provenance-repair.json` связывает capture,
новые implementation bytes и исходные frozen manifest/receipt. `SHA256SUMS`
покрывает весь этот repair-каталог, кроме самого manifest.

## Воспроизведение

Из `evals/jev-classification`:

```sh
rtk proxy ../../.venv/bin/python -B scope_dispatch_provenance.py \
  --capture runs/2026-10-14-scope-dispatch-provenance-repair-v1 \
  --source-run runs/2026-10-14-scope-binding-v3-1-results-astra-high --verify-repair
rtk proxy ../../.venv/bin/python -B -m unittest -v test_scope_dispatch_provenance.py
```

Portable replay не требует private session logs и не утверждает, что перечитал
их. Для дополнительной локальной проверки добавить `--source-logs` с исходной
директорией журналов, отдельно от `--verify-repair`. Retention описан в
[новом runbook](../../scope-dispatch-provenance-runbook.md).

## Root cause и урок

Подтверждённая причина P1: старый `retain_attempt.py` конструировал `agent_task`
из номера slot. Последующий uniqueness check проверял эти сконструированные
строки, поэтому не мог выявить reuse реального context или ошибочную ассоциацию
output. Исправление проверяет actual tool result + child metadata + writer/raw
association. Regression включает разные task names с повторным session UUID.

При разработке exporter первый pre-write запуск отклонил несовпадение prompt:
журнал хранит encrypted task payload, а не plaintext prompt. Ничего не было
расшифровано; формат capture теперь сохраняет только digest opaque payload и
явно оставляет plaintext verification false. Первый полный export оставил
incomplete capture без ready marker из-за отсутствия numeric shell exit code у
annotator-09. Сохранённый writer result не исправлялся: новый decoder различает
tool completion и подтверждённый shell exit. После исправления экспорт повторён
в отдельный временный каталог и исходные evidence files сопоставлены.
Это два software-decoder диагностических отказа, не новые annotation attempts
или model failures. Границы свидетельств не заменялись положительными флагами.

Исторические сообщения «unique contexts» и «exact checked prompt supplied» нужно
читать с этой поправкой: первое теперь поддержано session evidence, второе
независимо по plaintext не установлено. Семантические решения D1/D2 по-прежнему
ожидают human adjudication. Direct provider calls = 0; новых аннотаторов нет.
