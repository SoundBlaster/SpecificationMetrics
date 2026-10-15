# Conditional recommendation diagnostic v1

## Задача и границы

[Smoke #63](https://github.com/SoundBlaster/SpecificationMetrics/pull/63) получил
8/8 native-valid ответов, но 4/8 противоречивых tuples. Оба провайдера пропустили
переиспользование существующей BDD Specification. Это ещё не доказывает причину.
Следующий опыт проверяет две управляемые гипотезы:

- **H1 — conditional action:** изменится ли выбор действия, если concern kind и
  evidence support явно даны как фиксированные предпосылки?
- **H2 — ownership salience:** изменится ли BDD-рекомендация, если уже показанная
  цепочка принадлежности Specification явно сведена в проверяемый witness?

Это диагностика исполнения заданной policy на четырёх известных development
targets SpecGraph, **не** качество самостоятельного определения intent и не
unseen accuracy. Согласие с искусственно заданной ролью нельзя выдавать за
правильное распознавание роли. Роли взяты из v4.1 integrator examples, выработанных
после обсуждения человеком. Path остаётся предпосылкой `unknown / insufficient`
для выбранного no-document view; дополнительные документы не подставляются.

## Дизайн: 18 запросов, до 54 сетевых попыток

| Arm | Targets × providers | Изменение |
| --- | ---: | --- |
| `baseline` | 4 × 2 = 8 | Побайтно прежние wires, новый execution и request IDs |
| `conditioned` | 4 × 2 = 8 | Те же source/scope + фиксированные role/support и инструкция условного выбора |
| `ownership_witness` | 1 × 2 = 2 | Только BDD: тот же conditioned wire + явный source-derived ownership witness |

Все arms содержат те же **три Choice-оси**, те же options/criteria и тот же
architecture profile. Во втором arm меняется bundle «инструкция conditioning +
явные предпосылки», поэтому результат не позволит разделить эффекты этих двух
частей. Третий arm добавляет только witness; вопросы совпадают с conditioned.
Остальные три targets не дублируются бессодержательным ownership arm.

Для каждой пары target/provider порядок arms циклически сдвигается фиксированным
образом; он зафиксирован в manifest. Это не полноценная рандомизация и не защита
от всех временных эффектов. Каждый wire — отдельный native request без передаваемой
истории предыдущих ответов. Независимость backend, отсутствие caching и
детерминированность ответов не предполагаются. Старые восемь ответов сохраняются
как история; основной контраст использует **свежий** baseline в новом batch.

Premises видимы модели только в conditioned arms:

| Target | Concern kind | Evidence support |
| --- | --- | --- |
| Manifest path, bound application, no documents | unknown | insufficient |
| Gate precedence, shared definition | policy | supported |
| BDD invalid step, bound findings | policy | supported |
| YAML newline, shared definition | mechanics | supported |

Ни желаемые recommendations, ни integrator rationales, ни прошлые provider labels
в wire не передаются. Это не blind-разметка: явно переданные premises являются
самим экспериментальным воздействием.

### Witness: факт о коде, не готовая рекомендация

Для BDD source содержит:

```python
class BDDScenarioValuesSpec(BDDPolicy):
    # selected `not step.valid` находится в findings
    ...

class BDDPolicy(Specification[BDDContext]):
    def _evaluate(self, candidate, recorder):
        return not self.findings(candidate)
```

Witness связывает selected predicate, объявленный тип, наследование, verdict path,
membership в `POLICIES` и выбранный `policy.findings(context)`. Его точные quotes
и SHA-256 относятся к уже поставляемым source fragments. Summary не содержит
команду `reuse_specification` и не вводит новых source facts.

Run-specific AST checks подтверждают показанную структуру, отсутствие override
`_evaluate` в дочернем классе и receiver binding. Это **не** общий resolver Python
imports, не runtime proof и не доказательство сторонних зависимостей. Witness
не заявляет больше, чем frozen source view. Его отсутствие в других arms не
означает отсутствия Specification: исходная BDD-цепочка остаётся во всех arms.
Witness также увеличивает длину контекста; отдельного length-matched control в этом
минимальном опыте нет. Поэтому эффект нельзя приписать только форме summary,
отделив её от повторного предъявления evidence и увеличения контекста.

## Измерения до запуска

Все ответы сохраняются исходными. Формальный слой не подменяет рекомендацию и
не запускает повторный запрос ради исправления семантического результата.

1. **Transport/native shape:** HTTP, завершённость, attempts, model/question/option
   identities, probability mass. Ошибки native format отделяются от semantic labels;
   они не становятся автоматически «неправильным architectural action».
2. **Returned-tuple consistency:** прежние `native.tuple_violations` применяются к
   трём реально возвращённым меткам во всех arms. Старый contract не меняется.
3. **Premise compliance:** только в conditioned/witness — вернула ли модель обе
   заданные premises. Echo является compliance, не accuracy.
4. **Action against the same premises:** для baseline и conditioned отдельно
   применить тот же formal contract к возвращённому действию и фиксированным
   development premises. Это общий условный критерий сравнения, а не исправленные
   provider labels. Raw tuple и результат этой проверки остаются разными полями.
5. **BDD reuse:** для каждого из трёх arms показать выбранное действие и
   `reuse_selected / existing_specification_not_reused`. Критерий следует из
   принятого architecture profile и проверенного evaluation path, не из имени
   класса. Это узкий диагностический критерий, не общая semantic accuracy.
6. **Controls:** отдельно показать gate formalization, YAML new-formalization и
   path action. Для YAML keep_procedural и use_tool_rules различаются по точности
   рекомендации, но оба сохраняют human intent «не создавать новую Specification».

Missing rows, неполный transport batch и невалидные native ответы показываются
отдельно; нулевой observed failure при отсутствующих ответах не означает успех.
Inspector не аттестует ledger или billing и не выводит отсутствие POST из
отсутствия response row. Для live-публикации потребуется отдельная проверка ledger.

### Как интерпретировать H1/H2

- **H1 supported в этом batch для конкретного provider:** все четыре пары имеют
  native-valid ответы, conditioned echo = 4/4 и число action violations against
  the same premises строго меньше baseline; нет нового YAML formalization и
  потери gate formalization, если она была выбрана в baseline.
  Нарушенный echo — невыполненная интервенция, а не успех reasoning.
- **H1 не подтверждена:** violations не уменьшились или появились control
  regressions. Рост нарушений — результат против полезности этого варианта на
  данных случаях. При native/transport потерях вывод по полному набору отложен.
- **H2 supported в показанной BDD-паре:** conditioned не выбрал reuse, а witness
  выбрал; обе premises соблюдены и оба ответа native-valid. Если оба выбрали reuse,
  добавочная польза witness не показана; если ни один — гипотеза не поддержана в
  этой паре. Обратный переход — регрессия. На одного provider приходится всего
  одна пара: ни статистической значимости, ни обобщения на кодовую базу здесь нет.

Если результаты смешанные, не объявлять победителя и не складывать разные criteria
в выдуманный quality score. Не подбирать prompt по четырём знакомым примерам и
не менять acceptance задним числом. Следующий шаг выбирается после сохранённого
разбора; для обобщения потребуется отдельный held-out набор.

## Команды и authorization boundary

Из `evals/jev-classification`, repository venv:

```sh
../../.venv/bin/python -m unittest -v test_conditional_native_action.py
../../.venv/bin/python conditional_native_action_v1.py
../../.venv/bin/python conditional_native_action_v1.py \
  --stage /tmp/specmetrics-conditional-action-NEW
```

Эти команды не читают credentials и не обращаются в сеть. `--stage` создаёт новый
каталог эксклюзивно, проверяет frozen bytes и transport preflight. Повторное
использование существующего destination запрещено.

В `evals/jev-classification/AGENTS.md` требуется отдельное explicit approval для
платного frozen run. Подготовка пакета и прежний бюджет 8/24 не являются разрешением
на **новые 18 запросов / до 54 попыток**, включая повторы TLS по текущей transport
policy. Semantic retries не входят в план. После такого разрешения: создать
новый run, записать authorization до POST и вызвать существующий transport:

```sh
../../.venv/bin/python coreinfra_retry_run.py \
  --run /tmp/specmetrics-conditional-action-NEW --live
../../.venv/bin/python conditional_native_action_v1.py \
  --inspect /tmp/specmetrics-conditional-action-NEW
```

Transport останавливает batch при HTTP/transport/JSON-ошибке; TLS-повторы ограничены
тремя попытками на запрос. Остаток бюджета не разрешает новые logical requests.
Native/semantic failures сохраняются для разбора и не «лечатся» дополнительными POST.
Ни scoring reference, ни production S/U, ни полная v4.1 Annotation не меняются.
