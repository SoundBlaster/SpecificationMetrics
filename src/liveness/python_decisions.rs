//! Source inventory of typed decision calls, separate from Boolean-if evidence.
use clap::ValueEnum;
use serde::Serialize;
use tree_sitter::Node;

use super::python_applications::{FactoryTarget, resolved_factory};
use super::{ParsedPythonSource, PythonLiveness, PythonSource};
use crate::model::{ParseIssue, ScanReport, ScopeIssue};

#[derive(Clone, Copy, Debug, ValueEnum)]
pub enum ApplicationProfile {
    PythonIfV1,
    PythonDecisionsV1,
    PythonDecisionFlowV1,
}

#[derive(Serialize)]
pub struct DecisionReport {
    profile: &'static str,
    metric_effect: &'static str,
    counting_rule_version: u32,
    root: String,
    includes: Vec<String>,
    source_digest: String,
    scope_manifest_digest: Option<String>,
    provisional: bool,
    scope_issues: Vec<ScopeIssue>,
    parse_issues: Vec<ParseIssue>,
    marker_issues: Vec<ParseIssue>,
    analyzed_python_files: usize,
    unsupported_source_files: usize,
    examined_decide_calls: usize,
    direct_application: usize,
    mixed_expression: usize,
    unresolved_call: usize,
    pub(super) sites: Vec<DecisionSite>,
}

#[derive(Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum Category {
    DirectApplication,
    MixedExpression,
    UnresolvedCall,
}

#[derive(Serialize)]
pub(super) struct DecisionSite {
    pub(super) application_id: String,
    pub(super) path: String,
    pub(super) line: usize,
    pub(super) column: usize,
    end_line: usize,
    end_column: usize,
    receiver: String,
    method: &'static str,
    category: Category,
    pub(super) projection: Option<String>,
    consumer: &'static str,
    pub(super) bound_to: Option<String>,
    pub(super) target: Option<FactoryTarget>,
    reason: &'static str,
}

pub fn decision_applications(scan: &ScanReport) -> DecisionReport {
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
    let mut sites = Vec::new();
    for source in &resolver.sources {
        visit(
            &resolver,
            source,
            source.tree.root_node(),
            &scan.source_digest,
            &mut sites,
        );
    }
    DecisionReport {
        profile: "specification-metrics.python-decision-applications/v1",
        metric_effect: "none",
        counting_rule_version: crate::model::COUNTING_RULE_VERSION,
        root: scan.root.clone(),
        includes: scan.includes.clone(),
        source_digest: scan.source_digest.clone(),
        scope_manifest_digest: scan.scope_manifest_digest.clone(),
        provisional: scan.scope_review_required
            || !scan.parse_issues.is_empty()
            || !scan.marker_issues.is_empty(),
        scope_issues: scan.scope_issues.clone(),
        parse_issues: scan.parse_issues.clone(),
        marker_issues: scan.marker_issues.clone(),
        analyzed_python_files: resolver.sources.len(),
        unsupported_source_files: scan.sources.len() - sources.len(),
        examined_decide_calls: sites.len(),
        direct_application: sites
            .iter()
            .filter(|s| s.category == Category::DirectApplication)
            .count(),
        mixed_expression: sites
            .iter()
            .filter(|s| s.category == Category::MixedExpression)
            .count(),
        unresolved_call: sites
            .iter()
            .filter(|s| s.category == Category::UnresolvedCall)
            .count(),
        sites,
    }
}

fn visit(
    resolver: &PythonLiveness,
    source: &ParsedPythonSource,
    node: Node<'_>,
    digest: &str,
    sites: &mut Vec<DecisionSite>,
) {
    if node.kind() == "call"
        && let Some(function) = node.child_by_field_name("function")
        && function.kind() == "attribute"
        && function
            .child_by_field_name("attribute")
            .and_then(|n| n.utf8_text(source.source.as_bytes()).ok())
            == Some("decide")
        && let Some(receiver) = function.child_by_field_name("object")
    {
        let target = resolved_factory(resolver, source, node, receiver).filter(|t| {
            matches!(
                t.constructor.as_str(),
                "FirstMatch" | "FirstMatch.with_fallback"
            )
        });
        let (projection, consumer, bound_to) = consumption(node, &source.source);
        let category = if target.is_none() {
            Category::UnresolvedCall
        } else if matches!(
            consumer,
            "binding" | "return" | "argument" | "standalone" | "boolean_guard"
        ) {
            Category::DirectApplication
        } else {
            Category::MixedExpression
        };
        let reason = if target.is_none() {
            "firstmatch_binding_not_proven"
        } else {
            "resolved_static_firstmatch_binding"
        };
        let start = node.start_position();
        let end = node.end_position();
        let identity = format!(
            "python-decision/v1\0{digest}\0{}\0{}\0{}",
            source.path,
            node.start_byte(),
            node.end_byte()
        );
        sites.push(DecisionSite {
            application_id: blake3::hash(identity.as_bytes()).to_hex().to_string(),
            path: source.path.clone(),
            line: start.row + 1,
            column: start.column + 1,
            end_line: end.row + 1,
            end_column: end.column + 1,
            receiver: receiver
                .utf8_text(source.source.as_bytes())
                .unwrap_or_default()
                .to_owned(),
            method: "decide",
            category,
            projection,
            consumer,
            bound_to,
            target,
            reason,
        });
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        visit(resolver, source, child, digest, sites);
    }
}

