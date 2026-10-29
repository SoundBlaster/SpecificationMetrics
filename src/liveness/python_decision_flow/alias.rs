//! Bounded name provenance for a single decision origin.
use super::*;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Serialize)]
#[serde(rename_all = "lowercase")]
enum State {
    Origin,
    Other,
    Deleted,
}

#[derive(Serialize)]
pub(super) struct Evidence {
    contract: &'static str,
    origin_token: String,
    origin_projection: String,
    limits: Limits,
    visited_nodes: usize,
    states: BTreeMap<String, State>,
    events: Vec<Event>,
    consumer_reference: Option<Consumer>,
}
#[derive(Serialize)]
struct Limits {
    max_tracked_names: usize,
    max_following_named_sibling_nodes: usize,
}
#[derive(Serialize)]
struct Event {
    kind: &'static str,
    anchor: Anchor,
    source: Option<String>,
    target: String,
    before: BTreeMap<String, Option<State>>,
    after: BTreeMap<String, State>,
}
#[derive(Serialize)]
struct Consumer {
    name: String,
    state: State,
    projection: String,
    anchor: Anchor,
}

fn has_object_target(node: Node<'_>) -> bool {
    if matches!(node.kind(), "attribute" | "subscript") {
        return true;
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor).any(has_object_target)
}

fn record(
    e: &mut Evidence,
    kind: &'static str,
    node: Node<'_>,
    target: &str,
    source: Option<&str>,
    state: State,
) {
    let mut before = BTreeMap::new();
    before.insert(target.to_owned(), e.states.get(target).copied());
    if let Some(source) = source {
        before.insert(source.to_owned(), e.states.get(source).copied());
    }
    e.states.insert(target.to_owned(), state);
    let mut after = BTreeMap::new();
    after.insert(target.to_owned(), state);
    e.events.push(Event {
        kind,
        anchor: anchor(node),
        source: source.map(str::to_owned),
        target: target.to_owned(),
        before,
        after,
    });
}

pub(super) fn trace(
    scan: &ScanReport,
    site: &DecisionSite,
    source: &ParsedPythonSource,
    resolver: &PythonLiveness,
    result: &mut BindingFlow,
) {
    let mut states = BTreeMap::new();
    states.insert(result.variable.clone(), State::Origin);
    let mut e = Evidence {
        contract: "specification-metrics.local-alias-flow-contract/v1-draft",
        origin_token: site.application_id.clone(),
        origin_projection: site.projection.clone().unwrap_or_else(|| "raw".to_owned()),
        limits: Limits {
            max_tracked_names: 8,
            max_following_named_sibling_nodes: 64,
        },
        visited_nodes: 0,
        states,
        events: Vec::new(),
        consumer_reference: None,
    };
    trace_inner(scan, site, source, resolver, result, &mut e);
    result.alias_flow = Some(e);
}

