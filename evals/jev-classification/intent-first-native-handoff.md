# Intent-first v4.1: подготовка native Jev/Luna smoke

## TL;DR

Подготовлены **8 logical requests, максимум 24 network attempts**: четыре
разобранных примера SpecGraph × два провайдера, без повторного semantic experiment.
Native wire и decoder проверяются локально с fake HTTP. Реальных запросов пока нет.

Это **проекция трёх полей v4.1**, а не полный Annotation. Native Choice возвращает
категории, probabilities и provider confidence; rationale, basis и source quotes
полного контракта не генерируются этим подключением. Приём проекции не означает
PASS полного v4.1, human adjudication или разрешение менять код/метрики.

## Сопоставление

| v4.1 / transport | Native вопрос / данные | Правило |
| --- | --- | --- |
| `concern_kind` | Choice: policy / variant_behavior / mechanics / unknown | Основная ответственность точного выражения |
| `evidence_confidence` | Choice: supported / limited / insufficient | Ordinal evidence support для роли |
| `recommendation` | Choice: formalize / reuse_specification / use_tool_rules / keep_procedural | Архитектурное действие |
| Native `confidence` | `answers[axis].provider_confidence` | Число провайдера, не категория evidence support и не калиброванный score |
| basis / rationale / quotes / intent-review report | Отсутствуют | Не подставлять author rationale или вымышленные evidence |

Проверяется совместимость tuple: `unknown ↔ insufficient`, procedural только для
`mechanics / supported`, подтверждённая mechanics не оправдывает formalize.
Противоречивые метки сохраняются как получены с `tuple_violations`; их нельзя
переписать в ожидаемые ответы. Такая проверка не доказывает смысловую верность роли.

## Native wire и источник

Используются явные model IDs и endpoints из ранее сохранённого native протокола:

- Jev: `jev-1.13.0`, `https://hub.coreinfra.ai/typesafe/api/v1/systemone`.
  Запрос: `model`, canonical UTF-8 `state`, три named Choice questions с `criteria`.
  Ответ: object `answers`, probability maps.
- Luna: `gpt-6-luna`, `https://hub.coreinfra.ai/openai/api/v1/decisions`.
  Запрос: `model`, тот же canonical UTF-8 `input`, три named Choice questions с
  `choices[{value,description}]`. Ответ: named array, probability arrays.

Новая доступность моделей и поддержка трёх вопросов **ещё не проверены live**.
Models/endpoints не заменяются aliases при ошибке. Порядок провайдеров чередуется
между cases; один case имеет одну и ту же state и criteria у обоих провайдеров.

Wire передаёт только source state и semantic questions: глобальная цель,
intent lookup, scope, правило формализации при неопределённости, reuse/tool rules.
Он не содержит integrator labels, reference, integrator case/task IDs, старый annotation
prompt или rich JSON Schema с несовместимыми указаниями вернуть rationale/JSON.
Documents остаются в тех evidence views, где они были предоставлены.

Source state bytes v4.1 используют своё encoding; native state сериализуется
canonical JSON. В manifest раздельно сохранены `source_state_sha256` и
`wire_state_sha256`. `source_task_sha256` сохраняет привязку к v4.1; новый
`native_task_sha256` связывает projection policy, source task, state и questions.
Это новые native tasks, не переиспользование старых tasks с другими вопросами.

Подготовка: [frozen пакет](runs/2026-10-15-intent-first-native-preparation-v1/README.md).
[Producer](prepare_intent_first_native.py) воспроизводит source v4.1, весь file set,
native wires, implementation/input hashes и SHA-256 inventory.

## Offline commands

Из корня репозитория:

```bash
rtk proxy .venv/bin/python -m unittest discover -s evals/jev-classification -p test_intent_first_native.py -v
rtk proxy .venv/bin/python evals/jev-classification/prepare_intent_first_native.py
```

Создание **нового** execution directory, без сети и чтения ключа:

```bash
rtk proxy .venv/bin/python evals/jev-classification/prepare_intent_first_native.py --stage /tmp/specmetrics-intent-native-smoke-01
rtk proxy .venv/bin/python evals/jev-classification/coreinfra_retry_run.py --run /tmp/specmetrics-intent-native-smoke-01
```

Existing directory не перезаписывается. Frozen preparation directory не служит
местом для responses/ledger. `--stage` кладёт точный manifest в отдельный каталог
и вызывает только offline preflight существующего транспорта.

## Будущий ограниченный live-прогон

Само сохранение пакета **не разрешает inference**. После отдельного явного решения
на этот бюджет существующий runner принимает `--live`:

```bash
rtk proxy .venv/bin/python evals/jev-classification/coreinfra_retry_run.py --run /tmp/specmetrics-intent-native-smoke-01 --live
```

Runner читает `COREINFRA_API_KEY` только в live mode; credential не записывается
в manifest/ledger. Verified TLS остаётся включённым. Повторяются те же bytes до
трёх total attempts на logical request по существующему retry protocol. Ошибки
сертификата не считаются временными; ambiguous POST и возможное повторное
исполнение учитываются транспортом. При transport/HTTP/decode failure batch
останавливается. Semantic/native decoding выполняется после transport batch:
wrong-model/invalid-tuple не вызывает новых запросов или semantic retries,
но **не останавливает уже выполняющийся транспортный batch досрочно**.
Он всё равно ограничен восемью logical requests / 24 total attempts.

После batch:

```bash
rtk proxy .venv/bin/python evals/jev-classification/prepare_intent_first_native.py --inspect /tmp/specmetrics-intent-native-smoke-01
```

Decoder проверяет exact model/question/option identities, finite numeric bounds,
winner, probability mass и tuple. Jev 1.13 допускает отклонение суммы до 1% для
этих 3/4-option questions с явным warning и исходными числами. Luna остаётся
strict с tolerance 1e-6. Provider confidence не пересчитывается.

Inspector проверяет записанную request/wire/model association и сохраняет hash
того же снимка bytes, который был разобран, даже при параллельной дописи файла.
`native_status` описывает форму ответа, а `projection_status` явно различает
согласованную и противоречивую проекцию. Это не независимая аттестация выполнения. Он **не воспроизводит
transport ledger** и не объявляет billing/operational completeness. Отсутствие row
означает «response row отсутствует», а не «POST точно не было». Transport receipt
и attempt ledger остаются отдельным evidence. Full Annotation, semantic correctness
и provider scoring отмечены false даже при восьми согласованных tuples.

## Критерии и дальнейшая оценка

1. **Transport:** receipt/ledger отдельно показывают attempts, POST ambiguity,
   HTTP failures и завершение. Не подменять их наличием JSON файла.
2. **Native compatibility:** получить восемь ответов с ожидаемыми model/question/
   option identities; mass warnings учитывать отдельно. Ошибки не исключать из
   знаменателя восьми запланированных запросов.
3. **Tuple consistency:** показать исходные метки и violations по всем наблюдаемым
   ответам, включая native-valid, но противоречивые tuples. Не исправлять их.
4. **Semantic evaluation:** четыре знакомых integrator examples не дают accuracy
   или generalization. Для этого отдельно выбрать новые SpecGraph cases, получить
   независимый reference под v4.1 и зафиксировать protocol до новых запросов.

Первый smoke подтвердит или опровергнет работоспособность native mapping. Он не
докажет качество трёх осей, пользу паттерна или улучшение S/U. Rust evaluation
driver и старые two-question experiments сохранены; эта подготовка использует
существующий Python transport без замены их contracts.
