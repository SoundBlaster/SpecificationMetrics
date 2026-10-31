//! Advisory source binding for synchronous factory-backed Python if conditions.
//! This deliberately does not implement the future uses_specification U exclusion.
use std::collections::HashSet;

use serde::Serialize;
use tree_sitter::Node;

use super::python_inheritance::{Binding, binds_name, unique_binding};
use super::{
    ParsedPythonSource, PythonLiveness, PythonSource, expression_path, has_module_getattr,
};
use crate::model::{Candidate, Language, ParseIssue, ScanReport, ScopeIssue};

#[derive(Debug, Serialize)]
pub struct ApplicationReport {
    profile: &'static str,
    metric_effect: &'static str,
    counting_rule_version: u32,
    source_digest: String,
    root: String,
    includes: Vec<String>,
    scope_manifest_digest: Option<String>,
    provisional: bool,
    scope_issues: Vec<ScopeIssue>,
    parse_issues: Vec<ParseIssue>,
    marker_issues: Vec<ParseIssue>,
    analyzed_if_candidates: usize,
    unsupported_candidates: usize,
    if_candidates_without_application_call: usize,
    direct_application: usize,
    mixed_expression: usize,
    unresolved_call: usize,
    sites: Vec<ApplicationSite>,
}

#[derive(Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum Category {
    DirectApplication,
    MixedExpression,
    UnresolvedCall,
}

#[derive(Debug, Serialize)]
struct ApplicationSite {
    candidate: Candidate,
    category: Category,
    calls: Vec<ApplicationCall>,
}

#[derive(Debug, Serialize)]
struct ApplicationCall {
    receiver: String,
    method: &'static str,
    line: usize,
    column: usize,
    target: Option<FactoryTarget>,
    reason: &'static str,
}

#[derive(Clone, Debug, Serialize)]
pub(super) struct FactoryTarget {
    path: String,
    line: usize,
    column: usize,
    pub(super) constructor: String,
}

pub(super) enum Symbol {
    Module(String),
    Constructor(String),
    Value(FactoryTarget),
}

pub fn application_sites(scan: &ScanReport) -> ApplicationReport {
    let sources: Vec<_> = scan
        .sources
        .iter()
        .filter(|source| source.path.ends_with(".py"))
        .filter_map(|source| {
            String::from_utf8(source.bytes.clone())
                .ok()
                .map(|text| PythonSource {
                    path: source.path.clone(),
                    source: text,
                })
        })
        .collect();
    let resolver = PythonLiveness::new(&sources, &scan.specifications);
    let mut report = ApplicationReport {
        profile: "specification-metrics.python-if-applications/v1",
        metric_effect: "none",
        counting_rule_version: crate::model::COUNTING_RULE_VERSION,
        source_digest: scan.source_digest.clone(),
        root: scan.root.clone(),
        includes: scan.includes.clone(),
        scope_manifest_digest: scan.scope_manifest_digest.clone(),
        provisional: scan.scope_review_required
            || !scan.parse_issues.is_empty()
            || !scan.marker_issues.is_empty(),
        scope_issues: scan.scope_issues.clone(),
        parse_issues: scan.parse_issues.clone(),
        marker_issues: scan.marker_issues.clone(),
        analyzed_if_candidates: 0,
        unsupported_candidates: 0,
        if_candidates_without_application_call: 0,
        direct_application: 0,
        mixed_expression: 0,
        unresolved_call: 0,
        sites: Vec::new(),
    };
    for candidate in &scan.candidates {
        if candidate.language != Language::Python || candidate.kind != "if" {
            report.unsupported_candidates += 1;
            continue;
        }
        let condition = resolver
            .sources
            .iter()
            .find(|s| s.path == candidate.path)
            .and_then(|source| {
                find_if(source.tree.root_node(), candidate)
                    .and_then(|node| node.child_by_field_name("condition"))
                    .map(|condition| (source, condition))
            });
        let Some((source, condition)) = condition else {
            report.unsupported_candidates += 1;
            continue;
        };
        report.analyzed_if_candidates += 1;
        let mut calls = Vec::new();
        collect_calls(&resolver, source, condition, &mut calls);
        if calls.is_empty() {
            report.if_candidates_without_application_call += 1;
            continue;
        }
        let category = if calls.iter().any(|call| call.target.is_none()) {
            report.unresolved_call += 1;
            Category::UnresolvedCall
        } else if direct_expression(condition, &source.source) {
            report.direct_application += 1;
            Category::DirectApplication
        } else {
            report.mixed_expression += 1;
            Category::MixedExpression
        };
        report.sites.push(ApplicationSite {
            candidate: candidate.clone(),
            category,
            calls,
        });
    }
    report
}

