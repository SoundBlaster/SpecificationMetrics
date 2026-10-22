//! Bounded local def/use evidence. No CFG joins, alias propagation or U exclusion.
use serde::Serialize;
use tree_sitter::Node;

use super::python_decisions::{DecisionReport, DecisionSite, decision_applications};
use super::{PythonLiveness, PythonSource};
use crate::model::ScanReport;

#[derive(Serialize)]
pub struct FlowReport {
    profile: &'static str,
    metric_effect: &'static str,
    applications: DecisionReport,
    examined_bindings: usize,
    linked_bindings: usize,
    unresolved_bindings: usize,
    not_linked_bindings: usize,
    bindings: Vec<BindingFlow>,
}

#[derive(Serialize)]
struct BindingFlow {
    application_id: String,
    path: String,
    variable: String,
    origin_projection: Option<String>,
    status: &'static str,
    reason: &'static str,
    stop: Option<Anchor>,
    branch: Option<BranchUse>,
}

#[derive(Serialize)]
struct Anchor {
    line: usize,
    column: usize,
    syntax_kind: String,
}

#[derive(Serialize)]
struct BranchUse {
    anchor: Anchor,
    candidate_fingerprint: Option<String>,
    condition: String,
    reference_projection: String,
}

pub fn decision_flow(scan: &ScanReport) -> FlowReport {
    let applications = decision_applications(scan);
    let sources: Vec<_> = scan
        .sources
        .iter()
        .filter(|s| s.path.ends_with(".py"))
        .filter_map(|s| {
            String::from_utf8(s.bytes.clone())
                .ok()
                .map(|source| PythonSource {
                    path: s.path.clone(),
                    source,
                })
        })
        .collect();
    let resolver = PythonLiveness::new(&sources, &scan.specifications);
    let bindings: Vec<_> = applications
        .sites
        .iter()
        .filter_map(|site| {
            let name = site.bound_to.as_ref()?;
            let mut result = BindingFlow {
                application_id: site.application_id.clone(),
                path: site.path.clone(),
                variable: name.clone(),
                origin_projection: site.projection.clone(),
                status: "unresolved",
                reason: "origin_binding_not_proven",
                stop: None,
                branch: None,
            };
            if site.target.is_some()
                && let Some(source) = resolver.sources.iter().find(|s| s.path == site.path)
            {
                trace(
                    scan,
                    site,
                    source.tree.root_node(),
                    &source.source,
                    &mut result,
                );
            }
            Some(result)
        })
        .collect();
    FlowReport {
        profile: "specification-metrics.python-decision-flow/v1",
        metric_effect: "none",
        examined_bindings: bindings.len(),
        linked_bindings: bindings.iter().filter(|b| b.status == "linked").count(),
        unresolved_bindings: bindings.iter().filter(|b| b.status == "unresolved").count(),
        not_linked_bindings: bindings.iter().filter(|b| b.status == "not_linked").count(),
        applications,
        bindings,
    }
}

fn anchor(node: Node<'_>) -> Anchor {
    let p = node.start_position();
    Anchor {
        line: p.row + 1,
        column: p.column + 1,
        syntax_kind: node.kind().to_owned(),
    }
}

fn origin<'a>(node: Node<'a>, site: &DecisionSite) -> Option<Node<'a>> {
    let p = node.start_position();
    if node.kind() == "call" && p.row + 1 == site.line && p.column + 1 == site.column {
        return Some(node);
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .find_map(|child| origin(child, site))
}