fn consumption<'a>(
    mut node: Node<'a>,
    text: &str,
) -> (Option<String>, &'static str, Option<String>) {
    node = unwrap_parentheses(node);
    let mut projection = None;
    if let Some(parent) = node.parent()
        && parent.kind() == "attribute"
        && parent.child_by_field_name("object") == Some(node)
    {
        let attribute = parent
            .child_by_field_name("attribute")
            .and_then(|n| n.utf8_text(text.as_bytes()).ok());
        if matches!(attribute, Some("value" | "matched")) {
            projection = attribute.map(str::to_owned);
            node = unwrap_parentheses(parent);
        }
    }
    let Some(parent) = node.parent() else {
        return (projection, "embedded", None);
    };
    let consumer = match parent.kind() {
        "assignment" if parent.child_by_field_name("right") == Some(node) => "binding",
        "return_statement" => "return",
        "argument_list" | "keyword_argument" => "argument",
        "expression_statement" => "standalone",
        "if_statement"
            if projection.as_deref() == Some("matched")
                && parent.child_by_field_name("condition") == Some(node) =>
        {
            "boolean_guard"
        }
        _ => "embedded",
    };
    let bound_to = if consumer == "binding" {
        parent
            .child_by_field_name("left")
            .filter(|n| n.kind() == "identifier")
            .and_then(|n| n.utf8_text(text.as_bytes()).ok())
            .map(str::to_owned)
    } else {
        None
    };
    (projection, consumer, bound_to)
}