fn find_if<'a>(node: Node<'a>, candidate: &Candidate) -> Option<Node<'a>> {
    let position = node.start_position();
    if node.kind() == "if_statement"
        && position.row + 1 == candidate.line
        && position.column + 1 == candidate.column
    {
        return Some(node);
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .find_map(|child| find_if(child, candidate))
}

fn application_receiver<'a>(node: Node<'a>, text: &str) -> Option<Node<'a>> {
    if node.kind() != "call" {
        return None;
    }
    let function = node.child_by_field_name("function")?;
    if function.kind() != "attribute"
        || function
            .child_by_field_name("attribute")?
            .utf8_text(text.as_bytes())
            .ok()?
            != "is_satisfied_by"
    {
        return None;
    }
    function.child_by_field_name("object")
}

fn collect_calls(
    resolver: &PythonLiveness,
    source: &ParsedPythonSource,
    node: Node<'_>,
    calls: &mut Vec<ApplicationCall>,
) {
    // Deferred bodies and comprehension scopes do not establish a guard's decision.
    if matches!(
        node.kind(),
        "lambda"
            | "generator_expression"
            | "list_comprehension"
            | "set_comprehension"
            | "dictionary_comprehension"
    ) {
        return;
    }
    if let Some(receiver) = application_receiver(node, &source.source) {
        let target = resolved_factory(resolver, source, node, receiver)
            .filter(|target| target.constructor == "PredicateSpec");
        let reason = if target.is_some() {
            "resolved_static_factory_binding"
        } else {
            "binding_not_proven_in_supported_static_subset"
        };
        let point = node.start_position();
        calls.push(ApplicationCall {
            receiver: receiver
                .utf8_text(source.source.as_bytes())
                .unwrap_or_default()
                .to_owned(),
            method: "is_satisfied_by",
            line: point.row + 1,
            column: point.column + 1,
            target,
            reason,
        });
        // Argument construction is outside the boolean-result classification.
        return;
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_calls(resolver, source, child, calls);
    }
}

pub(super) fn resolved_factory(
    resolver: &PythonLiveness,
    source: &ParsedPythonSource,
    call: Node<'_>,
    receiver: Node<'_>,
) -> Option<FactoryTarget> {
    match resolved_call_symbol(resolver, source, call, receiver)? {
        Symbol::Value(target) => Some(target),
        _ => None,
    }
}

pub(super) fn resolved_call_symbol(
    resolver: &PythonLiveness,
    source: &ParsedPythonSource,
    call: Node<'_>,
    receiver: Node<'_>,
) -> Option<Symbol> {
    let name = root_name(receiver, &source.source)?;
    if resolver.parse_failed.contains(&source.path) || lexical_binding(call, &name, &source.source)
    {
        return None;
    }
    let mut ancestor = call.parent();
    while let Some(node) = ancestor {
        if matches!(
            node.kind(),
            "generator_expression"
                | "list_comprehension"
                | "set_comprehension"
                | "dictionary_comprehension"
        ) {
            return None;
        }
        ancestor = node.parent();
    }
    resolve_expression(resolver, source, receiver, &mut HashSet::new())
}

fn direct_expression(node: Node<'_>, text: &str) -> bool {
    if application_receiver(node, text).is_some() {
        return true;
    }
    if !matches!(
        node.kind(),
        "parenthesized_expression" | "not_operator" | "boolean_operator"
    ) {
        return false;
    }
    let mut cursor = node.walk();
    let children: Vec<_> = node
        .named_children(&mut cursor)
        .filter(|n| n.kind() != "comment")
        .collect();
    !children.is_empty() && children.iter().all(|child| direct_expression(*child, text))
}

fn root_name(node: Node<'_>, source: &str) -> Option<String> {
    Some(expression_path(node, source)?.split('.').next()?.to_owned())
}