fn trace(
    scan: &ScanReport,
    site: &DecisionSite,
    root: Node<'_>,
    text: &str,
    result: &mut BindingFlow,
) {
    let Some(mut node) = origin(root, site) else {
        result.reason = "origin_anchor_unavailable";
        return;
    };
    while node.kind() != "assignment" {
        let Some(parent) = node.parent() else {
            result.reason = "assignment_unavailable";
            return;
        };
        node = parent;
    }
    let Some(statement) = node.parent().filter(|n| n.kind() == "expression_statement") else {
        result.reason = "assignment_shape_unsupported";
        return;
    };
    let Some(block) = statement.parent().filter(|n| n.kind() == "block") else {
        result.reason = "function_body_required";
        return;
    };
    if block
        .parent()
        .is_none_or(|n| n.kind() != "function_definition")
    {
        result.reason = "straight_line_function_body_required";
        return;
    }
    if contains_scope_directive(block) {
        result.reason = "global_or_nonlocal_scope";
        return;
    }
    let mut cursor = block.walk();
    for next in block
        .named_children(&mut cursor)
        .filter(|n| n.start_byte() > statement.start_byte())
    {
        result.stop = Some(anchor(next));
        match next.kind() {
            "comment" | "pass_statement" => continue,
            "if_statement" => {
                let Some(condition) = next.child_by_field_name("condition") else {
                    result.reason = "condition_unavailable";
                    return;
                };
                let Some(projection) = condition_reference(
                    condition,
                    &result.variable,
                    site.projection.as_deref(),
                    text,
                ) else {
                    result.reason = "condition_or_control_flow_unsupported";
                    return;
                };
                let p = next.start_position();
                let fingerprint = scan
                    .candidates
                    .iter()
                    .find(|c| {
                        c.path == site.path
                            && c.kind == "if"
                            && c.line == p.row + 1
                            && c.column == p.column + 1
                    })
                    .map(|c| c.fingerprint.clone());
                result.status = "linked";
                result.reason = "local_straight_line_read";
                result.branch = Some(BranchUse {
                    anchor: anchor(next),
                    candidate_fingerprint: fingerprint,
                    condition: condition
                        .utf8_text(text.as_bytes())
                        .unwrap_or_default()
                        .to_owned(),
                    reference_projection: projection,
                });
                return;
            }
            "expression_statement" => {
                let Some(expression) = next.named_child(0) else {
                    result.reason = "statement_unavailable";
                    return;
                };
                if matches!(expression.kind(), "assignment" | "augmented_assignment") {
                    if expression
                        .child_by_field_name("left")
                        .is_some_and(|n| target_mentions(n, &result.variable, text))
                    {
                        result.status = "not_linked";
                        result.reason = "binding_reassigned_or_mutated";
                        return;
                    }
                    if expression.kind() == "assignment"
                        && expression
                            .child_by_field_name("left")
                            .is_some_and(|n| n.kind() == "identifier")
                        && expression.child_by_field_name("type").is_none()
                        && expression.child_by_field_name("right").is_some_and(literal)
                    {
                        continue;
                    }
                }
                if literal(expression) {
                    continue;
                }
                result.reason = "intervening_expression_barrier";
                return;
            }
            "delete_statement" if target_mentions(next, &result.variable, text) => {
                result.status = "not_linked";
                result.reason = "binding_deleted";
                return;
            }
            _ => {
                result.reason = "control_flow_or_effect_barrier";
                return;
            }
        }
    }
    result.status = "not_linked";
    result.reason = "no_supported_branch_before_scope_end";
    result.stop = None;
}

fn target_mentions(node: Node<'_>, name: &str, text: &str) -> bool {
    match node.kind() {
        "identifier" => return node.utf8_text(text.as_bytes()).ok() == Some(name),
        "attribute" => {
            return node
                .child_by_field_name("object")
                .is_some_and(|n| target_mentions(n, name, text));
        }
        "subscript" => {
            return node
                .child_by_field_name("value")
                .is_some_and(|n| target_mentions(n, name, text));
        }
        _ => {}
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|n| target_mentions(n, name, text))
}

