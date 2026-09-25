use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, ensure};
use ignore::WalkBuilder;
use tree_sitter::{Language as TreeSitterLanguage, Node, Parser};

use crate::model::{Candidate, Language, ParseIssue, SCHEMA_VERSION, ScanReport};

pub fn scan(root: &Path, includes: &[String]) -> Result<ScanReport> {
    let root = root
        .canonicalize()
        .with_context(|| format!("cannot resolve {}", root.display()))?;
    let includes = normalize_includes(includes)?;
    let base = if root.is_file() {
        root.parent().expect("source file has a parent")
    } else {
        &root
    };
    for include in &includes {
        let selected = base
            .join(include)
            .canonicalize()
            .with_context(|| format!("include path does not exist: {include}"))?;
        ensure!(
            selected.starts_with(base),
            "include escapes scan root: {include}"
        );
    }
    let mut files = source_files(&root)?;
    files.sort();

    let mut candidates = Vec::new();
    let mut parse_issues = Vec::new();
    for file in files {
        let language = file
            .extension()
            .and_then(|extension| extension.to_str())
            .and_then(Language::from_extension)
            .expect("source_files returns only supported extensions");
        let relative_path = if root.is_file() {
            file.file_name().expect("source file has a name")
        } else {
            file.strip_prefix(&root)
                .expect("file is inside root")
                .as_os_str()
        };
        let relative_path = relative_path.to_string_lossy().replace('\\', "/");
        if !includes.is_empty()
            && !includes.iter().any(|included| {
                relative_path == *included || relative_path.starts_with(&format!("{included}/"))
            })
        {
            continue;
        }
        let source = match fs::read_to_string(&file) {
            Ok(source) => source,
            Err(error) => {
                parse_issues.push(ParseIssue {
                    path: relative_path,
                    message: format!("cannot read UTF-8 source: {error}"),
                });
                continue;
            }
        };
        let mut parser = Parser::new();
        parser
            .set_language(&tree_sitter_language(language))
            .with_context(|| format!("cannot load {} parser", language.label()))?;
        let Some(tree) = parser.parse(&source, None) else {
            parse_issues.push(ParseIssue {
                path: relative_path,
                message: "parser returned no syntax tree".to_owned(),
            });
            continue;
        };
        let root_node = tree.root_node();
        if root_node.has_error() {
            parse_issues.push(ParseIssue {
                path: relative_path.clone(),
                message: "syntax tree contains an ERROR or MISSING node".to_owned(),
            });
        }
        let mut occurrences = HashMap::new();
        visit(
            root_node,
            language,
            &relative_path,
            source.as_bytes(),
            &mut occurrences,
            &mut candidates,
        );
    }
    candidates.sort_by(|a, b| {
        (&a.path, a.line, a.column, &a.fingerprint).cmp(&(
            &b.path,
            b.line,
            b.column,
            &b.fingerprint,
        ))
    });
    Ok(ScanReport {
        schema_version: SCHEMA_VERSION,
        root: root.display().to_string(),
        includes,
        candidates,
        parse_issues,
    })
}

pub fn normalize_includes(includes: &[String]) -> Result<Vec<String>> {
    let mut normalized = Vec::new();
    for include in includes {
        let include = include.trim().trim_end_matches('/').replace('\\', "/");
        let path = Path::new(&include);
        if include.is_empty()
            || path.is_absolute()
            || path.components().any(|component| {
                matches!(
                    component,
                    std::path::Component::ParentDir | std::path::Component::CurDir
                )
            })
        {
            anyhow::bail!("include must be a non-empty relative path: {include}");
        }
        normalized.push(include);
    }
    normalized.sort();
    normalized.dedup();
    Ok(normalized)
}

fn source_files(root: &Path) -> Result<Vec<PathBuf>> {
    if root.is_file() {
        return Ok(if supported(root) {
            vec![root.to_path_buf()]
        } else {
            Vec::new()
        });
    }
    let mut files = Vec::new();
    for entry in WalkBuilder::new(root).build() {
        let entry = entry.with_context(|| format!("cannot walk {}", root.display()))?;
        if entry
            .file_type()
            .is_some_and(|file_type| file_type.is_file())
            && supported(entry.path())
        {
            files.push(entry.into_path());
        }
    }
    Ok(files)
}

fn supported(path: &Path) -> bool {
    path.extension()
        .and_then(|extension| extension.to_str())
        .and_then(Language::from_extension)
        .is_some()
}

fn tree_sitter_language(language: Language) -> TreeSitterLanguage {
    match language {
        Language::Python => tree_sitter_python::LANGUAGE.into(),
        Language::Swift => tree_sitter_swift::LANGUAGE.into(),
        Language::Rust => tree_sitter_rust::LANGUAGE.into(),
    }
}