pub(super) fn lexical_binding(mut node: Node<'_>, name: &str, text: &str) -> bool {
    let mut inside_function = false;
    while let Some(parent) = node.parent() {
        if parent.kind() == "lambda" || (parent.kind() == "class_definition" && !inside_function) {
            return true;
        }
        // Defaults and annotations are outside the function's local body scope.
        // Only crossing the body boundary makes a method skip its class locals.
        if parent.kind() == "function_definition"
            && parent.child_by_field_name("body") == Some(node)
        {
            inside_function = true;
            // A method's bare name skips its class namespace. Enclosing function
            // scopes still participate in closure lookup and can shadow globals.
            if parent
                .child_by_field_name("parameters")
                .is_some_and(|parameters| parameters_bind(parameters, name, text))
                || parent.child_by_field_name("body").is_some_and(|body| {
                    binds_name(body, name, text.as_bytes()) || has_scope_directive(body)
                })
            {
                return true;
            }
        }
        node = parent;
    }
    false
}

fn parameters_bind(parameters: Node<'_>, name: &str, text: &str) -> bool {
    let mut cursor = parameters.walk();
    parameters.named_children(&mut cursor).any(|parameter| {
        let target = match parameter.kind() {
            "default_parameter" | "typed_default_parameter" => {
                parameter.child_by_field_name("name")
            }
            "typed_parameter" => {
                let annotation = parameter.child_by_field_name("type");
                let mut cursor = parameter.walk();
                parameter
                    .named_children(&mut cursor)
                    .find(|child| Some(*child) != annotation && !child.is_extra())
            }
            _ => Some(parameter),
        };
        target.is_some_and(|target| mentions_identifier(target, name, text))
    })
}

fn mentions_identifier(node: Node<'_>, name: &str, text: &str) -> bool {
    if node.kind() == "identifier" && node.utf8_text(text.as_bytes()).ok() == Some(name) {
        return true;
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| mentions_identifier(child, name, text))
}

fn has_scope_directive(node: Node<'_>) -> bool {
    if matches!(node.kind(), "global_statement" | "nonlocal_statement") {
        return true;
    }
    if matches!(
        node.kind(),
        "function_definition" | "class_definition" | "lambda"
    ) {
        return false;
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor).any(has_scope_directive)
}

fn resolve_expression(
    resolver: &PythonLiveness,
    source: &ParsedPythonSource,
    node: Node<'_>,
    visited: &mut HashSet<(String, String)>,
) -> Option<Symbol> {
    let path = expression_path(node, &source.source)?;
    let mut parts = path.split('.');
    let root = parts.next()?;
    if mutates_object(source.tree.root_node(), root, &source.source) {
        return None;
    }
    let (position, _) = unique_binding(source, root)?;
    if position >= node.start_byte() {
        return None;
    }
    let mut symbol = resolve_symbol(resolver, &source.module, root, visited)?;
    for part in parts {
        symbol = match symbol {
            Symbol::Module(module) => {
                resolve_symbol(resolver, &module, part, visited).or_else(|| {
                    explicit_module_import(source, &format!("{module}.{part}"), node.start_byte())
                        .then(|| imported_submodule(resolver, &module, part))
                        .flatten()
                })?
            }
            _ => return None,
        };
    }
    Some(symbol)
}

