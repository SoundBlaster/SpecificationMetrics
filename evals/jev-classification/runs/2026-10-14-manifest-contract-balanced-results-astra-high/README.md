# Balanced v2: независимая разметка Astra High

Получены 48 аннотаций: 12 свежих contexts без наследования, по четыре различных target. Выполнены три волны 01–04, 05–08, 09–12. Запрошены `gpt-6-astra` и `high`; runtime model identity не подтверждена доступным tool response и записана отдельно как unknown. Canonical task IDs сохранены в attempt receipts. Запросов к Jev/Luna или другим внешним provider API не было; выполнены именно 12 agent inference contexts.

Все 12 initial attempts прошли существующий provenance/quote validator после ответа и при итоговом replay. Replacements, excluded attempts и formal failures: 0. 48 rows сохранены без исправления labels/quotes. `semantic-review.json` содержит предложенный nonblind model-integrator review: H_contract 6/6, H_consumers 6/6, H_target_fidelity 48/48. H_traceability подтверждён per-attempt validator в пределах scoped assignment + fresh context + self-report. Formal pass не доказывает semantic correctness.

## Наблюдаемые результаты

Cell01: без документов/consumers; cell02: документы; cell03: consumers; cell04: оба. Decisive coverage имеет знаменатель **3 для каждой оси каждой target-cell**. `needs_review` и `unknown` сохраняются как abstentions, не exclusions.

| Target | Cell | Opportunity histogram | Concern histogram | Decisive opportunity | Decisive concern |
|---|---|---|---|---|---|
| target-01: manifest path BoolOp | 01 | needs_review 3 | unknown 3 | 0/3 | 0/3 |
| target-01 | 02 | eligible 3 | policy 3 | 3/3 | 3/3 |
| target-01 | 03 | excluded 2, needs_review 1 | mechanics 2, unknown 1 | 2/3 | 2/3 |
| target-01 | 04 | eligible 3 | policy 3 | 3/3 | 3/3 |
| target-02: gate != "none" | 01 | eligible 3 | policy 3 | 3/3 | 3/3 |
| target-02 | 02 | eligible 3 | policy 3 | 3/3 | 3/3 |
| target-02 | 03 | eligible 3 | policy 3 | 3/3 | 3/3 |
| target-02 | 04 | eligible 3 | policy 3 | 3/3 | 3/3 |
| target-03: not step.valid | 01 | excluded 3 | policy 3 | 3/3 | 3/3 |
| target-03 | 02 | excluded 3 | policy 3 | 3/3 | 3/3 |
| target-03 | 03 | excluded 3 | policy 3 | 3/3 | 3/3 |
| target-03 | 04 | excluded 3 | policy 3 | 3/3 | 3/3 |
| target-04: missing YAML newline | 01 | excluded 3 | mechanics 3 | 3/3 | 3/3 |
| target-04 | 02 | excluded 3 | mechanics 3 | 3/3 | 3/3 |
| target-04 | 03 | excluded 3 | mechanics 3 | 3/3 | 3/3 |
| target-04 | 04 | excluded 3 | mechanics 3 | 3/3 | 3/3 |

Все 4 abstention rows относятся к target-01: annotator-01/05/09 в cell01 и annotator-03 в cell03. Единственное разногласие на обеих осях — cell03: annotator-03 needs_review/unknown, annotator-07/11 excluded/mechanics. Полный перечень вместе с SHA — `analysis/histograms.json`; каждая row, repetition и position — `analysis/observed-rows.json`.

## Сравнения внутри target

Для target-01 добавление документов при consumers=false (01→02) сопровождается переходом 3 abstentions к 3 eligible/policy. При consumers=true (03→04) 2 excluded/mechanics + 1 abstention сменяются 3 eligible/policy. В написанных rationale документ трактуется как evidence supplied fail-closed traversal contract при ограниченной authority.

Добавление consumers при documents=false (01→03) повышает decisive coverage с 0/3 до 2/3, но эти два решения — excluded/mechanics. При documents=true (02→04) labels и coverage не меняются. Consumers сами по себе не дают единого толкования primary responsibility всего BoolOp. Это описание данного balanced run, не оценка causal effect.

В target-02 документы и consumers не меняют gate-priority interpretation; target-03 остаётся excluded по явному same-decision Specification ownership и policy по concern; target-04 остаётся serialization mechanics. Для каждого control сравнения 01→02, 03→04, 01→03 и 02→04 имеют одинаковые labels и coverage. Добавленная evidence различается по targets, поэтому общий pooled treatment effect не вычислялся.

## Semantic review и пределы вывода

Интегратор прочитал rationale/uncertainties всех 48 rows и supplied evidence. В `semantic-review.json` заполнены 60 applicable entries, каждый связан с exact raw SHA, case/task/state identity и цитатой rationale. Критерии выполнены по предложенному judgment: documentary traversal requirement не отрицается, supplied consumers не отрицаются, границы target и operational capabilities не подменяются. Эти критерии не требуют конкретных labels и не заменяют adjudication.

Разногласие cell03 требует review порога, при котором generic consumers становятся affirmative evidence для excluded. Предложенная позиция интегратора — сохранить неопределённость до adjudication; 2:1 не является доказательством. Для document-present cells eligible/policy имеет содержательное основание, однако роль canonical-spelling clause не становится каноническим требованием от согласия трёх ответов. Подробности и lesson: `analysis/diagnosis.md`.

Изоляция — scoped assignment, fresh contexts и self-report, без filesystem sandbox. Проверки bytes до/после не доказывают, что модель прочитала именно эти bytes, и не обнаруживают изменение с последующим восстановлением. Один общий model family, четыре отобранных выражения, deterministic order, разная длина evidence и возможный control priming ограничивают обобщение. 48 judgments не означают 48 source targets. Runtime identity не подтверждена. Production S/U, gold и reference authority не изменены.

## Артефакты и replay

- `delivery/`: сохранённые packet/template/prompt bytes, первоначальные blank receipts и output files. Historical `delivery-receipt.json` описывает момент materialization и намеренно остаётся prepared-not-dispatched; актуальный итог — `execution-receipt.json`.
- `raw-attempts/`: exact output bytes всех 12 attempts, включая abstentions.
- `attempt-receipts/`: фактические task IDs, context declaration, model request отдельно от unknown runtime identity, input/prompt/raw SHA.
- `semantic-review.json`: proposed integrator review, не blind adjudication и не human gold.
- `validation/`: actual-file preflight, post-answer validation и final replay logs существующего validator.
- `execution-receipt.json`: связывает producer/preparation/input/prompt/raw/review/analysis identities и retained/excluded attempts.
- `SHA256SUMS`: byte-integrity inventory результата; проверяет содержимое, не semantic correctness.

Replay описан в `REPLAY.md`. Имеющийся validator поддерживает preparation/per-attempt validation; автоматического batch-results semantic grader нет. Поэтому пакет заявляет завершённый сбор и предложенный review с подтверждёнными per-attempt checks, но не автоматически сертифицированный semantic batch gate.

Следующий шаг: human adjudication target-01/cell03 и роли canonical-spelling clause полного BoolOp, без изменения этого frozen outcome.
