# Что именно классифицируем: четыре примера SpecGraph

Сначала код и вопрос к нему; затем метка и причина. Ниже реальные функции или
сокращённые **непрерывные** фрагменты из SpecGraph revision
`51c8d93cc385569864b3cd7f5040d4b3e0820a1b`. Пропущенные части функций не заменены
новой логикой. Это пояснение существующей разметки, не patch приложения.

| Пример | Какой вопрос задаёт выбранное выражение | Рекомендация / статус |
| --- | --- | --- |
| Manifest path | Допустима ли такая ссылка на artifact — или это только требуемая форма пути для адаптера? | Без документов D3 `needs_review / unknown`, предложено. Для documented manifest binding D1 `eligible / policy`, подтверждено |
| Gate precedence | Нужно ли выбрать gate work перед обычным refinement? | `eligible / policy`, контрольное предложение |
| YAML newline | Нужно ли дописать terminator сериализованного текста? | `excluded / mechanics`, контрольное предложение |
| BDD invalid step | Какие шаги нарушают уже существующее scenario-values rule? | `excluded / policy`, D2 подтверждено |

`eligible` — предложение представить решение как Specification, а не команда
обязательно переписать код. `excluded` — здесь нет **новой** возможности внедрения:
это либо mechanics, либо решение уже представлено Specification. Эти причины
различаются, поэтому нужны две оси.

## 1. Спорный пример: `_safe_path` в manifest parser