fn unwrap_parentheses(mut node: Node<'_>) -> Node<'_> {
    while let Some(parent) = node.parent()
        && parent.kind() == "parenthesized_expression"
    {
        node = parent;
    }
    node
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{live, scan};
    use std::fs;

    const POLICY: &str =
        "from specification_core import FirstMatch\nRULE = FirstMatch.with_fallback((), 'ready')\n";
    fn analyze(policy: &str, app: &str) -> (ScanReport, DecisionReport) {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join("policy.py"), policy).unwrap();
        fs::write(dir.path().join("app.py"), app).unwrap();
        let scan = scan::scan(dir.path(), &[]).unwrap();
        let report = decision_applications(&scan);
        (scan, report)
    }

    #[test]
    fn resolves_real_pilot_shapes_without_inventing_branch_dataflow() {
        let (scan, r) = analyze(
            POLICY,
            "from policy import RULE\ndef run(c):\n    result = RULE.decide(c).value\n    if result: pass\n    return wrap(RULE.decide(c).value)\n",
        );
        assert_eq!(r.direct_application, 2);
        assert_eq!(r.sites[0].bound_to.as_deref(), Some("result"));
        assert_eq!(r.sites[0].projection.as_deref(), Some("value"));
        assert_eq!(r.sites[1].consumer, "argument");
        assert_eq!(
            r.sites[0].target.as_ref().unwrap().constructor,
            "FirstMatch.with_fallback"
        );
        assert_eq!(
            live::measure(&scan, None).unwrap().remaining_opportunities,
            1
        );
        assert!(r.provisional); // No reviewed manifest in this fixture.
    }

    #[test]
    fn separates_result_consumption_from_embedded_logic() {
        let (_, r) = analyze(
            POLICY,
            "from policy import RULE\ndef run(c):\n    a = RULE.decide(c)\n    b = (RULE.decide(c)).matched\n    c = RULE.decide(c).value if c.ready else None\n    if RULE.decide(c).value == 'ready': pass\n    if RULE.decide(c): pass\n    d = RULE.decide(c).other\n",
        );
        assert_eq!(r.direct_application, 2);
        assert_eq!(r.mixed_expression, 4);
        assert_eq!(r.sites[1].projection.as_deref(), Some("matched"));
        let (_, guard) = analyze(
            POLICY,
            "from policy import RULE\nif RULE.decide(None).matched: pass\n",
        );
        assert_eq!(guard.direct_application, 1);
    }

    #[test]
    fn supports_constructor_and_module_aliases_and_rejects_mismatched_methods() {
        let (_, r) = analyze(
            "import specification_core as core\nRULE = core.FirstMatch(())\n",
            "import policy as p\ndef run(c):\n    return p.RULE.decide(c)\n",
        );
        assert_eq!(r.direct_application, 1);
        let (scan, r) = analyze(
            "from specification_core import PredicateSpec\nRULE = PredicateSpec(lambda c: True)\n",
            "from policy import RULE\nx = RULE.decide(None)\n",
        );
        assert_eq!(r.unresolved_call, 1);
        assert_eq!(
            serde_json::to_value(super::super::python_applications::application_sites(&scan))
                .unwrap()["sites"],
            serde_json::json!([])
        );
    }

    #[test]
    fn aliases_reexports_shadowing_cycles_and_deferred_scopes_stay_conservative() {
        for policy in [
            "class FirstMatch: pass\nRULE = FirstMatch()\n",
            "from other import FirstMatch\nRULE = FirstMatch(())\n",
            "from specification_core import AsyncFirstMatch\nRULE = AsyncFirstMatch(())\n",
            "RULE = RULE.with_fallback((), 0)\n",
        ] {
            assert_eq!(
                analyze(policy, "from policy import RULE\nx = RULE.decide(None)\n")
                    .1
                    .unresolved_call,
                1
            );
        }
        for app in [
            "from policy import RULE\ndef run(RULE):\n    return RULE.decide(None)\n",
            "from policy import RULE\nx = [RULE.decide(None) for RULE in items]\n",
            "from policy import RULE\nx = lambda: RULE.decide(None)\n",
            "from policy import RULE\nRULE.decide = lambda c: 0\nx = RULE.decide(None)\n",
        ] {
            assert_eq!(analyze(POLICY, app).1.unresolved_call, 1);
        }
    }

    #[test]
    fn malformed_sources_and_application_ids_are_snapshot_bound() {
        let (_, r) = analyze(
            POLICY,
            "from policy import RULE\nx = RULE.decide(None)\nbroken = (\n",
        );
        assert!(r.provisional);
        assert_eq!(r.unresolved_call, 1);
        let (_, first) = analyze(POLICY, "from policy import RULE\nx = RULE.decide(None)\n");
        let (_, second) = analyze(
            POLICY,
            "from policy import RULE\nx = RULE.decide(None)\n# change\n",
        );
        assert_ne!(
            first.sites[0].application_id,
            second.sites[0].application_id
        );
    }

    #[test]
    fn explicit_reexports_and_file_scope_preserve_resolution_boundaries() {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir(dir.path().join("pkg")).unwrap();
        fs::write(dir.path().join("pkg/policy.py"), POLICY).unwrap();
        fs::write(
            dir.path().join("pkg/__init__.py"),
            "from .policy import RULE as READY\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("app.py"),
            "from pkg import READY\nx = READY.decide(None).value\n",
        )
        .unwrap();
        let scan = scan::scan(dir.path(), &[]).unwrap();
        assert_eq!(decision_applications(&scan).direct_application, 1);
        let narrow = scan::scan(dir.path(), &["app.py".to_owned()]).unwrap();
        assert_eq!(decision_applications(&narrow).unresolved_call, 1);
        fs::write(
            dir.path().join("app.py"),
            "from pkg import READY\nif READY.is_satisfied_by(None): pass\n",
        )
        .unwrap();
        let scan = scan::scan(dir.path(), &[]).unwrap();
        let old = serde_json::to_value(super::super::python_applications::application_sites(&scan))
            .unwrap();
        assert_eq!(old["direct_application"], 0);
        assert_eq!(old["unresolved_call"], 1);
    }

    #[test]
    fn nonstandard_import_root_must_be_selected_explicitly() {
        let dir = tempfile::tempdir().unwrap();
        let tools = dir.path().join("tools");
        fs::create_dir(&tools).unwrap();
        fs::write(tools.join("policy.py"), POLICY).unwrap();
        fs::write(
            tools.join("app.py"),
            "from policy import RULE\nx = RULE.decide(None)\n",
        )
        .unwrap();
        let project = scan::scan(dir.path(), &[]).unwrap();
        assert_eq!(decision_applications(&project).unresolved_call, 1);
        let import_root = scan::scan(&tools, &[]).unwrap();
        assert_eq!(decision_applications(&import_root).direct_application, 1);
        assert_ne!(project.source_digest, import_root.source_digest);
    }
}
