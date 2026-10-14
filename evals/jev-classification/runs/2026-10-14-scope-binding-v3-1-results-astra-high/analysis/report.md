# Scope-binding v3.1 — bounded Astra/high run

Получены **48 raw annotations из 12 fresh contexts; по 4 разных families в каждом**.
+Четыре rows одного context не считаются статистически независимыми наблюдениями.
Все 12 первых attempts прошли actual-file formal replay. Failed/excluded attempts и
replacements: **0**. Прямых внешних Jev/Luna/provider API requests: **0**; отдельно
учтены 12 annotation contexts и один nonblind model-integrator context. Запрашивались
`gpt-6-astra` / `high`, `fork_turns=none`; runtime model identity инструментом не
подтверждена и в receipts оставлена `null`.

## Наблюдения по каждой family

В каждой ячейке ровно **3** ответа. `E` = eligible, `X` = excluded, `R` = needs_review;
`P` = policy, `M` = mechanics, `U` = unknown. Variant_behavior нигде не выбран.
Decisive coverage исключает R или U, но сохраняет знаменатель 3 отдельно по оси.

| Target | Cell | Unit / documents | Opportunity histogram | Coverage | Concern histogram | Coverage |
|---|---|---|---|---|---|---|
| target-01 | 01 | shared / absent | X:3 | 3/3 | M:3 | 3/3 |
| target-01 | 02 | shared / present | E:1, R:2 | 1/3 | P:1, U:2 | 1/3 |
| target-01 | 03 | bound / absent | X:1, R:2 | 1/3 | M:1, U:2 | 1/3 |
| target-01 | 04 | bound / present | E:3 | 3/3 | P:3 | 3/3 |
| target-02 | 01 | shared / absent | E:3 | 3/3 | P:3 | 3/3 |
| target-02 | 02 | shared / present | E:3 | 3/3 | P:3 | 3/3 |
| target-02 | 03 | bound / absent | E:3 | 3/3 | P:3 | 3/3 |
| target-02 | 04 | bound / present | E:3 | 3/3 | P:3 | 3/3 |
| target-03 | 01 | shared / absent | X:3 | 3/3 | P:3 | 3/3 |
| target-03 | 02 | shared / present | X:3 | 3/3 | P:3 | 3/3 |
| target-03 | 03 | bound / absent | X:3 | 3/3 | P:2, U:1 | 2/3 |
| target-03 | 04 | bound / present | X:3 | 3/3 | P:3 | 3/3 |
| target-04 | 01 | shared / absent | X:3 | 3/3 | M:3 | 3/3 |
| target-04 | 02 | shared / present | X:3 | 3/3 | M:3 | 3/3 |
| target-04 | 03 | bound / absent | X:3 | 3/3 | M:3 | 3/3 |
| target-04 | 04 | bound / present | X:3 | 3/3 | M:3 | 3/3 |

`target-01` — полный path predicate. Для shared definition без документов все три
ответа выбрали mechanics/excluded. При наличии документов два shared ответа сохраняют
неопределённость: contract manifest integrity не определяет однозначно primary
responsibility общего helper, используемого также для staging prefix. Bound application
с документами дала три eligible/policy; без документов два ответа abstain и один
выбирает mechanics/excluded. Это наблюдаемая чувствительность объяснений к unit и
документам в данном пакете; correctness и причинный эффект этим не установлены.

`target-02` — gate precedence. Во всех четырёх ячейках три eligible/policy:
обоснования опираются на if/elif, ranks и gate obligations; последующий action dispatch
не переносится на exact predicate. `target-04` — newline formatting: во всех ячейках
три excluded/mechanics, с прямым witness в serializer и добавлении newline.

`target-03` — invalid-step findings. Opportunity во всех ячейках excluded на основании
конкретного Specification evaluation path. В bound/no-doc cell один concern unknown:
annotator-01 различает direct findings collection и verdict evaluation, ссылаясь на
непоказанные `step.valid` и `transition`. Два других ответа этой ячейки считают уже
показанную связь findings → satisfaction достаточным witness policy. Спор касается
роли выбранного применения, а не обнаружения owner.

## Все disagreements и abstentions

Disagreement есть в **5 axis×cell**: target-01/cell02 по обеим осям,
target-01/cell03 по обеим осям и target-03/cell03 по concern_kind.

- target-01/cell02: annotator-02 = eligible/policy; annotator-06 и annotator-10 = needs_review/unknown.
- target-01/cell03: annotator-03 и annotator-07 = needs_review/unknown; annotator-11 = excluded/mechanics.
- target-03/cell03: annotator-01 = excluded/unknown; annotator-05 и annotator-09 = excluded/policy.

Это все abstentions: 4 по opportunity, 5 по concern_kind, в 5 отдельных rows.
Оси считаются независимо. Полные identities, позиции, raw SHA, rationale и uncertainty
для каждого случая сохранены в `histograms.json`; все 48 строк с исходными labels —
в `rows-with-identities.json`. Разные families не объединялись в общий treatment effect.

## Proposed semantic review

`../review/semantic-review.json` заполнен как **NONBLIND MODEL-INTEGRATOR judgment**,
не blind adjudication и не human gold. Для каждого из 144 judgments сохранены actual
raw SHA, task/state/rubric/scope-binding identities, обе точные contiguous rationale
quotes и содержательная note. Полные rationale paragraphs используются как quotes,
поэтому это 288 цитат без перефразирования.

| Criterion | Proposed met | Needs review |
|---|---:|---:|
| scope_fidelity | 48 | 0 |
| role_witness | 42 | 6 |
| ownership | 48 | 0 |

Все шесть `criterion_met=false` имеют judgment `needs_review`, а не утверждение о
доказанной ошибочности label. Пять относятся к достаточности role witness path
predicate: annotator-01/05/09 с target-01 cell01, annotator-02 с target-01 cell02 и
annotator-11 с target-01 cell03. Generic adapter use не обязательно исключает domain
integrity, а применение integrity-contract к shared prefix требует отдельного bridge.
Шестой — annotator-01/target-03: необходимо содержательно разрешить связь reporting
application с already-owned validity role. Большинство и formal pass не служили
правилом semantic judgment; disagreement само по себе не является failure.

Formal traceability сохранён отдельно: 12 actual-file replays, точные quotes из своего
case, обе оси, case set и scope acknowledgments проверены. Semantic review не меняет
их статус `semantic_correctness_verified=false`; автоматического batch semantic gate
нет. Все raw outcomes сохранены без исправлений.

## Границы доказательства и следующий шаг

Pre/post проверки повторно читали исходные declared packet/template/prompt paths;
retained raw bytes равны созданным annotations.json. Изоляция — scoped assignment,
fresh context и self-report, без filesystem sandbox и доказательства фактического
model consumption. Изменение с восстановлением между byte checks не обнаруживается.
Для original-path replay нужны эти исходные absolute paths и зафиксированные
implementation bytes. Копия в другом checkout сама по себе не подтверждает dispatch.

Target-cell×position не fully crossed. Нельзя оценивать изолированный order effect,
причинный scope effect или model mechanism; common-model bias и priming остаются.
Согласие не равно истине. Human gold = false, reference-for-provider-scoring = false,
metric effect = none; production classifier и U/S не менялись. Исторические raw labels,
diagnoses и author labels не использовались как reference.

Следующий шаг — независимый аудит родителей/integrator по шести review notes и
формальным связям пакета, затем focused PR. Новый annotation/provider run для
разрешения disagreements этим отчётом не разрешается.
