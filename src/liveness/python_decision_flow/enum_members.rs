//! Conservative same-module Enum member evidence; never import or evaluate Python.
use serde::Serialize;
use tree_sitter::Node;

use super::{Anchor, anchor, literal};
use crate::liveness::python_applications::{lexical_binding, mutates_object};
use crate::liveness::python_inheritance::{Binding, unique_binding};
use crate::liveness::{ParsedPythonSource, PythonLiveness};

#[derive(Serialize)]
pub(super) struct EnumMemberEvidence {
    class_name: String,
    member_name: String,
    class_anchor: Anchor,
    member_anchor: Anchor,
}

pub(super) fn resolve(
    resolver: &PythonLiveness,
    source: &ParsedPythonSource,
    operand: Node<'_>,
) -> Option<EnumMemberEvidence> {
    if operand.kind() != "attribute" {
        return None;
    }
    let text = source.source.as_bytes();
    let object = operand.child_by_field_name("object")?;
    if object.kind() != "identifier" {
        return None;
    }
    let name = object.utf8_text(text).ok()?;
    let member = operand
        .child_by_field_name("attribute")?
        .utf8_text(text)
        .ok()?;
    if member.starts_with('_')
        || lexical_binding(operand, name, &source.source)
        || mutates_object(source.tree.root_node(), name, &source.source)
        || resolver.sources.iter().any(|s| s.module == "enum")
    {
        return None;
    }
    let (position, binding) = unique_binding(source, name)?;
    if !matches!(binding, Binding::Class) || position >= operand.start_byte() {
        return None;
    }
    let mut cursor = source.tree.root_node().walk();
    let class = source
        .tree
        .root_node()
        .named_children(&mut cursor)
        .find(|n| {
            // Decorated, inherited/custom and imported classes are intentionally excluded.
            n.kind() == "class_definition" && n.start_byte() == position
        })?;
    let bases = class.child_by_field_name("superclasses")?;
    let mut cursor = bases.walk();
    let bases: Vec<_> = bases.named_children(&mut cursor).collect();
    if bases.len() != 1 || !standard_enum_base(source, bases[0], class.start_byte()) {
        return None;
    }
    let mut selected = None;
    let mut names = std::collections::HashSet::new();
    let mut cursor = class.walk();
    let body = class.child_by_field_name("body")?;
    for statement in body.named_children(&mut cursor) {
        if matches!(statement.kind(), "comment" | "pass_statement") {
            continue;
        }
        if statement.kind() != "expression_statement" {
            return None;
        }
        let expression = statement.named_child(0)?;
        if expression.kind() == "string" && literal(expression) {
            continue;
        }
        if expression.kind() != "assignment" || expression.child_by_field_name("type").is_some() {
            return None;
        }
        let left = expression.child_by_field_name("left")?;
        let right = expression.child_by_field_name("right")?;
        let field = left.utf8_text(text).ok()?;
        if left.kind() != "identifier"
            || field.starts_with('_')
            || !literal(right)
            || !names.insert(field)
        {
            return None;
        }
        if field == member {
            selected = Some(anchor(left));
        }
    }
    Some(EnumMemberEvidence {
        class_name: name.to_owned(),
        member_name: member.to_owned(),
        class_anchor: anchor(class),
        member_anchor: selected?,
    })
}

fn standard_enum_base(source: &ParsedPythonSource, base: Node<'_>, before: usize) -> bool {
    let text = source.source.as_bytes();
    let (root, qualified) = match base.kind() {
        "identifier" => (base, false),
        "attribute"
            if base
                .child_by_field_name("attribute")
                .and_then(|n| n.utf8_text(text).ok())
                == Some("Enum") =>
        {
            let Some(object) = base.child_by_field_name("object") else {
                return false;
            };
            if object.kind() != "identifier" {
                return false;
            }
            (object, true)
        }
        _ => return false,
    };
    let Ok(name) = root.utf8_text(text) else {
        return false;
    };
    if mutates_object(source.tree.root_node(), name, &source.source) {
        return false;
    }
    let Some((position, binding)) = unique_binding(source, name) else {
        return false;
    };
    position < before
        && match binding {
            Binding::Imported(module, imported) => {
                !qualified && module == "enum" && imported == "Enum"
            }
            Binding::Module(module) => qualified && module == "enum",
            _ => false,
        }
}