[Исходник helper](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/static_artifact_incremental_stage.py#L33).
Полная функция из [сохранённого packet](runs/2026-10-14-scope-binding-v3-1-results-astra-high/delivery/annotator-03/packet.json),
target-01, fragment-01:

```python
def _safe_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise IncrementalStageError("manifest file path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise IncrementalStageError(f"manifest file path is unsafe: {value!r}")
    return value
```

Мы оцениваем **весь BoolOp второго `if`**, не первый type guard и не функцию
целиком. Он проверяет сразу absolute path, parent components и canonical spelling.
Принятый `value` возвращается без изменения: это проверка представления, не его
нормализация. Имя `unsafe` само по себе не определяет domain role.

Выбранный вызов находится в `_manifest_files`, fragment-04:

```python
path = _safe_path(row.get("path"))
digest = row.get("sha256")
```

Далее manifest paths используются в `_load_local_manifest`, fragment-05:

```python
for relative_path, row in files.items():
    source = bundle_dir / relative_path
    if not source.is_file():
        raise IncrementalStageError(f"local manifest path is missing: {relative_path}")
```

**Что здесь понятно:** путь manifest entry ограничивают до использования при
bundle-relative file access. **Что остаётся спорным:** какой contract реализует
вся проверка в этом применении?

| Возможный contract — это трактовки, не новые факты | Как он меняет оценку |
| --- | --- |
| «Файловый адаптер принимает только canonical relative POSIX paths» | Mechanics: технический precondition выбранного способа обращения к файлам |
| «Публикуемый artifact reference обязан быть canonical relative path без parent components» | Policy: именованное правило допустимости ссылок на артефакты |

Один и тот же fragment совместим с обоими смыслами. File access не делает правило
автоматически mechanics, а отбор допустимых строк не делает любой parser policy.
Нужен witness primary contract. Документы для другой evidence view описывают
fail-closed traversal и authoritative manifest index — поэтому для **documented
application** D1 подтверждает policy. Эти отсутствующие документы не подставлены
задним числом в no-doc task.

Для no-doc application предложено **`needs_review / unknown`**. Это не finding
«код неправильный» и не обещание, что LLM должна угадать intent. Проверка сама по
себе также не доказывает physical filesystem containment, например через symlinks.

Общий `_safe_path` — ещё одна единица оценки: его используют также для staging
prefix. Смысл одного manifest binding не переносится автоматически на все uses.

## 2. Более ясный кандидат: gate перед refinement

Из [candidate_move](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/product_workspace_next_moves.py#L70),
[packet annotator-04](runs/2026-10-14-scope-binding-v3-1-results-astra-high/delivery/annotator-04/packet.json),
target-02, fragment-01; signature и формирование возвращаемого dict опущены:

```python
gate = node.gate_state
if gate != "none":
    if gate not in gate_order or gate not in GATE_ACTIONS:
        raise ValueError(f"unsupported gate state for {node.id}: {gate}")
    kind, next_gap, hint_template = GATE_ACTIONS[gate]
    command_hint = hint_template.format(spec_id=node.id)
    rank = gate_order.index(gate)
elif node.status in status_order:
    next_gap = "targeted_refinement"
    command_hint = f"Run a targeted dry-run for {node.id}, then refine one bounded concern."
    rank = len(gate_order) + status_order.index(node.status)
    kind = "refine_spec"
else:
    return None
```

Target — только **`gate != "none"`**. Из кода видно содержательное решение:
outstanding gate выбирает gate work вместо status-based refinement; rank ставит
refinement после gates. Это выбор приоритета domain obligations.

Предложение: **`eligible / policy`**. Такой rule можно назвать, адресовать,
тестировать и наблюдать централизованно. Последующий `GATE_ACTIONS[gate]` — другой
участок; его роль не подменяет вопрос о precedence. Здесь не требуется README,
чтобы увидеть показанные alternatives и priority. При этом речь об advisory
next move, не о доказательстве исполнения работы или выдачи полномочий.

Это одна из двух контрольных семей, ожидающих подтверждения в readiness matrix.

## 3. Технический control: newline в YAML

[dump_canonical_yaml](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/spec_yaml.py#L64),
[packet annotator-01](runs/2026-10-14-scope-binding-v3-1-results-astra-high/delivery/annotator-01/packet.json),
target-04, fragment-01:

```python
def dump_canonical_yaml(data: dict[str, Any]) -> str:
    rendered = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered
```

Target — **`not rendered.endswith("\n")`**. Его непосредственный effect — дописать
один terminator к сериализованному тексту. Он не выбирает разрешённую работу,
приоритет обязательств или валидность BDD-сценария.

Предложение: **`excluded / mechanics`**. В выбранном architecture profile обычная
serialization/representation mechanics остаётся procedural. Это правило
архитектурного стиля оценки, не математическое свойство любого newline check во
всех программах. Здесь мы не предлагаем отдельную Specification только потому,
что встретился `if`. Контрольное предложение ещё не human-confirmed.

## 4. Уже оформленная policy: невалидный BDD step

В [BDDScenarioValuesSpec.findings](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/native_bdd/values_spec.py#L23)
есть такой fragment:

```python
findings.extend(
    issue("invalid_value", f"{path}.steps[{i}]")
    for i, step in enumerate(entry.steps)
    if not step.valid
)
```

Target — **`not step.valid`**. Он выбирает шаги, для которых формируется
scenario-values violation. `BDDScenarioValuesSpec` наследует `BDDPolicy`, а тот
— `Specification[BDDContext]`. Существенно не имя класса, а показанный evaluation
path. В `BDDPolicy` verdict определяется этими findings:

```python
def _evaluate(self, candidate: BDDContext, recorder: TraceRecorder | None) -> bool:
    return not self.findings(candidate)
```

И [composition](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/tools/native_bdd/composition.py#L35)
получает verdict, затем сами findings:

```python
passed = policy.is_satisfied_by(context, recorder=recorder)
current_findings = policy.findings(context)
findings.extend(current_findings)
```

Все три snippets — из
[packet annotator-01](runs/2026-10-14-scope-binding-v3-1-results-astra-high/delivery/annotator-01/packet.json),
target-03, fragments 01/03/05. D2 подтверждает **`excluded / policy`**:

- `policy`: selected predicate участвует в domain rule;
- `excluded`: **новую** Specification для того же решения выделять не нужно;
- прямой вызов `findings` ради diagnostics не делает сам predicate mechanics.

Сбор готовых findings в список можно оценивать отдельно как orchestration,
но это уже другой target. Мы не утверждаем точные внутренние правила `step.valid`,
runtime execution или чистоту всех вызываемых методов.

## Что утверждать и что из этого не следует

Для завершения [16-task readiness matrix](runs/2026-10-15-scope-reference-readiness-v1/README.md)
предложены три пункта: no-doc manifest `needs_review / unknown`, gate precedence
`eligible / policy`, newline formatting `excluded / mechanics`. D2 для BDD уже
подтверждён; его не нужно подтверждать повторно. D1/D2 и raw outcomes сохранены.

Это вопросы о **пригодности архитектурного представления**, не список runtime
bugs и не измерение скорости или количества дефектов. На основании таблицы
рефакторинг не запускался, новые метрики не начислялись, scoring не включался.
Новый provider/model run не нужен, чтобы прочитать код и выбрать эти трактовки.
