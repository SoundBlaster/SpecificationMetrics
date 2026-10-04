//! Detect newly introduced procedural copies of project-registered rules.
mod ast;
mod git;

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, ensure};
use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::classify::JevClient;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Catalog {
    schema_version: u32,
    project: String,
    rules: Vec<Rule>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Rule {
    id: String,
    bounded_context: String,
    paths: Vec<String>,
    canonical_path: String,
    canonical_symbol: String,
    canonical_digest: String,
    #[serde(default)]
    templates: Vec<Template>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Template {
    id: String,
    expression: String,
    #[serde(default)]
    renameable_identifiers: Vec<String>,
    source_url: String,
}

struct Pattern {
    id: String,
    expr: ast::Expr,
    binders: Vec<String>,
}

struct IndexedRule {
    rule: Rule,
    declaration: String,
    patterns: Vec<Pattern>,
}

#[derive(Debug, Deserialize, Serialize)]
pub(crate) struct Finding {
    pub rule_id: String,
    pub path: String,
    pub line: usize,
    pub kind: String,
    pub construct: String,
    pub introduced: bool,
    pub template_id: Option<String>,
    pub expression: String,
    pub canonical_path: String,
    pub canonical_symbol: String,
    pub bounded_context: String,
    pub semantic_suggestion: Option<Value>,
}

#[derive(Debug, Deserialize, Serialize)]
pub(crate) struct Report {
    pub artifact_kind: String,
    pub schema_version: u32,
    pub project: String,
    pub base_revision: String,
    pub head_revision: String,
    pub catalog_digest: String,
    pub analyzer_version: String,
    pub scope: String,
    pub status: String,
    pub before_reimplementations: usize,
    pub after_reimplementations: usize,
    pub new_reimplementations: usize,
    pub new_near_matches: usize,
    pub reused_specifications: usize,
    pub files_checked: usize,
    pub diagnostics: Vec<String>,
    pub findings: Vec<Finding>,
    pub semantic_review_requests: Vec<Value>,
}

pub(crate) fn digest(source: &str) -> String {
    format!("blake3:{}", blake3::hash(source.as_bytes()).to_hex())
}

fn valid_path(path: &str) -> bool {
    !path.is_empty()
        && !path.contains('\\')
        && !path.starts_with('/')
        && path.split('/').all(|p| !matches!(p, "" | "." | ".."))
}

fn in_scope(rule: &Rule, path: &str) -> bool {
    rule.paths
        .iter()
        .any(|p| path == p || path.starts_with(&format!("{p}/")))
}

pub(crate) fn definition(root: &Path, reference: &str, path: &str, symbol: &str) -> Result<Value> {
    ensure!(valid_path(path), "invalid canonical path");
    let revision = git::revision(root, reference)?;
    let source = git::source(root, &revision, path)?.context("canonical source is absent")?;
    let tree = ast::parse(&source)?;
    let node = ast::declaration(&tree, &source, symbol)?;
    Ok(json!({"revision": revision, "path": path, "symbol": symbol,
        "digest": digest(ast::text(node,&source)), "line":node.start_position().row+1,
        "code": ast::text(node,&source)}))
}

fn load_catalog(
    root: &Path,
    path: &Path,
    head: &str,
) -> Result<(String, Catalog, Vec<IndexedRule>)> {
    let bytes = fs::read_to_string(path)?;
    let mut catalog: Catalog = toml::from_str(&bytes)?;
    ensure!(
        catalog.schema_version == 1 && !catalog.project.trim().is_empty(),
        "invalid rule catalog"
    );
    ensure!(!catalog.rules.is_empty(), "rule catalog is empty");
    let mut ids = BTreeSet::new();
    let mut indexed = vec![];
    for rule in catalog.rules.drain(..) {
        ensure!(ids.insert(rule.id.clone()), "duplicate rule ID");
        ensure!(
            !rule.bounded_context.trim().is_empty(),
            "rule context is required"
        );
        ensure!(
            valid_path(&rule.canonical_path) && rule.canonical_path.ends_with(".py"),
            "canonical rule must be a relative Python source"
        );
        ensure!(
            !rule.paths.is_empty() && rule.paths.iter().all(|p| valid_path(p)),
            "invalid rule scope"
        );
        let source = git::source(root, head, &rule.canonical_path)?
            .context("canonical rule missing at head")?;
        let tree = ast::parse(&source)?;
        let node = ast::declaration(&tree, &source, &rule.canonical_symbol)?;
        let declaration = ast::text(node, &source).to_owned();
        ensure!(
            digest(&declaration) == rule.canonical_digest,
            "canonical digest changed for {}; review and refresh catalog",
            rule.id
        );
        // The Python v1 adapter supports directly imported PredicateSpec lambda declarations.
        let imported = ast::imported_names(&tree, &source, "specification_core", "PredicateSpec");
        ensure!(
            imported.iter().any(|name| name == "PredicateSpec"),
            "canonical PredicateSpec import required"
        );
        let (lambda, binder) = ast::canonical_predicate(node, &source)?;
        let mut patterns = vec![Pattern {
            id: "canonical".into(),
            expr: ast::expression(lambda, &source),
            binders: vec![binder],
        }];
        let mut template_ids = BTreeSet::new();
        for template in &rule.templates {
            ensure!(
                template.id != "canonical" && template_ids.insert(template.id.clone()),
                "duplicate template ID"
            );
            ensure!(
                template.source_url.starts_with("https://github.com/"),
                "template source provenance required"
            );
            patterns.push(Pattern {
                id: template.id.clone(),
                expr: ast::template(&template.expression)?,
                binders: template.renameable_identifiers.clone(),
            });
        }
        indexed.push(IndexedRule {
            rule,
            declaration,
            patterns,
        });
    }
    Ok((digest(&bytes), catalog, indexed))
}

fn findings(source: &str, path: &str, rules: &[IndexedRule]) -> Result<(Vec<Finding>, usize)> {
    let tree = ast::parse(source)?;
    let mut findings = vec![];
    let mut reused = 0;
    for indexed in rules.iter().filter(|r| in_scope(&r.rule, path)) {
        let excluded = if path == indexed.rule.canonical_path {
            ast::declaration(&tree, source, &indexed.rule.canonical_symbol)
                .ok()
                .map(|n| n.byte_range())
        } else {
            None
        };
        for site in ast::sites(&tree, source, excluded) {
            // A verified import followed by a policy evaluation is reuse, not a copy.
            if verified_reuse(&tree, source, &site.code, &indexed.rule)? {
                reused += 1;
                continue;
            }
            let exact = indexed
                .patterns
                .iter()
                .find(|p| ast::matches(&p.expr, &site.expr, &p.binders));
            let near = exact.is_none()
                && indexed
                    .patterns
                    .iter()
                    .any(|p| ast::similarity(&p.expr, &site.expr));
            if exact.is_none() && !near {
                continue;
            }
            findings.push(Finding {
                rule_id: indexed.rule.id.clone(),
                path: path.into(),
                line: site.line,
                kind: if exact.is_some() {
                    "reimplementation".into()
                } else {
                    "near_match".into()
                },
                construct: site.kind.into(),
                introduced: false,
                template_id: exact.map(|p| p.id.clone()),
                expression: site.code,
                canonical_path: indexed.rule.canonical_path.clone(),
                canonical_symbol: indexed.rule.canonical_symbol.clone(),
                bounded_context: indexed.rule.bounded_context.clone(),
                semantic_suggestion: None,
            });
        }
    }
    Ok((findings, reused))
}

fn verified_reuse(tree: &tree_sitter::Tree, source: &str, code: &str, rule: &Rule) -> Result<bool> {
    let module = rule
        .canonical_path
        .trim_end_matches(".py")
        .rsplit('/')
        .next()
        .unwrap();
    let imported = ast::imported_names(tree, source, module, &rule.canonical_symbol);
    if imported.is_empty() {
        return Ok(false);
    }
    // Conservative shadow guard; aliases/module imports are review-only in v1.
    fn shadow(node: tree_sitter::Node<'_>, source: &str, symbol: &str) -> bool {
        if matches!(
            node.kind(),
            "assignment" | "function_definition" | "class_definition"
        ) && node
            .child_by_field_name("left")
            .or_else(|| node.child_by_field_name("name"))
            .is_some_and(|n| ast::text(n, source) == symbol)
        {
            return true;
        }
        if matches!(node.kind(), "parameters" | "lambda_parameters")
            && ast::text(node, source)
                .split(|c: char| !c.is_alphanumeric() && c != '_')
                .any(|v| v == symbol)
        {
            return true;
        }
        node.named_children(&mut node.walk())
            .any(|n| shadow(n, source, symbol))
    }
    let imported: Vec<_> = imported
        .into_iter()
        .filter(|name| !shadow(tree.root_node(), source, name))
        .collect();
    if imported.is_empty() {
        return Ok(false);
    }
    let expr = format!("__rule__ = ({code})");
    let tree = ast::parse(&expr)?;
    fn evaluation(mut node: tree_sitter::Node<'_>, source: &str, symbol: &str) -> bool {
        while node.kind() == "parenthesized_expression" {
            node = node.named_child(0).unwrap();
        }
        if node.kind() == "not_operator" {
            return node
                .named_child(0)
                .is_some_and(|n| evaluation(n, source, symbol));
        }
        node.kind() == "call"
            && node.child_by_field_name("function").is_some_and(|f| {
                f.kind() == "attribute"
                    && f.child_by_field_name("object")
                        .is_some_and(|o| ast::text(o, source) == symbol)
                    && f.child_by_field_name("attribute")
                        .is_some_and(|a| ast::text(a, source) == "is_satisfied_by")
            })
    }
    let value = tree
        .root_node()
        .named_child(0)
        .and_then(|n| n.named_child(0))
        .and_then(|n| n.child_by_field_name("right"))
        .context("predicate value missing")?;
    Ok(imported.iter().any(|name| evaluation(value, &expr, name)))
}

fn delta_key(f: &Finding) -> String {
    let expression = f.template_id.clone().unwrap_or_else(|| {
        ast::signature(&ast::template(&f.expression).expect("previously parsed"))
    });
    format!("{}:{}:{expression}", f.rule_id, f.kind)
}

pub(crate) fn check(
    root: &Path,
    catalog: &Path,
    base: &str,
    head: &str,
    jev: Option<&JevClient>,
) -> Result<Report> {
    let base = git::revision(root, base)?;
    let head = git::revision(root, head)?;
    let (catalog_digest, catalog, rules) = load_catalog(root, catalog, &head)?;
    let mut report = Report {
        artifact_kind: "rule_reuse_report".into(),
        schema_version: 1,
        project: catalog.project,
        base_revision: base.clone(),
        head_revision: head.clone(),
        catalog_digest,
        analyzer_version: "python-rule-reuse-v1".into(),
        scope: "changed Python files in registered rule path scopes".into(),
        status: "complete".into(),
        before_reimplementations: 0,
        after_reimplementations: 0,
        new_reimplementations: 0,
        new_near_matches: 0,
        reused_specifications: 0,
        files_checked: 0,
        diagnostics: vec![],
        findings: vec![],
        semantic_review_requests: vec![],
    };
    for paths in git::changed(root, &base, &head)? {
        let selected = paths
            .after
            .as_ref()
            .or(paths.before.as_ref())
            .expect("diff path");
        let scoped = |p: &&String| p.ends_with(".py") && rules.iter().any(|r| in_scope(&r.rule, p));
        let before_path = paths.before.as_ref().filter(scoped);
        let after_path = paths.after.as_ref().filter(scoped);
        if before_path.is_none() && after_path.is_none() {
            continue;
        }
        report.files_checked += 1;
        let before = before_path
            .map(|p| git::source(root, &base, p))
            .transpose()?
            .flatten();
        let after = after_path
            .map(|p| git::source(root, &head, p))
            .transpose()?
            .flatten();
        let old = before
            .as_deref()
            .map(|s| findings(s, before_path.unwrap(), &rules))
            .transpose();
        let new = after
            .as_deref()
            .map(|s| findings(s, after_path.unwrap(), &rules))
            .transpose();
        let (old, new, reused) = match (old, new) {
            (Ok(old), Ok(new)) => {
                let (new, reused) = new.unwrap_or_default();
                (old.unwrap_or_default().0, new, reused)
            }
            _ => {
                report.diagnostics.push(format!("parse_issue:{selected}"));
                report.status = "incomplete".into();
                continue;
            }
        };
        report.before_reimplementations +=
            old.iter().filter(|f| f.kind == "reimplementation").count();
        report.after_reimplementations +=
            new.iter().filter(|f| f.kind == "reimplementation").count();
        report.reused_specifications += reused;
        let mut counts = BTreeMap::<String, usize>::new();
        for f in &old {
            *counts.entry(delta_key(f)).or_default() += 1;
        }
        for mut finding in new {
            let count = counts.entry(delta_key(&finding)).or_default();
            finding.introduced = *count == 0;
            *count = count.saturating_sub(1);
            if finding.introduced && finding.kind == "reimplementation" {
                report.new_reimplementations += 1;
            }
            if finding.introduced && finding.kind == "near_match" {
                report.new_near_matches += 1;
                let rule = rules.iter().find(|r| r.rule.id == finding.rule_id).unwrap();
                let request = json!({"candidate":{"path":finding.path,"line":finding.line,"predicate":finding.expression},
                    "existing_rule":{"id":rule.rule.id,"bounded_context":rule.rule.bounded_context,
                                     "path":rule.rule.canonical_path,"symbol":rule.rule.canonical_symbol,
                                     "definition":rule.declaration},
                    "context_limits":"Unlisted callers, data origin and dependencies are omitted."});
                if serde_json::to_vec(&request)?.len() > 24 * 1024 {
                    finding.semantic_suggestion =
                        Some(json!({"choice":"needs_review","diagnostic":"context_too_large"}));
                } else {
                    report
                        .semantic_review_requests
                        .push(json!({"state":request,"questions":questions()}));
                    if let Some(client) = jev {
                        finding.semantic_suggestion = Some(semantic(client, &request));
                    }
                }
            }
            report.findings.push(finding);
        }
    }
    Ok(report)
}

fn questions() -> Value {
    json!({"rule_reuse":{"type":"choice",
        "instructions":"Compare only the candidate predicate and registered rule in the same stated bounded context. Decide whether they implement the same rule over comparable input facts. Matching field names alone is insufficient; do not invent missing facts or input mappings. Changed authority, thresholds or outcomes can define a different rule. Use needs_review for insufficient evidence. This is a suggestion and never authorizes a blocking gate or code rewrite.",
        "criteria":{"same_rule":"The candidate repeats the registered rule over comparable facts.",
                    "different_rule":"The visible evidence establishes a different rule.",
                    "needs_review":"Evidence or context is insufficient to reliably compare."}}})
}

fn semantic_answer(client: &JevClient, state: &Value) -> Value {
    let result = client
        .request(state, &questions())
        .ok()
        .and_then(|b| serde_json::from_slice::<Value>(&b).ok());
    let Some(body) = result else {
        return json!({"choice":"needs_review","diagnostic":"provider_error","cacheable":false});
    };
    let answer = &body["answers"]["rule_reuse"];
    let choice = answer["choice"].as_str().unwrap_or("");
    let labels = ["same_rule", "different_rule", "needs_review"];
    let probabilities = answer["probabilities"].as_object();
    let valid = labels.contains(&choice)
        && answer["type"] == "choice"
        && body["model"]
            .as_str()
            .is_some_and(|m| !m.is_empty() && m.len() <= 128)
        && answer["confidence"]
            .as_f64()
            .is_some_and(|v| (0.0..=1.0).contains(&v))
        && probabilities.is_some_and(|p| {
            p.len() == 3
                && labels.iter().all(|label| {
                    p.get(*label)
                        .and_then(Value::as_f64)
                        .is_some_and(|v| (0.0..=1.0).contains(&v))
                })
                && (p.values().filter_map(Value::as_f64).sum::<f64>() - 1.0).abs() < 0.02
        });
    if !valid {
        return json!({"choice":"needs_review","diagnostic":"malformed_provider_output","cacheable":false});
    }
    json!({"choice":choice,"probabilities":answer["probabilities"],"confidence":answer["confidence"],
           "returned_model":body["model"],"model_revision":null,"cacheable":false,
           "rationale":{"text":null,"source":"unavailable"}})
}

fn semantic(client: &JevClient, state: &Value) -> Value {
    let mut answer = semantic_answer(client, state);
    answer["requested_model"] = json!(client.requested_model());
    answer["prompt_version"] = json!("rule-reuse-semantic-v1");
    answer["prompt_digest"] = json!(digest(&questions().to_string()));
    answer["input_digest"] = json!(digest(&state.to_string()));
    answer["cacheable"] = json!(false);
    answer
}

pub(crate) fn save(path: &Path, report: &Report) -> Result<i64> {
    if let Some(parent) = path.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent)?;
    }
    let connection = Connection::open(path)?;
    connection.execute_batch(
        "CREATE TABLE IF NOT EXISTS rule_reuse_snapshots (
        id INTEGER PRIMARY KEY, recorded_at_unix_ms INTEGER NOT NULL,
        snapshot_key TEXT NOT NULL UNIQUE, report_json TEXT NOT NULL);",
    )?;
    let body = serde_json::to_string(report)?;
    let now = i64::try_from(SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis())?;
    connection.execute("INSERT OR IGNORE INTO rule_reuse_snapshots(recorded_at_unix_ms,snapshot_key,report_json) VALUES (?1,?2,?3)",
        params![now,digest(&body),body])?;
    Ok(connection.query_row(
        "SELECT id FROM rule_reuse_snapshots WHERE snapshot_key=?1",
        [digest(&body)],
        |r| r.get(0),
    )?)
}

pub(crate) fn history(path: &Path, limit: usize) -> Result<Value> {
    ensure!(
        path.is_file() && limit > 0 && limit <= 1000,
        "existing store and limit 1..=1000 required"
    );
    let connection = Connection::open(path)?;
    let mut query=connection.prepare("SELECT id,recorded_at_unix_ms,report_json FROM rule_reuse_snapshots ORDER BY id DESC LIMIT ?1")?;
    let rows = query.query_map([limit], |row| {
        Ok((
            row.get::<_, i64>(0)?,
            row.get::<_, i64>(1)?,
            row.get::<_, String>(2)?,
        ))
    })?;
    let mut records = vec![];
    for row in rows {
        let (id, time, body) = row?;
        records.push(json!({"id":id,"recorded_at_unix_ms":time,"report":serde_json::from_str::<Value>(&body)?}));
    }
    Ok(json!(records))
}

#[cfg(test)]
mod tests;
