use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, ensure};
use ignore::WalkBuilder;
use tree_sitter::{Language as TreeSitterLanguage, Node, Parser};

use crate::model::{
    Candidate, Language, ParseIssue, SCHEMA_VERSION, ScanReport, ScopeIssue,
    SpecificationDefinition,
};
use crate::scope::{ScopeManifest, SourceRole};

#[cfg(test)]
pub fn scan(root: &Path, includes: &[String]) -> Result<ScanReport> {
    scan_with_scope(root, includes, None)
}

pub fn scan_with_scope(
    root: &Path,
    includes: &[String],
    manifest: Option<&ScopeManifest>,
) -> Result<ScanReport> {
    let root = root
        .canonicalize()
        .with_context(|| format!("cannot resolve {}", root.display()))?;
    let includes = normalize_includes(includes)?;
    ensure!(
        manifest.is_none() || includes.is_empty(),
        "--include cannot be combined with a scope manifest"
    );
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
    for include in &includes {
        let selected = base.join(include).canonicalize()?;
        if selected.is_file() {
            ensure!(
                supported(&selected),
                "included file is not a supported source: {include}"
            );
            ensure!(
                files.binary_search(&selected).is_ok(),
                "included source is ignored by the file walker: {include}"
            );
        } else {
            ensure!(
                files.iter().any(|file| file.starts_with(&selected)),
                "included directory has no selected source files: {include}"
            );
        }
    }

    let mut candidates = Vec::new();
    let mut specifications = Vec::new();
    let mut parse_issues = Vec::new();
    let mut scope_issues = Vec::new();
    let mut application_files = 0;
    let mut excluded_files = 0;
    let mut source_hasher = blake3::Hasher::new();
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
        if let Some(manifest) = manifest {
            match manifest.role_for(&relative_path) {
                Ok(SourceRole::Application) => {}
                Ok(_) => {
                    excluded_files += 1;
                    continue;
                }
                Err(message) => {
                    scope_issues.push(ScopeIssue {
                        path: relative_path,
                        message,
                    });
                    continue;
                }
            }
        }
        application_files += 1;
        let source_bytes = match fs::read(&file) {
            Ok(source) => source,
            Err(error) => {
                parse_issues.push(ParseIssue {
                    path: relative_path,
                    message: format!("cannot read source: {error}"),
                });
                continue;
            }
        };
        source_hasher.update(relative_path.as_bytes());
        source_hasher.update(&[0]);
        source_hasher.update(&source_bytes);
        source_hasher.update(&[0]);
        let source = match std::str::from_utf8(&source_bytes) {
            Ok(source) => source,
            Err(error) => {
                parse_issues.push(ParseIssue {
                    path: relative_path,
                    message: format!("cannot decode UTF-8 source: {error}"),
                });
                continue;
            }
        };
        let mut parser = Parser::new();
        parser
            .set_language(&tree_sitter_language(language))
            .with_context(|| format!("cannot load {} parser", language.label()))?;
        let Some(tree) = parser.parse(source, None) else {
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
        let mut state = VisitState {
            occurrences: &mut occurrences,
            candidates: &mut candidates,
            specifications: &mut specifications,
        };
        visit(
            root_node,
            language,
            &relative_path,
            source.as_bytes(),
            &mut state,
            false,
        );
    }
    if manifest.is_some() && application_files == 0 {
        scope_issues.push(ScopeIssue {
            path: ".".to_owned(),
            message: "scope manifest selected no application source files".to_owned(),
        });
    }
    candidates.sort_by(|a, b| {
        (&a.path, a.line, a.column, &a.fingerprint).cmp(&(
            &b.path,
            b.line,
            b.column,
            &b.fingerprint,
        ))
    });
    specifications.sort_by(|a, b| {
        (&a.path, a.line, a.column, &a.name).cmp(&(&b.path, b.line, b.column, &b.name))
    });
    let scope_review_required = manifest.is_none() && includes.is_empty() && root.is_dir();
    Ok(ScanReport {
        schema_version: SCHEMA_VERSION,
        root: root.display().to_string(),
        includes,
        scope_manifest_digest: manifest.map(|manifest| manifest.digest().to_owned()),
        scope_issues,
        scope_review_required,
        application_files,
        excluded_files,
        candidates,
        specifications,
        source_digest: source_hasher.finalize().to_hex().to_string(),
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

struct VisitState<'a> {
    occurrences: &'a mut HashMap<String, usize>,
    candidates: &'a mut Vec<Candidate>,
    specifications: &'a mut Vec<SpecificationDefinition>,
}

fn visit(
    node: Node<'_>,
    language: Language,
    path: &str,
    source: &[u8],
    state: &mut VisitState<'_>,
    inside_specification: bool,
) {
    let declaration = specification_declaration(language, node, source);
    let factory = specification_factory(language, node, source);
    if let Some((name, kind)) = declaration.as_ref().or(factory.as_ref()) {
        let position = node.start_position();
        state.specifications.push(SpecificationDefinition {
            language,
            path: path.to_owned(),
            name: name.clone(),
            kind: (*kind).to_owned(),
            line: position.row + 1,
            column: position.column + 1,
        });
    }
    let inside_specification = inside_specification || declaration.is_some() || factory.is_some();
    if let Some(kind) = decision_kind(language, node, source) {
        let source_text = String::from_utf8_lossy(&source[node.byte_range()]);
        let normalized: String = source_text.split_whitespace().collect();
        let digest = blake3::hash(normalized.as_bytes()).to_hex().to_string();
        let base = format!("{}:{path}:{kind}:{}", language.label(), &digest[..16]);
        let occurrence = state.occurrences.entry(base.clone()).or_insert(0);
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
        state.candidates.push(Candidate {
            fingerprint: format!("{base}:{}", *occurrence),
            language,
            path: path.to_owned(),
            kind: kind.to_owned(),
            line: position.row + 1,
            column: position.column + 1,
            excerpt,
            inside_specification,
        });
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        visit(child, language, path, source, state, inside_specification);
    }
}

fn specification_declaration(
    language: Language,
    node: Node<'_>,
    source: &[u8],
) -> Option<(String, &'static str)> {
    let name = match (language, node.kind()) {
        (Language::Python, "class_definition") => {
            let bases = node.child_by_field_name("superclasses")?;
            let mut cursor = bases.walk();
            if !bases
                .named_children(&mut cursor)
                .any(|base| is_spec_base(node_text(base, source)))
            {
                return None;
            }
            node.child_by_field_name("name")?
        }
        (Language::Swift, "class_declaration") => {
            let mut cursor = node.walk();
            if !node
                .named_children(&mut cursor)
                .filter(|child| child.kind() == "inheritance_specifier")
                .filter_map(|base| base.child_by_field_name("inherits_from"))
                .any(|base| is_spec_base(node_text(base, source)))
            {
                return None;
            }
            node.child_by_field_name("name")?
        }
        (Language::Rust, "impl_item") => {
            let trait_node = node.child_by_field_name("trait")?;
            if !is_spec_base(node_text(trait_node, source)) {
                return None;
            }
            node.child_by_field_name("type")?
        }
        _ => return None,
    };
    let name = node_text(name, source).trim().to_owned();
    (!name.is_empty()).then_some((name, "declaration"))
}

fn is_spec_base(text: &str) -> bool {
    let base = text
        .trim()
        .split(['[', '<'])
        .next()
        .unwrap_or_default()
        .trim();
    let name = base.rsplit(['.', ':']).next().unwrap_or(base).trim();
    is_spec_marker(name)
}

fn is_spec_marker(name: &str) -> bool {
    matches!(
        name,
        "Specification"
            | "AsyncSpecification"
            | "DecisionSpec"
            | "AsyncDecisionSpec"
            | "DecisionSpecification"
            | "AutoContextSpecification"
    )
}

fn specification_factory(
    language: Language,
    node: Node<'_>,
    source: &[u8],
) -> Option<(String, &'static str)> {
    if language == Language::Swift && node.kind() == "comparison_expression" {
        let expression = node_text(node, source).trim();
        if let Some((head, tail)) = expression.split_once('<') {
            let factory = head.rsplit('.').next().unwrap_or(head).trim();
            if matches!(factory, "PredicateSpec" | "FirstMatchSpec")
                && tail.contains('>')
                && tail
                    .split_once('>')
                    .is_some_and(|(_, after)| after.trim_start().starts_with('{'))
            {
                return Some((factory.to_owned(), "factory"));
            }
        }
    }
    let called = match (language, node.kind()) {
        (Language::Python, "call") | (Language::Rust, "call_expression") => {
            node_text(node.child_by_field_name("function")?, source)
        }
        (Language::Swift, "call_expression") => {
            node_text(node, source).split(['(', '{']).next()?.trim()
        }
        _ => return None,
    };
    let called = called.trim();
    let base = called.split('<').next().unwrap_or(called).trim();
    let last = base.rsplit(['.', ':']).next().unwrap_or(base).trim();
    let known = match language {
        Language::Python => matches!(
            last,
            "PredicateSpec" | "AsyncPredicateSpec" | "FirstMatch" | "AsyncFirstMatch"
        ),
        Language::Swift => matches!(last, "PredicateSpec" | "FirstMatchSpec"),
        Language::Rust => called.rsplit_once("::").is_some_and(|(receiver, method)| {
            let receiver = receiver
                .trim_end_matches('>')
                .split("::<")
                .next()
                .unwrap_or(receiver);
            receiver.rsplit("::").next() == Some("FirstMatch")
                && matches!(method, "new" | "default")
        }),
    };
    known.then_some((called.to_owned(), "factory"))
}

fn node_text<'a>(node: Node<'_>, source: &'a [u8]) -> &'a str {
    std::str::from_utf8(&source[node.byte_range()]).unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;

    use crate::scope::ScopeManifest;

    use super::{is_spec_base, scan, scan_with_scope};

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
        fs::write(dir.path().join("notes.txt"), "not source").unwrap();
        assert!(scan(dir.path(), &["notes.txt".to_owned()]).is_err());
        fs::create_dir(dir.path().join("empty")).unwrap();
        assert!(scan(dir.path(), &["empty".to_owned()]).is_err());
    }

    #[test]
    fn generic_argument_does_not_count_as_specification_conformance() {
        assert!(is_spec_base("specification_core.Specification[int]"));
        assert!(is_spec_base("specification_core::Specification<i32>"));
        assert!(!is_spec_base("Container<Specification>"));
        assert!(!is_spec_base("Generic[Specification]"));
    }

    #[test]
    fn counts_specification_definitions_and_ignores_their_internal_branches() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.py"),
            "from specification_core import Specification, PredicateSpec\nclass Ready(Specification[int]):\n    def is_satisfied_by(self, value):\n        if value > 0:\n            return True\n        return False\nrule = PredicateSpec(lambda value: value > 0)\nif other:\n    pass\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("example.swift"),
            "struct Ready: Specification {\n    func isSatisfiedBy(_ value: Int) -> Bool {\n        if value > 0 { return true }\n        return false\n    }\n}\nlet rule = PredicateSpec<Int> { $0 > 0 }\nif other { print(other) }\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("example.rs"),
            "struct Ready;\nimpl Specification<i32> for Ready {\n    fn is_satisfied_by(&self, value: &i32) -> bool {\n        if *value > 0 { true } else { false }\n    }\n}\nfn run(other: bool) {\n    let rule = FirstMatch::<i32, bool>::new();\n    if other {}\n}\n",
        )
        .unwrap();
        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        let by_language = |language| {
            report
                .specifications
                .iter()
                .filter(|spec| spec.language == language)
                .count()
        };
        assert_eq!(by_language(crate::model::Language::Python), 2);
        assert_eq!(by_language(crate::model::Language::Swift), 2);
        assert_eq!(by_language(crate::model::Language::Rust), 2);
        assert_eq!(
            report
                .candidates
                .iter()
                .filter(|candidate| !candidate.inside_specification)
                .count(),
            3
        );
    }

    #[test]
    fn swift_extension_conformance_covers_its_decisions() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.swift"),
            "struct Ready {}\nextension Ready: Specification {\n    func isSatisfiedBy(_ value: Int) -> Bool {\n        if value > 0 { return true }\n        return false\n    }\n}\nif unrelated { print(unrelated) }\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        assert_eq!(report.specifications.len(), 1);
        assert_eq!(report.specifications[0].name, "Ready");
        assert_eq!(report.candidates.len(), 2);
        assert!(report.candidates[0].inside_specification);
        assert!(!report.candidates[1].inside_specification);
    }

    #[test]
    fn invalid_utf8_bytes_change_source_digest() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("invalid.py");
        fs::write(&source, [0xff]).unwrap();
        let first = scan(dir.path(), &[]).unwrap();
        fs::write(&source, [0xfe]).unwrap();
        let second = scan(dir.path(), &[]).unwrap();

        assert_eq!(first.parse_issues.len(), 1);
        assert_eq!(second.parse_issues.len(), 1);
        assert_ne!(first.source_digest, second.source_digest);
    }

    #[test]
    fn whole_project_manifest_excludes_non_application_sources() {
        let dir = tempdir().unwrap();
        for directory in ["app", "vendor", "tests", "generated"] {
            fs::create_dir(dir.path().join(directory)).unwrap();
        }
        fs::write(
            dir.path().join("app/policy.py"),
            "class Ready(Specification):\n    def accepts(self, x):\n        if x: return True\nif business: pass\n",
        )
        .unwrap();
        for directory in ["vendor", "tests", "generated"] {
            fs::write(
                dir.path().join(directory).join("other.py"),
                "class Other(Specification): pass\nif ignored: pass\n",
            )
            .unwrap();
        }
        let manifest = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='framework'\npaths=['vendor']\n[[source_sets]]\nrole='test'\npaths=['tests']\n[[source_sets]]\nrole='generated'\npaths=['generated']\n",
        )
        .unwrap();
        let first = scan_with_scope(dir.path(), &[], Some(&manifest)).unwrap();
        assert!(first.scope_issues.is_empty());
        assert!(!first.scope_review_required);
        assert_eq!(first.application_files, 1);
        assert_eq!(first.excluded_files, 3);
        assert_eq!(first.specifications.len(), 1);
        assert_eq!(first.candidates.len(), 2);
        assert!(first.candidates[0].inside_specification);
        assert!(!first.candidates[1].inside_specification);

        fs::write(dir.path().join("vendor/other.py"), "if changed: pass\n").unwrap();
        let second = scan_with_scope(dir.path(), &[], Some(&manifest)).unwrap();
        assert_eq!(first.source_digest, second.source_digest);
    }

    #[test]
    fn unassigned_source_is_a_scope_issue() {
        let dir = tempdir().unwrap();
        fs::create_dir(dir.path().join("app")).unwrap();
        fs::write(dir.path().join("app/main.py"), "if ready: pass\n").unwrap();
        fs::write(dir.path().join("other.py"), "if unknown: pass\n").unwrap();
        let manifest = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['app']\n",
        )
        .unwrap();
        let report = scan_with_scope(dir.path(), &[], Some(&manifest)).unwrap();
        assert_eq!(report.scope_issues.len(), 1);
        assert_eq!(report.scope_issues[0].path, "other.py");
        assert_eq!(report.candidates.len(), 1);
    }
}
