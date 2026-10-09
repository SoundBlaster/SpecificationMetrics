//! Explicit, snapshot-bound expression selection; not discovery or classification.
use std::fs;
use std::path::{Component, Path};

use anyhow::{Context, Result, ensure};
use clap::ValueEnum;
use serde::Serialize;
use tree_sitter::{Node, Parser};

#[derive(Clone, Copy, Debug, Serialize, ValueEnum)]
#[serde(rename_all = "snake_case")]
pub enum Selection {
    Condition,
    Value,
    Expression,
}

#[derive(Debug, Serialize)]
pub struct Span {
    /// 0-based UTF-8 byte offsets, end exclusive.
    start_byte: usize,
    end_byte: usize,
    /// 1-based line and UTF-8 byte columns, end exclusive.
    start_line: usize,
    start_column: usize,
    end_line: usize,
    end_column: usize,
}

#[derive(Debug, Serialize)]
pub struct SourceSlice {
    syntax_kind: String,
    span: Span,
    digest: String,
    code: String,
    truncated: bool,
}

#[derive(Debug, Serialize)]
pub struct DecisionTarget {
    artifact_type: &'static str,
    schema_version: u32,
    experimental: bool,
    language: &'static str,
    pub target_id: String,
    path: String,
    pub source_digest: String,
    selection: Selection,
    anchor: SourceSlice,
    pub expression: SourceSlice,
    context: SourceSlice,
    ownership_status: &'static str,
    metric_effect: &'static str,
}

fn digest(bytes: &[u8]) -> String {
    format!("blake3:{}", blake3::hash(bytes).to_hex())
}

fn slice(node: Node<'_>, source: &[u8], budget: usize) -> Result<SourceSlice> {
    let full = node.utf8_text(source)?;
    let mut limit = budget.min(full.len());
    while !full.is_char_boundary(limit) {
        limit -= 1;
    }
    let start = node.start_position();
    let end = node.end_position();
    Ok(SourceSlice {
        syntax_kind: node.kind().into(),
        span: Span {
            start_byte: node.start_byte(),
            end_byte: node.end_byte(),
            start_line: start.row + 1,
            start_column: start.column + 1,
            end_line: end.row + 1,
            end_column: end.column + 1,
        },
        digest: digest(full.as_bytes()),
        code: full[..limit].into(),
        truncated: limit < full.len(),
    })
}

fn find<'a>(node: Node<'a>, line: usize, column: usize, kind: &str) -> Option<Node<'a>> {
    let point = node.start_position();
    if node.is_named() && point.row + 1 == line && point.column + 1 == column && node.kind() == kind
    {
        return Some(node);
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if let Some(found) = find(child, line, column, kind) {
            return Some(found);
        }
    }
    None
}