fn resolve_symbol(
    resolver: &PythonLiveness,
    module: &str,
    name: &str,
    visited: &mut HashSet<(String, String)>,
) -> Option<Symbol> {
    if !visited.insert((module.to_owned(), name.to_owned())) {
        return None;
    }
    let mut sources = resolver.sources.iter().filter(|s| s.module == module);
    let source = sources.next();
    if sources.next().is_some() {
        return None;
    }
    let Some(source) = source else {
        return (module == "specification_core" && matches!(name, "PredicateSpec" | "FirstMatch"))
            .then(|| Symbol::Constructor(name.to_owned()));
    };
    if resolver.parse_failed.contains(&source.path)
        || has_module_getattr(source.tree.root_node(), &source.source)
        || mutates_object(source.tree.root_node(), name, &source.source)
    {
        return None;
    }
    let (position, binding) = unique_binding(source, name)?;
    match binding {
        Binding::Imported(module, name) => resolve_symbol(resolver, &module, &name, visited)
            .or_else(|| imported_submodule(resolver, &module, &name)),
        Binding::Module(module) => Some(Symbol::Module(module)),
        Binding::Other => {
            let node = source
                .tree
                .root_node()
                .named_descendant_for_byte_range(position, position)?;
            let mut statement = node;
            while statement.parent().is_some_and(|p| p.kind() != "module") {
                statement = statement.parent()?;
            }
            if statement.kind() != "expression_statement" {
                return None;
            }
            let assignment = statement.named_child(0)?;
            if assignment.kind() != "assignment"
                || assignment.child_by_field_name("left")?.kind() != "identifier"
            {
                return None;
            }
            let call = assignment.child_by_field_name("right")?;
            if call.kind() != "call" {
                return None;
            }
            let function = call.child_by_field_name("function")?;
            let mut fallback_visited = visited.clone();
            let constructor = if let Some(Symbol::Constructor(constructor)) =
                resolve_expression(resolver, source, function, visited)
            {
                constructor
            } else if function.kind() == "attribute"
                && function
                    .child_by_field_name("attribute")?
                    .utf8_text(source.source.as_bytes())
                    .ok()?
                    == "with_fallback"
                && let Some(Symbol::Constructor(constructor)) = resolve_expression(
                    resolver,
                    source,
                    function.child_by_field_name("object")?,
                    &mut fallback_visited,
                )
                && constructor == "FirstMatch"
            {
                "FirstMatch.with_fallback".to_owned()
            } else {
                return None;
            };
            let point = call.start_position();
            Some(Symbol::Value(FactoryTarget {
                path: source.path.clone(),
                line: point.row + 1,
                column: point.column + 1,
                constructor,
            }))
        }
        Binding::Class => None,
    }
}

fn explicit_module_import(source: &ParsedPythonSource, module: &str, before: usize) -> bool {
    let mut cursor = source.tree.root_node().walk();
    source
        .tree
        .root_node()
        .named_children(&mut cursor)
        .any(|node| {
            if node.kind() != "import_statement" || node.start_byte() >= before {
                return false;
            }
            let mut cursor = node.walk();
            node.named_children(&mut cursor).any(|import| {
                let name = import.child_by_field_name("name").unwrap_or(import);
                name.utf8_text(source.source.as_bytes())
                    .ok()
                    .is_some_and(|name| name == module || name.starts_with(&format!("{module}.")))
            })
        })
}

fn imported_submodule(resolver: &PythonLiveness, module: &str, name: &str) -> Option<Symbol> {
    let target = format!("{module}.{name}");
    let targets: Vec<_> = resolver
        .sources
        .iter()
        .filter(|s| s.module == target)
        .collect();
    if targets.len() != 1 || resolver.parse_failed.contains(&targets[0].path) {
        return None;
    }
    let parents: Vec<_> = resolver
        .sources
        .iter()
        .filter(|s| s.module == module)
        .collect();
    if parents.len() > 1
        || parents.iter().any(|s| {
            resolver.parse_failed.contains(&s.path)
                || has_module_getattr(s.tree.root_node(), &s.source)
                || binds_name(s.tree.root_node(), name, s.source.as_bytes())
        })
    {
        return None;
    }
    Some(Symbol::Module(target))
}

pub(super) fn mutates_object(node: Node<'_>, name: &str, text: &str) -> bool {
    // Capture patterns and type-alias binding have different binding grammars.
    if matches!(node.kind(), "match_statement" | "type_alias_statement")
        && mentions_identifier(node, name, text)
    {
        return true;
    }
    if matches!(
        node.kind(),
        "assignment" | "augmented_assignment" | "delete_statement"
    ) {
        let target = node.child_by_field_name("left").unwrap_or(node);
        if mutates_target(target, name, text) {
            return true;
        }
    }
    if node.kind() == "call"
        && node
            .child_by_field_name("function")
            .and_then(|f| f.utf8_text(text.as_bytes()).ok())
            .is_some_and(|f| matches!(f, "setattr" | "delattr"))
        && node
            .child_by_field_name("arguments")
            .and_then(|a| a.named_child(0))
            .is_some_and(|argument| root_name(argument, text).as_deref() == Some(name))
    {
        return true;
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| mutates_object(child, name, text))
}