fn decision_kind(language: Language, node: Node<'_>, source: &[u8]) -> Option<&'static str> {
    if language == Language::Swift && node.kind() == "call_expression" {
        let text = String::from_utf8_lossy(&source[node.byte_range()]);
        if text
            .trim_start()
            .strip_prefix("defer")
            .is_some_and(|remainder| remainder.trim_start().starts_with('{'))
        {
            return Some("defer");
        }
    }
    let kind = match (language, node.kind()) {
        (Language::Python, "if_statement") => "if",
        (Language::Python, "conditional_expression") => "conditional_expression",
        (Language::Python, "if_clause") => "comprehension_filter",
        (Language::Python, "match_statement") => "match",
        (Language::Swift, "if_statement" | "if_expression") => "if",
        (Language::Swift, "guard_statement") => "guard",
        (Language::Swift, "switch_statement" | "switch_expression") => "switch",
        (Language::Rust, "if_expression") => "if",
        (Language::Rust, "match_expression") => "match",
        _ => return None,
    };
    if kind == "if" && is_direct_else_if(node) {
        return None;
    }
    Some(kind)
}

fn is_direct_else_if(node: Node<'_>) -> bool {
    node.parent().is_some_and(|parent| {
        parent.kind() == "if_expression"
            || parent.kind() == "if_statement"
            || ((parent.kind() == "else_clause" || parent.kind() == "else")
                && parent.parent().is_some_and(|grandparent| {
                    grandparent.kind() == "if_expression" || grandparent.kind() == "if_statement"
                }))
    })
}

fn visit(
    node: Node<'_>,
    language: Language,
    path: &str,
    source: &[u8],
    occurrences: &mut HashMap<String, usize>,
    candidates: &mut Vec<Candidate>,
) {
    if let Some(kind) = decision_kind(language, node, source) {
        let source_text = String::from_utf8_lossy(&source[node.byte_range()]);
        let normalized: String = source_text.split_whitespace().collect();
        let digest = blake3::hash(normalized.as_bytes()).to_hex().to_string();
        let base = format!("{}:{path}:{kind}:{}", language.label(), &digest[..16]);
        let occurrence = occurrences.entry(base.clone()).or_insert(0);
        *occurrence += 1;
        let position = node.start_position();
        let excerpt = source_text
            .lines()
            .find(|line| !line.trim().is_empty())
            .unwrap_or_default()
            .trim()
            .chars()
            .take(120)
            .collect();
        candidates.push(Candidate {
            fingerprint: format!("{base}:{}", *occurrence),
            language,
            path: path.to_owned(),
            kind: kind.to_owned(),
            line: position.row + 1,
            column: position.column + 1,
            excerpt,
        });
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        visit(child, language, path, source, occurrences, candidates);
    }
}

#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;

    use super::scan;

    #[test]
    fn discovers_decisions_in_all_three_languages() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.py"),
            "if a:\n    pass\nelif b:\n    pass\nx = 1 if c else 2\ny = [n for n in xs if n]\nmatch x:\n    case 1: pass\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("example.swift"),
            "func f(_ x: Int) {\n    if x > 0 { print(x) } else if x == 0 { print(0) }\n    guard x >= 0 else { return }\n    switch x { case 1: print(1); default: break }\n    defer { print(\"done\") }\n}\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("example.rs"),
            "fn f(x: i32) {\n    if x > 0 {} else if x == 0 {}\n    match x { 0 => {}, _ => {} };\n}\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        let kinds: Vec<_> = report
            .candidates
            .iter()
            .map(|candidate| (candidate.path.as_str(), candidate.kind.as_str()))
            .collect();
        assert!(kinds.contains(&("example.py", "if")));
        assert!(kinds.contains(&("example.py", "conditional_expression")));
        assert!(kinds.contains(&("example.py", "comprehension_filter")));
        assert!(kinds.contains(&("example.py", "match")));
        assert!(kinds.contains(&("example.swift", "if")));
        assert!(kinds.contains(&("example.swift", "guard")));
        assert!(kinds.contains(&("example.swift", "switch")));
        assert!(kinds.contains(&("example.swift", "defer")));
        assert!(kinds.contains(&("example.rs", "if")));
        assert!(kinds.contains(&("example.rs", "match")));
        for path in ["example.py", "example.swift", "example.rs"] {
            assert_eq!(
                kinds
                    .iter()
                    .filter(|(candidate_path, kind)| *candidate_path == path && *kind == "if")
                    .count(),
                1,
                "else-if chains count as one decision in {path}"
            );
        }
    }

    #[test]
    fn fingerprint_survives_lines_inserted_before_decision() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("example.py");
        fs::write(&source, "if flag:\n    act()\n").unwrap();
        let first = scan(dir.path(), &[]).unwrap();
        fs::write(&source, "\n\nif flag:\n    act()\n").unwrap();
        let second = scan(dir.path(), &[]).unwrap();
        assert_eq!(
            first.candidates[0].fingerprint,
            second.candidates[0].fingerprint
        );
        assert_eq!(first.candidates[0].line, 1);
        assert_eq!(second.candidates[0].line, 3);
    }

    #[test]
    fn narrowing_and_expanding_scope_preserves_existing_fingerprints() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("first.py"), "if first:\n    pass\n").unwrap();
        fs::write(dir.path().join("second.py"), "if second:\n    pass\n").unwrap();
        let first = scan(dir.path(), &["first.py".to_owned()]).unwrap();
        let both = scan(dir.path(), &["first.py".to_owned(), "second.py".to_owned()]).unwrap();
        assert_eq!(first.candidates.len(), 1);
        assert_eq!(both.candidates.len(), 2);
        assert_eq!(
            first.candidates[0].fingerprint,
            both.candidates[0].fingerprint
        );
    }

    #[test]
    fn invalid_include_is_rejected() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("first.py"), "if first:\n    pass\n").unwrap();
        assert!(scan(dir.path(), &["missing.py".to_owned()]).is_err());
        assert!(scan(dir.path(), &["../outside.py".to_owned()]).is_err());
    }
}
