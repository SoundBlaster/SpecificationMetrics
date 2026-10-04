//! Conservative structural matching. Only registered identifier binders vary.
use std::collections::{BTreeMap, BTreeSet};

use anyhow::{Context, Result, ensure};
use tree_sitter::{Node, Parser, Tree};

#[derive(Clone, Debug, Eq, PartialEq)]
pub(super) struct Expr {
    kind: String,
    text: Option<String>,
    children: Vec<Expr>,
}

pub(super) fn parse(source: &str) -> Result<Tree> {
    let mut parser = Parser::new();
    parser.set_language(&tree_sitter_python::LANGUAGE.into())?;
    let tree = parser.parse(source, None).expect("parser has no timeout");
    ensure!(!tree.root_node().has_error(), "Python parse error");
    Ok(tree)
}

pub(super) fn text<'a>(node: Node<'_>, source: &'a str) -> &'a str {
    &source[node.byte_range()]
}

fn children(node: Node<'_>) -> Vec<Node<'_>> {
    let mut cursor = node.walk();
    node.children(&mut cursor)
        .filter(|n| n.kind() != "comment")
        .collect()
}

pub(super) fn expression(node: Node<'_>, source: &str) -> Expr {
    let nodes = children(node);
    if node.kind() == "parenthesized_expression" {
        let mut cursor = node.walk();
        let named: Vec<_> = node
            .named_children(&mut cursor)
            .filter(|n| n.kind() != "comment")
            .collect();
        if named.len() == 1 {
            return expression(named[0], source);
        }
    }
    if node.kind() == "string" {
        let raw = text(node, source);
        // Ordinary unescaped string literals only; f/byte/raw/triple strings remain exact.
        if raw.len() >= 2
            && (raw.starts_with('\'') || raw.starts_with('"'))
            && raw.as_bytes().first() == raw.as_bytes().last()
            && !raw[1..raw.len() - 1].contains(['\\', '\n', '\r'])
            && !raw.starts_with("\"\"\"")
            && !raw.starts_with("'''")
        {
            return Expr {
                kind: "string_value".into(),
                text: Some(raw[1..raw.len() - 1].into()),
                children: vec![],
            };
        }
    }
    let is_attribute = node.parent().is_some_and(|p| {
        p.kind() == "attribute" && p.child_by_field_name("attribute") == Some(node)
    });
    Expr {
        kind: if is_attribute {
            "attribute_name".into()
        } else {
            node.kind().into()
        },
        text: nodes.is_empty().then(|| text(node, source).to_owned()),
        children: nodes.into_iter().map(|n| expression(n, source)).collect(),
    }
}

pub(super) fn template(source: &str) -> Result<Expr> {
    let wrapped = format!("__rule__ = ({source})\n");
    let tree = parse(&wrapped)?;
    let statement = tree.root_node().named_child(0).expect("assignment");
    let assignment = statement.named_child(0).expect("assignment");
    let value = assignment.child_by_field_name("right").expect("right");
    Ok(expression(value, &wrapped))
}

pub(super) fn matches(pattern: &Expr, actual: &Expr, binders: &[String]) -> bool {
    fn visit(
        p: &Expr,
        a: &Expr,
        binders: &[String],
        captures: &mut BTreeMap<String, String>,
    ) -> bool {
        if p.kind == "identifier" && p.text.as_ref().is_some_and(|s| binders.contains(s)) {
            if a.kind != "identifier" {
                return false;
            }
            let key = p.text.as_ref().unwrap();
            let value = a.text.as_ref().unwrap();
            if let Some(previous) = captures.get(key) {
                return previous == value;
            }
            if captures.values().any(|v| v == value) {
                return false;
            }
            captures.insert(key.clone(), value.clone());
            return true;
        }
        p.kind == a.kind
            && p.text == a.text
            && p.children.len() == a.children.len()
            && p.children
                .iter()
                .zip(&a.children)
                .all(|(p, a)| visit(p, a, binders, captures))
    }
    visit(pattern, actual, binders, &mut BTreeMap::new())
}

pub(super) fn features(expr: &Expr) -> BTreeSet<String> {
    let mut result = BTreeSet::new();
    fn walk(e: &Expr, out: &mut BTreeSet<String>) {
        if matches!(e.kind.as_str(), "attribute_name" | "string_value")
            && let Some(text) = &e.text
        {
            out.insert(text.clone());
        }
        for child in &e.children {
            walk(child, out);
        }
    }
    walk(expr, &mut result);
    result
}

pub(super) fn similarity(a: &Expr, b: &Expr) -> bool {
    let a = features(a);
    let b = features(b);
    let common = a.intersection(&b).count();
    common >= 3 && common * 2 >= a.union(&b).count()
}

pub(super) fn declaration<'a>(tree: &'a Tree, source: &str, symbol: &str) -> Result<Node<'a>> {
    let mut cursor = tree.root_node().walk();
    for node in tree.root_node().named_children(&mut cursor) {
        let inner = if node.kind() == "expression_statement" {
            node.named_child(0).unwrap_or(node)
        } else {
            node
        };
        let name = inner
            .child_by_field_name("name")
            .or_else(|| inner.child_by_field_name("left"));
        if name.is_some_and(|n| text(n, source) == symbol) {
            return Ok(node);
        }
    }
    anyhow::bail!("canonical declaration not found: {symbol}")
}

