# Уточнение архитектурного подхода: четыре решения человека

2026-10-15. **Текущее руководство для выбора рефакторинга.** Это nonblind
human clarification после показа четырёх примеров. Точные слова пользователя,
предыдущая версия пояснения и привязки к 16 frozen tasks — в [decision.json](decision.json).
Привязку семейных решений ко всем четырём views выполнил integrator; человек
не рассматривал каждую из 16 строк отдельно. Источником authority служит его
объяснение, а не совпадение модельных ответов.

| Пример | Принятое решение | Следствие |
| --- | --- | --- |
| Manifest path | Смотреть intent, proposal и spec; при сохраняющемся сомнении предпочитать строгую формализацию | Ambiguity не означает «оставить процедурно» |
| Gate precedence | Явный кандидат в Specification | `eligible / policy`; повторное одобрение не требуется |
| YAML newline | Оставить ответственность formatter/linter | `excluded / mechanics`; отдельная Specification не нужна |
| BDD invalid step | Решение уже принадлежит Specification | `excluded / policy`; простые NOT/AND/OR не требуют обёртки |

## Intent прежде догадок о коде

В pinned SpecGraph `51c8d93cc385569864b3cd7f5040d4b3e0820a1b`
[proposal 0215](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/docs/proposals/0215_incremental_static_workspace_deployment.md#L64)
требует fail-closed path traversal и сохранения относительных durable URL paths.
[Operator documentation](https://github.com/0al-spec/SpecGraph/blob/51c8d93cc385569864b3cd7f5040d4b3e0820a1b/docs/static_artifact_publish.md#L44)
объясняет авторитетность manifest index. Полные файлы прочитаны из git objects;
их SHA-256 совпадают с сохранённым source mapping. Это достаточное документальное
основание для manifest-применения. Proposal имеет статус implemented proposal,
он не переименован в canonical Requirement.

Целевой поиск `path traversal|incremental.static|0215|canonical.*path|parent.*components`
в `specs/` той же revision не выявил прямого traversal/0215 contract. Это
ограниченный поиск, а не доказательство отсутствия всех возможных spec-связей.
Общий primary contract helper для manifest и staging-prefix применений этим
автоматически не установлен.

Для рабочего решения сначала используем доступные документы. В историческом
no-doc задании этих документов не было: его входы и reference нельзя изменить
задним числом. Предпочтение формализовать сомнительное решение уже установлено;
уверенность в его domain role — отдельный вопрос.

## Порядок принятия решения

1. Указать смысл решения и его alternatives; найти связанные intent, proposal,
   spec и существующие правила инструментов. Зафиксировать источник и authority.
2. Если ровно эта ответственность уже выполняется formatter/linter, использовать
   его правила. Не вводить параллельную Specification ради проверки формата.
   Это архитектурный принцип; мы не доказали, что конкретный внешний formatter
   уже исполняет этот точный YAML check в данном проекте.
3. Если решение уже представлено Specification или простой композицией известных
   Specifications, переиспользовать его. Не превращать NOT/AND/OR в новые wrappers.
4. Если это ещё inline domain decision, формализовать его. При сохраняющемся
   сомнении после поиска intent предпочесть строгую формализацию с явно записанным
   contract. Не выдавать неподтверждённую роль за доказанный факт.

В BDD-фрагменте `step.valid` — Boolean fact. Его связь со Specification доказана
путём findings → evaluation. Это не основание считать любой `not boolean`
композицией Specifications. Для настоящей композиции нужно распознать исходные
спецификации и связь с их evaluation. Предел сложности композиции пока не задан;
числовой порог этим решением не вводится. Отдельное имя для самостоятельного
доменного понятия возможно, но простой Boolean operator сам его не требует.

## Что меняет это уточнение

[Первое adjudication](../2026-10-14-scope-binding-adjudication-v1/README.md),
[предложение D3](../2026-10-15-manifest-application-without-documents-analysis/README.md)
и [readiness v1](../2026-10-15-scope-reference-readiness-v1/README.md) сохранены как
история. Их wording «controls ещё не подтверждены» описывает прежний момент.
Теперь gate/newline решения подтверждены на уровне семейств; BDD подтверждён
повторно с уточнением композиции. D3 не принят как единственное архитектурное
действие: предпочитаем формализацию, а не остановку на неопределённости.

Не нужно запрашивать те же четыре решения повторно. Следующее техническое
изменение — versioned contract будущей оценки, который различает architectural
recommendation, concern kind и evidence confidence. Текущий `needs_review` не
должен скрывать практическую рекомендацию формализовать.

Это уточнение не включает scorer, не объявляет весь корпус gold и не правит
старые inputs, rubric, raw labels, review или S/U. Scoring reference требует
явного mapping под соответствующую версию контракта. Новых model contexts и
provider requests — 0. Application code не менялся.

`SHA256SUMS` покрывает README и decision.json. Проверка: source digests,
16 уникальных case/task bindings, цитаты исходного кода, локальные ссылки и
отсутствие изменений в предыдущих frozen packages.
