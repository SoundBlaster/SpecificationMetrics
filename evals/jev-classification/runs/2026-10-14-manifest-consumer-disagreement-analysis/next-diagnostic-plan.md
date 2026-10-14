# Следующий diagnostic: declaration против application

Статус: proposal, не frozen protocol; ничего не запущено. Цель — проверить,
уменьшает ли явная единица оценки scope ambiguity при неизменной наблюдаемой
логике. Это не поиск prompt, который гарантирует желаемый label.

## Гипотезы

- **H_scope:** существенная часть разногласия связана с тем, что shared
  definition и manifest application не различены в задании.
- **H_threshold:** даже при явном subject остаётся разный порог достаточности
  consumer-only evidence; новый scope сам по себе это не исправит.
- **H_order:** порядок/позиция cases способны объяснить различия. Текущие
  три ответа не отделяют этот эффект от rater variability.

Гипотезы не объявляются взаимоисключающими и ещё не проверены. Внутреннее reasoning
модели по label не выводится.

## Предлагаемый минимальный дизайн

Держать consumers фиксированными и использовать 2×2:

| Cell | Единица оценки | Документы |
| --- | --- | --- |
| A | shared definition | нет |
| B | shared definition | есть |
| C | конкретное application | нет |
| D | конкретное application | есть |

Focal application — существующий вызов `_safe_path(row.get("path"))` внутри
`_manifest_files`. Сам exact BoolOp неизменен. Для application фиксируются source
revision, адрес expression, адрес callsite, semantic subject как `files[].path`,
точные argument bindings и error/return boundary. Не записывать заранее policy,
eligible или желаемый результат. Staging-prefix use остаётся видимым, но является
другим use, а не основанием перенести его роль на выбранное application.

Если сохранять прежний объём: четыре **различных dependency families**, 12 свежих
контекстов по четыре cases = 48 rows, три повторения на target-cell. Для каждого
control тоже выбрать реальный definition/application pair; не приклеивать
неприменимую scope-метку к прежнему кейсу. Каждый контекст получает все четыре
cells на разных families, только один view на family; никакого второго вида того
же helper в одном контексте. До запуска проверить прямые утечки definitions.

Эта схема является бюджетным эскизом. Для claims о H_order нужен отдельный
balanced schedule: три повторения не покрывают все четыре позиции для одной
cell. Если понадобится полный target-cell×position balance, сначала пересчитать
объём и зафиксировать другой protocol; не обещать это свойство текущим 48 rows.

## Подготовительные шаги

1. Принять operational meaning definition/application и отдельно правила
   дедупликации role bindings; ни определения, ни callsites не считать новыми
   кандидатами автоматически.
2. Найти и привязать четыре независимые source families и их реальные callsites.
   Проверить полноту scope без выбора labels, сохранить лицензии и provenance.
3. Сформировать v3 packets/rubric с явным scope; записать факторы, целевые
   сравнения, order limits и prospective review criteria **до разметки**.
4. Сохранить model request, контексты, raw attempts, exclusions и actual-file
   preflight. Новые provider/API calls требуют отдельного согласованного запуска.
5. Получить независимый review, затем запускать. Этот документ не заменяет
   materialized preparation или разрешение на новый inference experiment.

## Как различать результаты

- Сравнить A↔C и B↔D внутри каждого source target; документы A↔B и C↔D
  оценивать отдельно. Не pooling разных семей в общий treatment effect.
- Для каждой cell показать обе label histograms, decisive coverage, разногласия
  и rationale, которое названо role witness. Согласие не является correctness.
- Semantic reviewer проверяет попадание rationale в назначенный subject/scope,
  отсутствие переноса policy из чужого use и отсутствие exclusion только из-за
  ненайденного документа. Review обязан оставаться отдельно от model labels.
- Если в consumer-only application повторяется disagreement о том, является ли
  manifest admission самостоятельным правилом, **H_scope не объясняет весь
  эффект**; переходить к контракту sufficiency, а не усиливать prompt до согласия.
- Если scope не меняет аргументацию и результаты, считать это evidence против
  практической полезности данного уточнения в этом small-n опыте.
- Если disagreement меняет только место при перестановке, приоритет получает
  order diagnostic. Без отдельного контролируемого сравнения это лишь сигнал.
- Даже единообразный label после уточнения scope не подтверждает его истинность:
  accuracy требует принятого reference/adjudication, а каузальный вывод —
  адекватного order/rater control и достаточного объёма.

## Вопрос для будущей adjudication

Для manifest application является ли точное canonical POSIX spelling частью
устойчивого reference/identity contract либо ограничением текущего adapter?
И к чему относится решение о рефакторинге: одному общему predicate или отдельной
композиции reference policy, использующей технический predicate? Не отвечать
на эти вопросы большинством LLM-голосов и не создавать canonical Requirement
из нового аналитического документа.