fn expression(anchor: Node<'_>, selection: Selection) -> Result<Node<'_>> {
    let result = match (selection, anchor.kind()) {
        (Selection::Condition, "if_statement" | "elif_clause" | "while_statement") => {
            anchor.child_by_field_name("condition")
        }
        (Selection::Condition, "conditional_expression") => {
            let mut cursor = anchor.walk();
            anchor
                .named_children(&mut cursor)
                .filter(|n| n.kind() != "comment")
                .nth(1)
        }
        (Selection::Value, "return_statement") => {
            let mut cursor = anchor.walk();
            anchor
                .named_children(&mut cursor)
                .find(|n| n.kind() != "comment")
        }
        (Selection::Value, "assignment") => anchor.child_by_field_name("right"),
        (Selection::Value, "lambda") => anchor.child_by_field_name("body"),
        (Selection::Expression, _) if anchor.is_named() => {
            // Explicit identity selection is restricted to expression nodes;
            // a function or branch body cannot silently become the target.
            let allowed = [
                "call",
                "boolean_operator",
                "comparison_operator",
                "unary_operator",
                "identifier",
                "attribute",
                "subscript",
                "conditional_expression",
            ];
            allowed.contains(&anchor.kind()).then_some(anchor)
        }
        _ => None,
    };
    result.context("unsupported selector/anchor combination or missing expression")
}

fn context_node(anchor: Node<'_>) -> Node<'_> {
    let mut current = Some(anchor);
    while let Some(node) = current {
        if matches!(
            node.kind(),
            "function_definition" | "class_definition" | "assignment"
        ) {
            return node;
        }
        current = node.parent();
    }
    anchor
}

#[allow(clippy::too_many_arguments)]
pub fn extract(
    root: &Path,
    path: &str,
    line: usize,
    column: usize,
    kind: &str,
    selection: Selection,
    expected_digest: Option<&str>,
) -> Result<DecisionTarget> {
    ensure!(line > 0 && column > 0, "line and column must be positive");
    let relative = Path::new(path);
    let normalized = relative
        .components()
        .map(|c| c.as_os_str().to_string_lossy())
        .collect::<Vec<_>>()
        .join("/");
    ensure!(
        !relative.as_os_str().is_empty()
            && relative
                .components()
                .all(|c| matches!(c, Component::Normal(_)))
            && !path.contains('\\')
            && normalized == path,
        "path must be normalized and relative"
    );
    ensure!(
        relative.extension().is_some_and(|e| e == "py"),
        "experimental target extraction supports Python only"
    );
    let root = root.canonicalize()?;
    let file = root.join(relative).canonicalize()?;
    ensure!(file.starts_with(&root), "source path escapes root");
    let source = fs::read(&file)?;
    std::str::from_utf8(&source).context("source is not UTF-8")?;
    let source_digest = digest(&source);
    if let Some(expected) = expected_digest {
        ensure!(expected == source_digest, "source digest mismatch");
    }
    let mut parser = Parser::new();
    parser.set_language(&tree_sitter_python::LANGUAGE.into())?;
    let tree = parser
        .parse(&source, None)
        .context("parser returned no tree")?;
    ensure!(
        !tree.root_node().has_error(),
        "source has parse errors; refusing target extraction"
    );
    let anchor =
        find(tree.root_node(), line, column, kind).context("exact syntax anchor not found")?;
    let selected = expression(anchor, selection)?;
    ensure!(
        selected.byte_range().len() <= 4096,
        "target exceeds 4 KiB; select a narrower expression"
    );
    let expression = slice(selected, &source, 4096)?;
    let identity = serde_json::to_vec(&(
        "specification_metrics.decision_target/v1",
        path,
        &source_digest,
        &expression.syntax_kind,
        expression.span.start_byte,
        expression.span.end_byte,
    ))?;
    Ok(DecisionTarget {
        artifact_type: "specification_metrics.decision_target",
        schema_version: 1,
        experimental: true,
        language: "python",
        target_id: digest(&identity),
        path: path.into(),
        source_digest,
        selection,
        anchor: slice(anchor, &source, 4096)?,
        expression,
        context: slice(context_node(anchor), &source, 12288)?,
        ownership_status: "unknown",
        metric_effect: "none",
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(
        source: &str,
        line: usize,
        column: usize,
        kind: &str,
        select: Selection,
    ) -> Result<DecisionTarget> {
        let dir = tempfile::tempdir()?;
        fs::write(dir.path().join("example.py"), source)?;
        extract(dir.path(), "example.py", line, column, kind, select, None)
    }

    #[test]
    fn selects_condition_and_keeps_body_as_context() {
        let source = "def act(x):\n    if x.allowed and x.ready:\n        publish()\n";
        let target = fixture(source, 2, 5, "if_statement", Selection::Condition).unwrap();
        assert_eq!(target.expression.code, "x.allowed and x.ready");
        assert!(target.context.code.contains("publish()"));
        let span = &target.expression.span;
        assert_eq!(
            &source.as_bytes()[span.start_byte..span.end_byte],
            target.expression.code.as_bytes()
        );
        assert_eq!(target.ownership_status, "unknown");
    }

    #[test]
    fn supports_returns_lambdas_ternaries_and_construction_values() {
        for (source, line, column, kind, select, expected) in [
            (
                "def check(x):\n    return x.a and x.b\n",
                2,
                5,
                "return_statement",
                Selection::Value,
                "x.a and x.b",
            ),
            (
                "RULE = FirstMatch.with_fallback((), 1)\n",
                1,
                1,
                "assignment",
                Selection::Value,
                "FirstMatch.with_fallback((), 1)",
            ),
            (
                "rule = lambda x: x > 1\n",
                1,
                8,
                "lambda",
                Selection::Value,
                "x > 1",
            ),
            (
                "x = yes if condition else no\n",
                1,
                5,
                "conditional_expression",
                Selection::Condition,
                "condition",
            ),
        ] {
            let target = fixture(source, line, column, kind, select).unwrap();
            assert_eq!(target.expression.code, expected);
        }
    }

    #[test]
    fn rejects_wrong_anchor_parse_errors_and_whole_function() {
        assert!(
            fixture(
                "if ok:\n    pass\n",
                1,
                2,
                "if_statement",
                Selection::Condition
            )
            .is_err()
        );
        assert!(fixture("if :\n", 1, 1, "if_statement", Selection::Condition).is_err());
        assert!(
            fixture(
                "def f():\n    return 1\n",
                1,
                1,
                "function_definition",
                Selection::Expression
            )
            .is_err()
        );
        assert!(
            fixture(
                "def f():\n    return\n",
                2,
                5,
                "return_statement",
                Selection::Value
            )
            .is_err()
        );
    }

    #[test]
    fn comments_do_not_shift_ternary_condition_and_boolean_chains_use_outermost_anchor() {
        let source = "x = (\n    yes # explanation\n    if ok\n    else no\n)\n";
        let target = fixture(source, 2, 5, "conditional_expression", Selection::Condition).unwrap();
        assert_eq!(target.expression.code, "ok");
        let target = fixture(
            "x = a and b and c\n",
            1,
            5,
            "boolean_operator",
            Selection::Expression,
        )
        .unwrap();
        assert_eq!(target.expression.code, "a and b and c");
    }

    #[test]
    fn truncated_context_remains_utf8_and_keeps_full_span_digest() {
        let source = format!(
            "def ready(x):\n    # {}\n    return x.ready\n",
            "контекст".repeat(2000)
        );
        let target = fixture(&source, 3, 5, "return_statement", Selection::Value).unwrap();
        assert!(target.context.truncated);
        assert!(target.context.code.len() <= 12288);
        assert_eq!(target.context.digest, digest(source.trim_end().as_bytes()));
        assert_eq!(target.expression.code, "x.ready");
        assert!(!target.expression.truncated);
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlinks_outside_root() {
        let dir = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        fs::write(outside.path().join("secret.py"), "return_value = True\n").unwrap();
        std::os::unix::fs::symlink(outside.path().join("secret.py"), dir.path().join("case.py"))
            .unwrap();
        assert!(
            extract(
                dir.path(),
                "case.py",
                1,
                1,
                "assignment",
                Selection::Value,
                None
            )
            .is_err()
        );
    }

    #[test]
    fn utf8_offsets_and_snapshot_identity_are_exact() {
        let source = "# намерение\nзначение = x.a and x.b\n";
        let a = fixture(source, 2, 20, "boolean_operator", Selection::Expression).unwrap();
        let b = fixture(source, 2, 1, "assignment", Selection::Value).unwrap();
        assert_eq!(a.target_id, b.target_id);
        assert_eq!(a.expression.span.start_column, 20);
        assert_ne!(
            a.target_id,
            fixture(
                &(source.to_owned() + "# changed\n"),
                2,
                1,
                "assignment",
                Selection::Value
            )
            .unwrap()
            .target_id
        );
    }

    #[test]
    fn rejects_stale_source_escaping_paths_and_oversized_targets() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join("example.py"), "if ok:\n    pass\n").unwrap();
        assert!(
            extract(
                dir.path(),
                "example.py",
                1,
                1,
                "if_statement",
                Selection::Condition,
                Some("blake3:stale")
            )
            .is_err()
        );
        assert!(
            extract(
                dir.path(),
                "../example.py",
                1,
                1,
                "if_statement",
                Selection::Condition,
                None
            )
            .is_err()
        );
        let source = format!("if {}:\n    pass\n", "a and ".repeat(1000) + "b");
        assert!(fixture(&source, 1, 1, "if_statement", Selection::Condition).is_err());
    }
}