#[derive(Debug)]
pub(super) struct Site {
    pub line: usize,
    pub code: String,
    pub expr: Expr,
    pub kind: &'static str,
}

pub(super) fn sites(
    tree: &Tree,
    source: &str,
    excluded: Option<std::ops::Range<usize>>,
) -> Vec<Site> {
    fn walk(
        node: Node<'_>,
        source: &str,
        excluded: &Option<std::ops::Range<usize>>,
        out: &mut Vec<Site>,
    ) {
        if excluded
            .as_ref()
            .is_some_and(|span| span.start <= node.start_byte() && node.end_byte() <= span.end)
        {
            return;
        }
        let condition = match node.kind() {
            "if_statement" | "elif_clause" | "while_statement" => {
                node.child_by_field_name("condition")
            }
            "assert_statement" => node.named_child(0),
            "lambda" => node.child_by_field_name("body"),
            "call"
                if node
                    .child_by_field_name("function")
                    .is_some_and(|f| text(f, source) == "require") =>
            {
                node.child_by_field_name("arguments")
                    .and_then(|a| a.named_child(0))
            }
            _ => None,
        };
        if let Some(condition) = condition {
            out.push(Site {
                line: condition.start_position().row + 1,
                code: text(condition, source).into(),
                expr: expression(condition, source),
                kind: node.kind(),
            });
        }
        let mut cursor = node.walk();
        for child in node.named_children(&mut cursor) {
            walk(child, source, excluded, out);
        }
    }
    let mut result = vec![];
    walk(tree.root_node(), source, &excluded, &mut result);
    result
}

pub(super) fn signature(expr: &Expr) -> String {
    format!("{expr:?}")
}

/// Resolve explicit from-imports (including aliases); dynamic imports remain unsupported.
pub(super) fn imported_names(tree: &Tree, source: &str, module: &str, symbol: &str) -> Vec<String> {
    let mut names = vec![];
    for node in tree
        .root_node()
        .named_children(&mut tree.root_node().walk())
    {
        if node.kind() != "import_from_statement"
            || !node
                .child_by_field_name("module_name")
                .is_some_and(|n| text(n, source) == module)
        {
            continue;
        }
        for item in node.children_by_field_name("name", &mut node.walk()) {
            if item.kind() == "aliased_import" {
                if item
                    .child_by_field_name("name")
                    .is_some_and(|n| text(n, source) == symbol)
                    && let Some(alias) = item.child_by_field_name("alias")
                {
                    names.push(text(alias, source).into());
                }
            } else if text(item, source) == symbol {
                names.push(symbol.into());
            }
        }
    }
    names
}

pub(super) fn canonical_predicate<'a>(node: Node<'a>, source: &str) -> Result<(Node<'a>, String)> {
    let assignment = node
        .named_child(0)
        .context("canonical assignment required")?;
    let call = assignment
        .child_by_field_name("right")
        .context("canonical value required")?;
    ensure!(
        call.kind() == "call"
            && call
                .child_by_field_name("function")
                .is_some_and(|n| text(n, source) == "PredicateSpec"),
        "canonical value must directly call PredicateSpec"
    );
    let lambda = call
        .child_by_field_name("arguments")
        .and_then(|n| n.named_child(0))
        .context("predicate argument required")?;
    ensure!(lambda.kind() == "lambda", "inline lambda required");
    let params = lambda
        .child_by_field_name("parameters")
        .context("one context binder required")?;
    let binders: Vec<_> = params.named_children(&mut params.walk()).collect();
    ensure!(
        binders.len() == 1 && binders[0].kind() == "identifier",
        "one plain context binder required"
    );
    Ok((
        lambda
            .child_by_field_name("body")
            .context("predicate body required")?,
        text(binders[0], source).into(),
    ))
}
