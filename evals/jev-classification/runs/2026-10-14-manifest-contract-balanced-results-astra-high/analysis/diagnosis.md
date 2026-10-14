# Диагноз разногласия и lesson

## Наблюдение

Формальных failures нет: 12 первоначальных attempts валидны, replacements и exclusions — 0. Semantic criteria, проверенные интегратором, не обнаружили нарушений H_contract (6/6), H_consumers (6/6) или H_target_fidelity (48/48). Это предложенная оценка интегратора, а не независимая adjudication и не human gold.

Единственное межповторное разногласие: target-01/cell03 (documents=false, consumers=true), на обеих осях. annotator-03 дал needs_review/unknown; annotator-07 и annotator-11 дали excluded/mechanics. Точные raw bytes и SHA доступны в ../raw-attempts/ и ../attempt-receipts/; полные rationale и uncertainties сохранены без правок. Машинный перечень — histograms.json.

## Подтверждённая граница причинного объяснения

Все три ответа признают operational path uses. annotator-03 считает, что они не разрешают primary contract полного BoolOp; annotator-07/11 считают общий staging-prefix use и I/O consumers утвердительным свидетельством generic adapter mechanics. Это подтверждённое различие в написанных обоснованиях. Внутреннее reasoning модели и причинный механизм изменения labels не наблюдались.

Гипотеза: при отсутствии documentary contract разные свежие контексты по-разному применяют порог «affirmative mechanics evidence» к одним и тем же consumers. Не подтверждено, обусловлено ли это собственно семантикой evidence, длиной контекста, priming от controls или общей вариативностью модели. Замена annotator-03 либо большинства для получения согласия была бы нарушением протокола; замен не было.

## Предложенная интерпретация и профилактика

Интегратор оставляет cell03 unresolved для дальнейшей adjudication: generic I/O role действительно показана, но её достаточность для исключения domain reference policy остаётся предметом спора. Большинство 2:1 не устанавливает correctness. В cells02/04 supplied contract делает eligible/policy защищаемой интерпретацией; обязательность canonical-spelling clause как части primary domain contract требует отдельного review и не доказывается консенсусом.

Следующий bounded diagnostic: получить human review точного полного BoolOp, особенно общей роли canonical spelling и shared staging prefix, с явным критерием достаточности consumer-only evidence. Новое evidence, rubric или prompt оформлять новой версией, сохранив этот run. Не исправлять production-метрики, labels или frozen preparation по результатам одного small-n наблюдения.

Проверка профилактики в этом запуске: исходные bytes не изменялись; все 12 per-attempt replays прошли; 4 abstentions остались в знаменателях, replacements/exclusions отсутствуют; semantic-review привязан SHA в execution-receipt.json.