fn mutates_target(node: Node<'_>, name: &str, text: &str) -> bool {
    if matches!(node.kind(), "attribute" | "subscript") {
        return root_name(
            node.child_by_field_name("object")
                .or_else(|| node.child_by_field_name("value"))
                .unwrap_or(node),
            text,
        )
        .as_deref()
            == Some(name);
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| mutates_target(child, name, text))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{live, scan, scope::ScopeManifest};
    use std::{fs, path::Path};
    use tempfile::tempdir;

    fn write(root: &Path, path: &str, source: &str) {
        let path = root.join(path);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, source).unwrap();
    }

    fn analyze(files: &[(&str, &str)]) -> (ScanReport, ApplicationReport) {
        let dir = tempdir().unwrap();
        for (path, text) in files {
            write(dir.path(), path, text);
        }
        let manifest = ScopeManifest::parse(
            "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = ['.']\n",
        )
        .unwrap();
        let scan = scan::scan_with_scope(dir.path(), &[], Some(&manifest)).unwrap();
        let report = application_sites(&scan);
        (scan, report)
    }

    const POLICY: &str = "from specification_core import PredicateSpec\nRULE = PredicateSpec(lambda c: c.ready, name='ready')\n";

    #[test]
    fn specgraph_style_imports_and_negation_keep_raw_u_unchanged() {
        let (scan, report) = analyze(&[
            ("pkg/policy.py", POLICY),
            (
                "pkg/app.py",
                "from .policy import RULE\ndef evaluate(ctx):\n    if not RULE.is_satisfied_by(ctx): return 'blocked'\n",
            ),
        ]);
        assert_eq!(report.direct_application, 1);
        assert_eq!(report.unresolved_call, 0);
        assert!(!report.provisional);
        let site = &report.sites[0];
        assert_eq!(site.candidate.fingerprint, scan.candidates[0].fingerprint);
        assert_eq!(site.calls[0].target.as_ref().unwrap().path, "pkg/policy.py");
        assert_eq!(site.calls[0].target.as_ref().unwrap().line, 2);
        let raw = live::measure(&scan, None).unwrap();
        assert_eq!(raw.remaining_opportunities, 1);
        assert_eq!(raw.specification_definitions, 1);
        let before = serde_json::to_value(&scan).unwrap();
        application_sites(&scan);
        assert_eq!(before, serde_json::to_value(&scan).unwrap());
    }

    #[test]
    fn inline_and_applied_pair_preserves_primary_counting_contract() {
        let (inline, inline_report) =
            analyze(&[("app.py", "def run(c):\n    if c.ready: return True\n")]);
        let text = format!("{POLICY}def run(c):\n    if RULE.is_satisfied_by(c): return True\n");
        let (applied, report) = analyze(&[("app.py", &text)]);
        assert_eq!(inline_report.if_candidates_without_application_call, 1);
        assert_eq!(report.direct_application, 1);
        assert_eq!(
            live::measure(&inline, None)
                .unwrap()
                .remaining_opportunities,
            1
        );
        assert_eq!(
            live::measure(&applied, None)
                .unwrap()
                .remaining_opportunities,
            1
        );
    }

    #[test]
    fn boolean_composition_is_direct_but_additional_checks_are_mixed() {
        let text = format!(
            "{POLICY}def run(c):\n    if (RULE.is_satisfied_by(c) and not RULE.is_satisfied_by(c)): pass\n    if RULE.is_satisfied_by(c) and c.extra: pass\n    if RULE.is_satisfied_by(c) == True: pass\n    if bool(RULE.is_satisfied_by(c)): pass\n"
        );
        let (_, report) = analyze(&[("app.py", &text)]);
        assert_eq!(report.direct_application, 1);
        assert_eq!(report.mixed_expression, 3);
        assert_eq!(report.sites[0].calls.len(), 2);
    }

    #[test]
    fn module_aliases_constructor_aliases_and_reexports_resolve() {
        let (_, report) = analyze(&[
            (
                "pkg/policy.py",
                "import specification_core as core\nRULE = core.PredicateSpec(lambda c: c.ready)\n",
            ),
            ("pkg/api.py", "from .policy import RULE as READY\n"),
            (
                "app.py",
                "import pkg.api as rules\nfrom specification_core import PredicateSpec as P\nLOCAL = P(lambda c: c.ready)\ndef run(c):\n    if rules.READY.is_satisfied_by(c) or LOCAL.is_satisfied_by(c): pass\n",
            ),
        ]);
        assert_eq!(report.direct_application, 1);
        assert_eq!(report.unresolved_call, 0);
        assert_eq!(
            report.sites[0].calls[0].target.as_ref().unwrap().path,
            "pkg/policy.py"
        );
    }

    #[test]
    fn local_or_ambiguous_bindings_never_confirm_a_call() {
        for body in [
            "def run(RULE):\n    if RULE.is_satisfied_by(None): pass\n",
            "def run(c):\n    if RULE.is_satisfied_by(c): pass\n    RULE = c\n",
            "def run(c):\n    for RULE in c:\n        if RULE.is_satisfied_by(c): pass\n",
            "def run(c):\n    global RULE\n    if RULE.is_satisfied_by(c): pass\n",
            "class App:\n    if RULE.is_satisfied_by(None): pass\n",
            "RULE = None\nif RULE.is_satisfied_by(None): pass\n",
            "RULE.is_satisfied_by = lambda c: True\nif RULE.is_satisfied_by(None): pass\n",
            "setattr(RULE, 'is_satisfied_by', lambda c: True)\nif RULE.is_satisfied_by(None): pass\n",
            "del RULE.is_satisfied_by\nif RULE.is_satisfied_by(None): pass\n",
            "RULE.is_satisfied_by, other = (None, None)\nif RULE.is_satisfied_by(None): pass\n",
            "def run(c):\n    match c:\n        case RULE: pass\n    if RULE.is_satisfied_by(c): pass\n",
        ] {
            let (_, report) = analyze(&[("app.py", &format!("{POLICY}{body}"))]);
            assert_eq!(report.unresolved_call, 1, "{body}");
            assert_eq!(report.direct_application, 0, "{body}");
        }
    }

    #[test]
    fn method_globals_skip_class_namespace_but_capture_enclosing_function_bindings() {
        let text = format!(
            "{POLICY}class App:\n    RULE = None\n    def run(self, c):\n        if RULE.is_satisfied_by(c): pass\ndef outer(RULE):\n    class Nested:\n        def run(self, c):\n            if RULE.is_satisfied_by(c): pass\n"
        );
        let (_, report) = analyze(&[("app.py", &text)]);
        assert_eq!(report.direct_application, 1);
        assert_eq!(report.unresolved_call, 1);
        let (_, late) = analyze(&[
            ("pkg/__init__.py", ""),
            ("pkg/policy.py", POLICY),
            (
                "app.py",
                "import pkg as alias\nif alias.policy.RULE.is_satisfied_by(None): pass\nimport pkg.policy as later\n",
            ),
        ]);
        assert_eq!(late.unresolved_call, 1);
    }

    #[test]
    fn same_named_factories_missing_sources_cycles_and_async_are_unknown() {
        for (policy, imports) in [
            (
                "def PredicateSpec(f): return f\nRULE = PredicateSpec(lambda c: c.ready)\n",
                "from policy import RULE\n",
            ),
            (
                "from somewhere import PredicateSpec\nRULE = PredicateSpec(lambda c: c.ready)\n",
                "from policy import RULE\n",
            ),
            (
                "from specification_core import AsyncPredicateSpec\nRULE = AsyncPredicateSpec(lambda c: c.ready)\n",
                "from policy import RULE\n",
            ),
            (POLICY, "from missing import RULE\n"),
            ("from app import RULE\n", "from policy import RULE\n"),
            (POLICY, "from policy import *\n"),
        ] {
            let (_, report) = analyze(&[
                ("policy.py", policy),
                (
                    "app.py",
                    &format!("{imports}if RULE.is_satisfied_by(None): pass\n"),
                ),
            ]);
            assert_eq!(report.unresolved_call, 1, "{policy} {imports}");
            assert_eq!(report.direct_application, 0);
        }
    }

    #[test]
    fn only_the_condition_is_examined_and_unresolved_takes_precedence() {
        let text = format!(
            "{POLICY}def run(c):\n    if c.ready:\n        RULE.is_satisfied_by(c)\n    if RULE.is_satisfied_by(c):\n        if unknown.is_satisfied_by(c): pass\n    if (lambda: RULE.is_satisfied_by(c)): pass\n    if RULE.is_satisfied_by(c) and unknown.is_satisfied_by(c): pass\n"
        );
        let (_, report) = analyze(&[("app.py", &text)]);
        assert_eq!(report.analyzed_if_candidates, 5);
        assert_eq!(report.if_candidates_without_application_call, 2);
        assert_eq!(report.direct_application, 1);
        assert_eq!(report.unresolved_call, 2);
        assert_eq!(report.sites[2].calls.len(), 2);
    }

    #[test]
    fn parse_scope_and_language_limits_are_visible() {
        let (_, report) = analyze(&[
            (
                "app.py",
                &format!("{POLICY}if RULE.is_satisfied_by(None): pass\nbroken = (\n"),
            ),
            ("app.rs", "fn f() { if true {} }\n"),
        ]);
        assert!(report.provisional);
        assert!(!report.parse_issues.is_empty());
        assert_eq!(report.unresolved_call, 1);
        assert_eq!(report.unsupported_candidates, 1);
        let dir = tempdir().unwrap();
        write(dir.path(), "app.py", POLICY);
        let scan = scan::scan(dir.path(), &[]).unwrap();
        assert!(application_sites(&scan).provisional);
    }

    #[test]
    fn selected_scope_does_not_read_excluded_definition_files() {
        let dir = tempdir().unwrap();
        write(dir.path(), "policy.py", POLICY);
        write(
            dir.path(),
            "app.py",
            "from policy import RULE\nif RULE.is_satisfied_by(None): pass\n",
        );
        let scan = scan::scan(dir.path(), &["app.py".to_owned()]).unwrap();
        assert_eq!(application_sites(&scan).unresolved_call, 1);
    }

    #[test]
    fn mutations_in_the_defining_module_and_local_core_shadows_are_not_confirmed() {
        let (_, mutated) = analyze(&[
            (
                "policy.py",
                &format!("{POLICY}RULE.is_satisfied_by = lambda c: False\n"),
            ),
            (
                "app.py",
                "from policy import RULE\nif RULE.is_satisfied_by(None): pass\n",
            ),
        ]);
        assert_eq!(mutated.unresolved_call, 1);
        let (_, shadowed) = analyze(&[
            ("specification_core.py", "def PredicateSpec(f): return f\n"),
            (
                "app.py",
                &format!("{POLICY}if RULE.is_satisfied_by(None): pass\n"),
            ),
        ]);
        assert_eq!(shadowed.unresolved_call, 1);
    }

    #[test]
    fn explicit_submodule_import_works_for_regular_and_namespace_packages_only_when_loaded() {
        for initializer in [None, Some("")] {
            for (import, direct) in [
                ("import pkg.policy", true),
                ("from pkg import policy", true),
                ("import pkg", false),
            ] {
                let app = format!(
                    "{import}\nif {}.RULE.is_satisfied_by(None): pass\n",
                    if import.starts_with("from") {
                        "policy"
                    } else {
                        "pkg.policy"
                    }
                );
                let mut files = vec![("pkg/policy.py", POLICY), ("app.py", app.as_str())];
                if let Some(text) = initializer {
                    files.push(("pkg/__init__.py", text));
                }
                let (_, report) = analyze(&files);
                assert_eq!(
                    report.direct_application,
                    usize::from(direct),
                    "{initializer:?} {import}"
                );
                assert_eq!(report.unresolved_call, usize::from(!direct));
            }
        }
        for initializer in [
            "policy = None\n",
            "policy = None\npolicy = None\n",
            "if flag:\n    policy = None\n",
            "from unknown import *\n",
        ] {
            let (_, report) = analyze(&[
                ("pkg/__init__.py", initializer),
                ("pkg/policy.py", POLICY),
                (
                    "app.py",
                    "import pkg.policy\nif pkg.policy.RULE.is_satisfied_by(None): pass\n",
                ),
            ]);
            assert_eq!(report.unresolved_call, 1, "{initializer}");
        }
        let (_, report) = analyze(&[
            ("pkg/__init__.py", ""),
            ("pkg/policy.py", POLICY),
            ("src/pkg/policy.py", POLICY),
            (
                "app.py",
                "import pkg.policy\nif pkg.policy.RULE.is_satisfied_by(None): pass\n",
            ),
        ]);
        assert_eq!(report.unresolved_call, 1);
    }
}