fn contains_scope_directive(node: Node<'_>) -> bool {
    if matches!(node.kind(), "global_statement" | "nonlocal_statement") {
        return true;
    }
    // A nested definition is not this function's scope declaration.
    if matches!(
        node.kind(),
        "function_definition" | "class_definition" | "lambda"
    ) {
        return false;
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(contains_scope_directive)
}

fn literal(node: Node<'_>) -> bool {
    match node.kind() {
        "integer" | "float" | "true" | "false" | "none" => true,
        "string" => {
            let mut cursor = node.walk();
            !node
                .named_children(&mut cursor)
                .any(|n| n.kind() == "interpolation")
        }
        _ => false,
    }
}

fn reference(node: Node<'_>, name: &str, projection: Option<&str>, text: &str) -> Option<String> {
    if node.kind() == "identifier" && node.utf8_text(text.as_bytes()).ok() == Some(name) {
        return projection.map(str::to_owned);
    }
    if projection.is_none()
        && node.kind() == "attribute"
        && node.child_by_field_name("object").is_some_and(|n| {
            n.kind() == "identifier" && n.utf8_text(text.as_bytes()).ok() == Some(name)
        })
    {
        let field = node
            .child_by_field_name("attribute")?
            .utf8_text(text.as_bytes())
            .ok()?;
        if matches!(field, "value" | "matched") {
            return Some(field.to_owned());
        }
    }
    None
}

fn condition_reference(
    node: Node<'_>,
    name: &str,
    projection: Option<&str>,
    text: &str,
) -> Option<String> {
    if let Some(reference) = reference(node, name, projection, text) {
        return Some(reference);
    }
    if matches!(node.kind(), "parenthesized_expression" | "not_operator") {
        return condition_reference(node.named_child(0)?, name, projection, text);
    }
    if node.kind() == "comparison_operator" {
        let mut found = None;
        let mut cursor = node.walk();
        for operand in node.named_children(&mut cursor) {
            if let Some(value) = reference(operand, name, projection, text) {
                if found.is_some() {
                    return None;
                }
                found = Some(value);
            } else if !literal(operand) {
                return None;
            }
        }
        return found;
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scan;
    use std::fs;

    fn analyze(body: &str) -> FlowReport {
        let dir = tempfile::tempdir().unwrap();
        let source = format!(
            "from specification_core import FirstMatch\nRULE = FirstMatch.with_fallback((), 'ok')\n{body}"
        );
        fs::write(dir.path().join("app.py"), source).unwrap();
        decision_flow(&scan::scan(dir.path(), &[]).unwrap())
    }

    #[test]
    fn links_value_matched_and_raw_result_projections() {
        for (origin, condition, projection) in [
            (".value", "value", "value"),
            (".matched", "not value", "matched"),
            ("", "value.matched", "matched"),
            ("", "value.value == 'ok'", "value"),
            (".value", "value is not None", "value"),
        ] {
            let r = analyze(&format!(
                "def run(c):\n    value = RULE.decide(c){origin}\n    ignored = 1\n    if {condition}: pass\n"
            ));
            assert_eq!(r.linked_bindings, 1, "{origin} {condition}");
            let branch = r.bindings[0].branch.as_ref().unwrap();
            assert_eq!(branch.reference_projection, projection);
            assert!(branch.candidate_fingerprint.is_some());
        }
    }

    #[test]
    fn overwrites_delete_and_attribute_mutation_invalidate_the_origin() {
        for statement in [
            "value = None",
            "value += 1",
            "del value",
            "value.field = None",
        ] {
            let r = analyze(&format!(
                "def run(c):\n    value = RULE.decide(c).value\n    {statement}\n    if value: pass\n"
            ));
            assert_eq!(r.linked_bindings, 0, "{statement}");
            assert_eq!(r.not_linked_bindings, 1, "{statement}");
        }
        let r = analyze(
            "def run(c):\n    value = RULE.decide(c).value\n    value = RULE.decide(c).value\n    if value: pass\n",
        );
        assert_eq!(r.not_linked_bindings, 1);
        assert_eq!(r.linked_bindings, 1);
    }

    #[test]
    fn barriers_and_unsupported_conditions_never_create_links() {
        for statement in [
            "log(value)",
            "alias = value",
            "if c.ready: pass",
            "for x in c: pass",
            "return value",
            "def nested(): pass",
            "with c: pass",
            "assert value",
            "context.value = None",
            "del context.value",
        ] {
            let r = analyze(&format!(
                "def run(c):\n    value = RULE.decide(c).value\n    {statement}\n    if value: pass\n"
            ));
            assert_eq!(r.unresolved_bindings, 1, "{statement}");
            assert_eq!(r.linked_bindings, 0);
        }
        for condition in [
            "value and c.ready",
            "check(value)",
            "(value := False)",
            "value == other",
            "(lambda value: value)(c)",
        ] {
            let r = analyze(&format!(
                "def run(c):\n    value = RULE.decide(c).value\n    if {condition}: pass\n"
            ));
            assert_eq!(r.unresolved_bindings, 1, "{condition}");
        }
    }

    #[test]
    fn scopes_unknown_origins_raw_truthiness_and_missing_uses_remain_explicit() {
        for body in [
            "value = RULE.decide(None).value\nif value: pass\n",
            "def run(c):\n    if c:\n        value = RULE.decide(c).value\n        if value: pass\n",
            "def run(c):\n    global value\n    value = RULE.decide(c).value\n    if value: pass\n",
            "def run(RULE):\n    value = RULE.decide(None).value\n    if value: pass\n",
            "def run(c):\n    value = RULE.decide(c)\n    if value: pass\n",
        ] {
            let r = analyze(body);
            assert_eq!(r.unresolved_bindings, 1, "{body}");
        }
        let r = analyze("def run(c):\n    value = RULE.decide(c).value\n");
        assert_eq!(r.not_linked_bindings, 1);
    }
}