fn trace_inner(
    scan: &ScanReport,
    site: &DecisionSite,
    source: &ParsedPythonSource,
    resolver: &PythonLiveness,
    result: &mut BindingFlow,
    e: &mut Evidence,
) {
    let text = &source.source;
    let Some(mut node) = origin(source.tree.root_node(), site) else {
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
    let Some((function_body, loops)) = straight_line_scope(block) else {
        result.reason = "straight_line_function_body_required";
        return;
    };
    if contains_scope_directive(function_body) {
        result.reason = "global_or_nonlocal_scope";
        return;
    }
    let mut cursor = block.walk();
    for next in block
        .named_children(&mut cursor)
        .filter(|n| n.start_byte() > statement.start_byte())
    {
        result.stop = Some(anchor(next));
        e.visited_nodes += 1;
        if e.visited_nodes > 64 {
            result.reason = "statement_limit";
            return;
        }
        match next.kind() {
            "comment" | "pass_statement" => continue,
            "if_statement" => {
                let Some(condition) = next.child_by_field_name("condition") else {
                    result.reason = "condition_unavailable";
                    return;
                };
                let found: Vec<_> = e
                    .states
                    .iter()
                    .filter_map(|(name, state)| {
                        condition_reference(
                            condition,
                            name,
                            site.projection.as_deref(),
                            source,
                            resolver,
                        )
                        .map(|read| (name.clone(), *state, read))
                    })
                    .collect();
                if found.len() != 1 {
                    result.reason = "condition_or_control_flow_unsupported";
                    return;
                }
                let (name, state, read) = found.into_iter().next().unwrap();
                e.consumer_reference = Some(Consumer {
                    name,
                    state,
                    projection: read.projection.clone(),
                    anchor: anchor(next),
                });
                match state {
                    State::Other => {
                        result.status = "not_linked";
                        result.reason = "branch_reference_rebound";
                    }
                    State::Deleted => {
                        result.status = "not_linked";
                        result.reason = "branch_reference_deleted";
                    }
                    State::Origin => {
                        result.status = "linked";
                        result.reason = "local_alias_read";
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
                        result.branch = Some(BranchUse {
                            anchor: anchor(next),
                            candidate_fingerprint: fingerprint,
                            condition: condition
                                .utf8_text(text.as_bytes())
                                .unwrap_or_default()
                                .to_owned(),
                            reference_projection: read.projection,
                            enum_member: read.enum_member,
                            loop_anchors: loops,
                        });
                    }
                }
                return;
            }
            "expression_statement" => {
                let Some(expr) = next.named_child(0) else {
                    result.reason = "statement_unavailable";
                    return;
                };
                if expr.kind() == "augmented_assignment" {
                    result.reason = "object_mutation_barrier";
                    return;
                }
                if expr.kind() != "assignment" {
                    result.reason = "intervening_expression_barrier";
                    return;
                }
                let Some(left) = expr.child_by_field_name("left") else {
                    result.reason = "intervening_expression_barrier";
                    return;
                };
                if has_object_target(left) {
                    result.reason = "object_mutation_barrier";
                    return;
                }
                if left.kind() != "identifier" {
                    result.reason = "intervening_expression_barrier";
                    return;
                }
                let target = left.utf8_text(text.as_bytes()).unwrap_or_default();
                let right = expr.child_by_field_name("right");
                if expr.child_by_field_name("type").is_some() {
                    if right.is_none() {
                        continue;
                    }
                    result.reason = "intervening_expression_barrier";
                    return;
                }
                let Some(right) = right else {
                    result.reason = "intervening_expression_barrier";
                    return;
                };
                if right.kind() == "identifier" {
                    let from = right.utf8_text(text.as_bytes()).unwrap_or_default();
                    let Some(state) = e.states.get(from).copied() else {
                        result.reason = "intervening_expression_barrier";
                        return;
                    };
                    if matches!(state, State::Deleted) {
                        result.reason = "alias_copy_source_deleted";
                        return;
                    }
                    if !e.states.contains_key(target) && e.states.len() >= 8 {
                        result.reason = "alias_name_limit";
                        return;
                    }
                    record(e, "copy", next, target, Some(from), state);
                    continue;
                }
                if literal(right) {
                    if e.states.contains_key(target) {
                        record(e, "literal", next, target, None, State::Other);
                    }
                    continue;
                }
                result.reason = "intervening_expression_barrier";
                return;
            }
            "delete_statement" => {
                let Some(target) = next.named_child(0) else {
                    result.reason = "deletion_state_unproven";
                    return;
                };
                if has_object_target(target) {
                    result.reason = "object_mutation_barrier";
                    return;
                }
                if target.kind() != "identifier" || next.named_child_count() != 1 {
                    result.reason = "intervening_expression_barrier";
                    return;
                }
                let name = target.utf8_text(text.as_bytes()).unwrap_or_default();
                if !matches!(e.states.get(name), Some(State::Origin | State::Other)) {
                    result.reason = "deletion_state_unproven";
                    return;
                }
                record(e, "delete", next, name, None, State::Deleted);
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scan;

    #[test]
    fn inline_comment_after_origin_counts_towards_limit() {
        for (passes, expected) in [(62, "local_alias_read"), (63, "statement_limit")] {
            let dir = tempfile::tempdir().unwrap();
            let code = format!(
                "from specification_core import FirstMatch\nRULE = FirstMatch.with_fallback((), 'ok')\ndef run(c):\n    d = RULE.decide(c).value # comment\n{}    if d: pass\n",
                "    pass\n".repeat(passes)
            );
            std::fs::write(dir.path().join("app.py"), code).unwrap();
            let report = decision_flow_alias(&scan::scan(dir.path(), &[]).unwrap());
            assert_eq!(report.bindings[0].reason, expected);
        }
    }

    #[test]
    fn frozen_contract_matrix() {
        let matrix: serde_json::Value =
            serde_json::from_str(include_str!("../../../docs/local-alias-flow-cases.json"))
                .unwrap();
        let mut failures = Vec::new();
        for case in matrix["unit_cases"].as_array().unwrap() {
            let dir = tempfile::tempdir().unwrap();
            let code = format!(
                "from specification_core import FirstMatch\nRULE = FirstMatch.with_fallback((), 'ok')\n{}",
                case["code"].as_str().unwrap()
            );
            std::fs::write(dir.path().join("app.py"), code).unwrap();
            let scan = scan::scan(dir.path(), &[]).unwrap();
            let report = decision_flow_alias(&scan);
            let mut actual = serde_json::to_value(&report.bindings[0]).unwrap();
            if actual["reason"] == "origin_binding_not_proven" {
                assert_eq!(case["id"], "scope.global", "unexpected unresolved factory");
                let applications = decision_applications(&scan);
                let site = &applications.sites[0];
                let sources = vec![PythonSource {
                    path: "app.py".into(),
                    source: std::fs::read_to_string(dir.path().join("app.py")).unwrap(),
                }];
                let resolver = PythonLiveness::new(&sources, &scan.specifications);
                let mut binding = BindingFlow {
                    application_id: site.application_id.clone(),
                    path: site.path.clone(),
                    variable: site.bound_to.clone().unwrap(),
                    origin_projection: site.projection.clone(),
                    status: "unresolved",
                    reason: "origin_binding_not_proven",
                    stop: None,
                    branch: None,
                    alias_flow: None,
                };
                trace(&scan, site, &resolver.sources[0], &resolver, &mut binding);
                actual = serde_json::to_value(binding).unwrap();
            }
            let expected = &case["expected"];
            let mut stop = expected["stop"].clone();
            if let Some(line) = stop.get_mut("line") {
                *line = serde_json::json!(line.as_u64().unwrap() + 2);
            }
            let consumer = &actual["alias_flow"]["consumer_reference"];
            let reference = if consumer.is_null() {
                serde_json::Value::Null
            } else {
                serde_json::json!({"name":consumer["name"], "state":consumer["state"]})
            };
            if actual["status"] != expected["status"]
                || actual["reason"] != expected["reason"]
                || actual["stop"] != stop
                || reference != expected["reference"]
            {
                failures.push(format!(
                    "{}: expected {}, actual {}",
                    case["id"], expected, actual
                ));
            }
        }
        assert!(failures.is_empty(), "{}", failures.join("\n"));
    }
}
