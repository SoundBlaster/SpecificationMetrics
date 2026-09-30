use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, ensure};
use ignore::WalkBuilder;
use tree_sitter::{Language as TreeSitterLanguage, Node, Parser};

use crate::liveness::{self, PythonSource, RustModuleAssignment, RustSource};
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

    let rust_analysis = rust_marker_contexts(&root, &files, &includes, manifest);

    let mut candidates = Vec::new();
    let mut specifications = Vec::new();
    let mut python_sources = Vec::new();
    let mut rust_sources = Vec::new();
    let mut parse_issues = Vec::new();
    let mut marker_issues = Vec::new();
    let mut scope_issues = Vec::new();
    let mut application_files = 0;
    let mut excluded_files = 0;
    let mut source_hasher = blake3::Hasher::new();
    let mut sources = Vec::new();
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
        sources.push(crate::model::SourceSnapshot {
            path: relative_path.clone(),
            bytes: source_bytes.clone(),
        });
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
        if language == Language::Python {
            python_sources.push(PythonSource {
                path: relative_path.clone(),
                source: source.to_owned(),
            });
        }
        if language == Language::Rust {
            rust_sources.push(RustSource {
                path: relative_path.clone(),
                source: source.to_owned(),
                assignments: rust_analysis
                    .assignments
                    .get(&relative_path)
                    .into_iter()
                    .flatten()
                    .map(|(crate_root, module_path)| RustModuleAssignment {
                        crate_root: crate_root.clone(),
                        module_path: module_path.clone(),
                    })
                    .collect(),
            });
        }
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
        let swift_nominal_types = if language == Language::Swift {
            swift_nominal_type_names(root_node, source.as_bytes())
        } else {
            HashSet::new()
        };
        let swift_extension_specification_types = if language == Language::Swift {
            swift_extension_specification_type_names(
                root_node,
                source.as_bytes(),
                &swift_nominal_types,
            )
        } else {
            HashSet::new()
        };
        let rust_marker_context = if language == Language::Rust {
            rust_analysis
                .contexts
                .get(&relative_path)
                .cloned()
                .unwrap_or_default()
        } else {
            RustMarkerContext::default()
        };
        let mut state = VisitState {
            occurrences: &mut occurrences,
            candidates: &mut candidates,
            specifications: &mut specifications,
            marker_issues: &mut marker_issues,
            swift_nominal_types,
            swift_extension_specification_types,
            rust_marker_context,
            rust_recorded_specification_symbols: HashSet::new(),
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
    let specification_liveness = liveness::classify(
        &specifications,
        &python_sources,
        &rust_sources,
        manifest.is_some_and(ScopeManifest::liveness_closed_world),
        !parse_issues.is_empty() || !marker_issues.is_empty() || !scope_issues.is_empty(),
    );
    let liveness_review_required = specification_liveness
        .iter()
        .any(|entry| entry.status == crate::model::SpecificationLivenessStatus::Unknown);
    let liveness_closed_world = manifest.is_some_and(ScopeManifest::liveness_closed_world);
    let scope_review_required = manifest.is_none() && includes.is_empty() && root.is_dir();
    Ok(ScanReport {
        sources,
        schema_version: SCHEMA_VERSION,
        root: root.display().to_string(),
        includes,
        scope_manifest_digest: manifest.map(|manifest| manifest.digest().to_owned()),
        scope_issues,
        marker_issues,
        scope_review_required,
        application_files,
        excluded_files,
        candidates,
        specifications,
        specification_liveness,
        liveness_review_required,
        liveness_closed_world,
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
    marker_issues: &'a mut Vec<crate::model::ParseIssue>,
    swift_nominal_types: HashSet<String>,
    swift_extension_specification_types: HashSet<String>,
    rust_marker_context: RustMarkerContext,
    rust_recorded_specification_symbols: HashSet<RustSymbolPath>,
}

#[derive(Clone, Default)]
struct RustMarkerContext {
    marked_type_nodes: HashSet<usize>,
    resolved_marker_impls: HashSet<usize>,
    marked_native_impls: HashSet<usize>,
    specification_impl_nodes: HashSet<usize>,
    impl_target_symbols: HashMap<usize, HashSet<RustSymbolPath>>,
}

struct RustSourceUnit {
    source: String,
    tree: tree_sitter::Tree,
}

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
struct RustSymbolPath {
    crate_root: String,
    modules: Vec<String>,
    name: String,
}

struct RustImplRecord {
    path: String,
    crate_root: String,
    module_path: Vec<String>,
    byte: usize,
    trait_path: Option<String>,
    type_path: String,
}

#[derive(Default)]
struct RustSymbols {
    marker_traits: HashSet<RustSymbolPath>,
    types: HashSet<RustSymbolPath>,
    type_nodes: HashMap<(String, usize), HashSet<RustSymbolPath>>,
    impls: Vec<RustImplRecord>,
}

struct RustMarkerAnalysis {
    contexts: HashMap<String, RustMarkerContext>,
    assignments: HashMap<String, Vec<(String, Vec<String>)>>,
}

fn rust_marker_contexts(
    root: &Path,
    files: &[PathBuf],
    includes: &[String],
    manifest: Option<&ScopeManifest>,
) -> RustMarkerAnalysis {
    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_rust::LANGUAGE.into())
        .expect("tree-sitter Rust language is valid");
    let mut units = HashMap::<String, RustSourceUnit>::new();
    for file in files
        .iter()
        .filter(|path| path.extension().is_some_and(|ext| ext == "rs"))
    {
        let relative = if root.is_file() {
            file.file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .replace('\\', "/")
        } else {
            file.strip_prefix(root)
                .unwrap_or(file)
                .to_string_lossy()
                .replace('\\', "/")
        };
        if !includes.is_empty()
            && !includes
                .iter()
                .any(|include| relative == *include || relative.starts_with(&format!("{include}/")))
        {
            continue;
        }
        if manifest.is_some_and(|manifest| {
            !matches!(manifest.role_for(&relative), Ok(SourceRole::Application))
        }) {
            continue;
        }
        let Ok(source) = fs::read_to_string(file) else {
            continue;
        };
        let Some(tree) = parser.parse(&source, None) else {
            continue;
        };
        units.insert(relative.clone(), RustSourceUnit { source, tree });
    }
    if units.is_empty() {
        return RustMarkerAnalysis {
            contexts: HashMap::new(),
            assignments: HashMap::new(),
        };
    }

    let crate_roots = units
        .keys()
        .filter(|path| is_rust_crate_root(path))
        .cloned()
        .collect::<Vec<_>>();
    let has_declared_crate_roots = !crate_roots.is_empty();
    let roots = if has_declared_crate_roots {
        crate_roots
    } else {
        units.keys().cloned().collect::<Vec<_>>()
    };
    let mut assignments = HashMap::<String, Vec<(String, Vec<String>)>>::new();
    for crate_root in roots {
        let mut visited = HashSet::new();
        map_rust_module_file(
            &crate_root,
            &crate_root,
            Vec::new(),
            &units,
            &mut assignments,
            &mut visited,
        );
    }
    // Preserve single-file scans that have no recognizable crate root. Inside
    // a crate, an unreferenced file is not guessed to be part of that crate.
    if !has_declared_crate_roots {
        for path in units.keys() {
            if !assignments.contains_key(path) {
                assignments.insert(path.clone(), vec![(path.clone(), Vec::new())]);
            }
        }
    }

    let mut symbols = RustSymbols::default();
    for (path, unit) in &units {
        let Some(file_assignments) = assignments.get(path) else {
            continue;
        };
        for (crate_root, file_module) in file_assignments {
            collect_rust_module_symbols(
                unit.tree.root_node(),
                unit.source.as_bytes(),
                path,
                crate_root,
                file_module,
                &mut symbols,
            );
        }
    }

    let mut resolved_markers = Vec::new();
    let mut marked_types = HashSet::<RustSymbolPath>::new();
    for record in &symbols.impls {
        let Some(trait_path) = &record.trait_path else {
            continue;
        };
        if trait_path.rsplit("::").next() != Some("SpecificationMetricV1") {
            continue;
        }
        let resolved_trait =
            resolve_rust_symbol_path(trait_path, &record.crate_root, &record.module_path);
        let resolved_type =
            resolve_rust_symbol_path(&record.type_path, &record.crate_root, &record.module_path);
        if let (Some(resolved_trait), Some(resolved_type)) = (resolved_trait, resolved_type)
            && symbols.marker_traits.contains(&resolved_trait)
            && symbols.types.contains(&resolved_type)
            && resolved_trait.crate_root == resolved_type.crate_root
        {
            marked_types.insert(resolved_type.clone());
            resolved_markers.push((record.path.clone(), record.byte));
        }
    }

    let mut contexts = HashMap::<String, RustMarkerContext>::new();
    for ((path, byte), symbols) in &symbols.type_nodes {
        if symbols.iter().any(|symbol| marked_types.contains(symbol)) {
            contexts
                .entry(path.clone())
                .or_default()
                .marked_type_nodes
                .insert(*byte);
        }
    }
    for (path, byte) in resolved_markers {
        contexts
            .entry(path)
            .or_default()
            .resolved_marker_impls
            .insert(byte);
    }
    for record in &symbols.impls {
        let Some(target) =
            resolve_rust_symbol_path(&record.type_path, &record.crate_root, &record.module_path)
        else {
            continue;
        };
        let context = contexts.entry(record.path.clone()).or_default();
        context
            .impl_target_symbols
            .entry(record.byte)
            .or_default()
            .insert(target.clone());
        if marked_types.contains(&target) {
            if record.trait_path.is_none() {
                context.specification_impl_nodes.insert(record.byte);
            } else if record.trait_path.as_deref().is_some_and(is_spec_base) {
                context.marked_native_impls.insert(record.byte);
            }
        }
    }
    RustMarkerAnalysis {
        contexts,
        assignments,
    }
}

fn is_rust_crate_root(path: &str) -> bool {
    let path = Path::new(path);
    let filename = path.file_name().and_then(|name| name.to_str());
    if matches!(filename, Some("lib.rs" | "main.rs")) {
        return true;
    }
    let components = path
        .components()
        .filter_map(|part| part.as_os_str().to_str())
        .collect::<Vec<_>>();
    components.iter().enumerate().any(|(index, component)| {
        ["bin", "examples", "tests", "benches"].contains(component)
            && index + 2 == components.len()
            && components[index + 1].ends_with(".rs")
    })
}

fn map_rust_module_file(
    crate_root: &str,
    path: &str,
    modules: Vec<String>,
    units: &HashMap<String, RustSourceUnit>,
    assignments: &mut HashMap<String, Vec<(String, Vec<String>)>>,
    visited: &mut HashSet<(String, Vec<String>)>,
) {
    let Some(unit) = units.get(path) else { return };
    if !visited.insert((path.to_owned(), modules.clone())) {
        return;
    }
    let assignment = (crate_root.to_owned(), modules.clone());
    let file_assignments = assignments.entry(path.to_owned()).or_default();
    if !file_assignments.contains(&assignment) {
        file_assignments.push(assignment);
    }
    map_rust_external_and_inline_modules(
        unit.tree.root_node(),
        unit.source.as_bytes(),
        crate_root,
        &modules,
        units,
        assignments,
        visited,
    );
}

fn map_rust_external_and_inline_modules(
    scope: Node<'_>,
    source: &[u8],
    crate_root: &str,
    modules: &[String],
    units: &HashMap<String, RustSourceUnit>,
    assignments: &mut HashMap<String, Vec<(String, Vec<String>)>>,
    visited: &mut HashSet<(String, Vec<String>)>,
) {
    let mut cursor = scope.walk();
    for item in scope.named_children(&mut cursor) {
        if item.kind() != "mod_item" {
            continue;
        }
        let Some(name_node) = item.child_by_field_name("name") else {
            continue;
        };
        let name = node_text(name_node, source).trim().to_owned();
        let mut child_modules = modules.to_vec();
        child_modules.push(name.clone());
        if let Some(body) = item.child_by_field_name("body") {
            map_rust_external_and_inline_modules(
                body,
                source,
                crate_root,
                &child_modules,
                units,
                assignments,
                visited,
            );
        } else {
            let crate_parent = Path::new(crate_root).parent().unwrap_or(Path::new(""));
            let mut module_dir = crate_parent.to_path_buf();
            for part in modules {
                module_dir.push(part);
            }
            let direct = module_dir
                .join(format!("{name}.rs"))
                .to_string_lossy()
                .replace('\\', "/");
            let nested = module_dir
                .join(&name)
                .join("mod.rs")
                .to_string_lossy()
                .replace('\\', "/");
            let Some(target) = [direct, nested]
                .into_iter()
                .find(|candidate| units.contains_key(candidate))
            else {
                continue;
            };
            map_rust_module_file(
                crate_root,
                &target,
                child_modules,
                units,
                assignments,
                visited,
            );
        }
    }
}

fn collect_rust_module_symbols(
    scope: Node<'_>,
    source: &[u8],
    path: &str,
    crate_root: &str,
    modules: &[String],
    symbols: &mut RustSymbols,
) {
    let mut cursor = scope.walk();
    for item in scope.named_children(&mut cursor) {
        match item.kind() {
            "trait_item" => {
                if item
                    .child_by_field_name("name")
                    .is_some_and(|name| node_text(name, source).trim() == "SpecificationMetricV1")
                {
                    symbols.marker_traits.insert(RustSymbolPath {
                        crate_root: crate_root.to_owned(),
                        modules: modules.to_vec(),
                        name: "SpecificationMetricV1".to_owned(),
                    });
                }
            }
            "struct_item" | "enum_item" => {
                if let Some(name) = item.child_by_field_name("name") {
                    let symbol = RustSymbolPath {
                        crate_root: crate_root.to_owned(),
                        modules: modules.to_vec(),
                        name: node_text(name, source).trim().to_owned(),
                    };
                    symbols.types.insert(symbol.clone());
                    symbols
                        .type_nodes
                        .entry((path.to_owned(), item.start_byte()))
                        .or_default()
                        .insert(symbol);
                }
            }
            "impl_item" => {
                if let Some(type_node) = item.child_by_field_name("type") {
                    symbols.impls.push(RustImplRecord {
                        path: path.to_owned(),
                        crate_root: crate_root.to_owned(),
                        module_path: modules.to_vec(),
                        byte: item.start_byte(),
                        trait_path: item
                            .child_by_field_name("trait")
                            .map(|n| node_text(n, source).trim().to_owned()),
                        type_path: node_text(type_node, source).trim().to_owned(),
                    });
                }
            }
            "mod_item" => {
                if let Some(name_node) = item.child_by_field_name("name")
                    && let Some(body) = item.child_by_field_name("body")
                {
                    let mut child_modules = modules.to_vec();
                    child_modules.push(node_text(name_node, source).trim().to_owned());
                    collect_rust_module_symbols(
                        body,
                        source,
                        path,
                        crate_root,
                        &child_modules,
                        symbols,
                    );
                }
            }
            _ => {}
        }
    }
}

fn resolve_rust_symbol_path(
    path: &str,
    crate_root: &str,
    current_module: &[String],
) -> Option<RustSymbolPath> {
    let path = path
        .split('<')
        .next()?
        .chars()
        .filter(|c| !c.is_whitespace())
        .collect::<String>();
    let mut segments = path
        .split("::")
        .filter(|segment| !segment.is_empty())
        .collect::<Vec<_>>();
    if segments.is_empty() {
        return None;
    }
    let modules = match segments[0] {
        "crate" => {
            segments.remove(0);
            Vec::new()
        }
        "self" => {
            segments.remove(0);
            current_module.to_vec()
        }
        "super" => {
            let mut modules = current_module.to_vec();
            while segments.first() == Some(&"super") {
                segments.remove(0);
                modules.pop()?;
            }
            modules
        }
        _ => current_module.to_vec(),
    };
    if segments.is_empty() {
        return None;
    }
    let name = segments.pop()?.to_owned();
    let mut modules = modules;
    modules.extend(segments.into_iter().map(str::to_owned));
    Some(RustSymbolPath {
        crate_root: crate_root.to_owned(),
        modules,
        name,
    })
}

enum PythonMarker {
    Absent,
    Valid,
    Invalid {
        message: String,
        row: usize,
        column: usize,
    },
}

fn visit(
    node: Node<'_>,
    language: Language,
    path: &str,
    source: &[u8],
    state: &mut VisitState<'_>,
    inside_specification: bool,
) {
    let marker = if language == Language::Python && node.kind() == "class_definition" {
        python_specification_marker(node, source)
    } else {
        PythonMarker::Absent
    };
    if let PythonMarker::Invalid {
        message,
        row,
        column,
    } = &marker
    {
        let class_name = node
            .child_by_field_name("name")
            .map(|name| node_text(name, source).trim())
            .unwrap_or("<anonymous>");
        state.marker_issues.push(crate::model::ParseIssue {
            path: path.to_owned(),
            message: format!(
                "Python Specification marker on class {class_name:?} at {}:{}: {message}",
                row + 1,
                column + 1
            ),
        });
    }
    if language == Language::Swift
        && swift_marker_extension(node, source)
        && node.child_by_field_name("name").is_some_and(|name| {
            !state
                .swift_nominal_types
                .contains(node_text(name, source).trim())
        })
    {
        state.marker_issues.push(crate::model::ParseIssue {
            path: path.to_owned(),
            message: format!(
                "Swift SpecificationMetricV1 extension at {}:{} does not resolve to a nominal type declared in the same source file",
                node.start_position().row + 1,
                node.start_position().column + 1
            ),
        });
    }
    if language == Language::Rust
        && rust_marker_trait_candidate(node, source)
        && !rust_marker_implementation_is_resolved(node, source, &state.rust_marker_context)
    {
        state.marker_issues.push(crate::model::ParseIssue {
            path: path.to_owned(),
            message: format!(
                "Rust SpecificationMetricV1 implementation at {}:{} must resolve to a declared marker trait and a struct or enum in the measured crate",
                node.start_position().row + 1,
                node.start_position().column + 1
            ),
        });
    }
    let declaration = specification_declaration(
        language,
        node,
        source,
        &state.swift_nominal_types,
        &state.swift_extension_specification_types,
        &state.rust_marker_context,
    )
    .or_else(|| {
        if matches!(marker, PythonMarker::Valid) {
            let name = node.child_by_field_name("name")?;
            Some((node_text(name, source).trim().to_owned(), "declaration"))
        } else {
            None
        }
    });
    let factory = specification_factory(language, node, source);
    let extension_conformance_for_local_type = language == Language::Swift
        && swift_specification_extension(node, source)
        && node.child_by_field_name("name").is_some_and(|name| {
            state
                .swift_nominal_types
                .contains(node_text(name, source).trim())
        });
    let rust_duplicate_specification = language == Language::Rust
        && declaration.is_some()
        && is_duplicate_rust_specification(
            node,
            source,
            &state.rust_marker_context,
            &mut state.rust_recorded_specification_symbols,
        );
    if !extension_conformance_for_local_type
        && !rust_duplicate_specification
        && let Some((name, kind)) = declaration.as_ref().or(factory.as_ref())
    {
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
    let inside_specification = inside_specification
        || (language == Language::Rust
            && rust_inherent_impl_for_specification(node, source, &state.rust_marker_context));
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

fn python_specification_marker(node: Node<'_>, source: &[u8]) -> PythonMarker {
    const MARKER_NAME: &str = "__specmetrics_specification__";
    let Some(body) = node.child_by_field_name("body") else {
        return PythonMarker::Absent;
    };
    let mut assignments = Vec::new();
    let mut body_cursor = body.walk();
    for statement in body.named_children(&mut body_cursor) {
        if statement.kind() != "expression_statement" {
            continue;
        }
        let mut statement_cursor = statement.walk();
        for expression in statement.named_children(&mut statement_cursor) {
            if expression.kind() != "assignment" {
                continue;
            }
            let Some(left) = expression.child_by_field_name("left") else {
                continue;
            };
            if node_text(left, source).trim() == MARKER_NAME {
                assignments.push(expression);
            }
        }
    }
    if assignments.is_empty() {
        return PythonMarker::Absent;
    }
    if assignments.len() != 1 {
        let position = assignments[0].start_position();
        return PythonMarker::Invalid {
            message: "the marker class variable must be declared exactly once".to_owned(),
            row: position.row,
            column: position.column,
        };
    }
    let assignment = assignments[0];
    let annotation = assignment
        .child_by_field_name("type")
        .map(|node| normalize_type_expression(node_text(node, source)));
    let value_matches = assignment
        .child_by_field_name("right")
        .is_some_and(|node| is_marker_string_literal(node, source));
    let annotation_matches = annotation.as_deref().is_some_and(|annotation| {
        matches!(
            annotation,
            "ClassVar[Literal[\"specification/v1\"]]"
                | "ClassVar[Literal['specification/v1']]"
                | "typing.ClassVar[typing.Literal[\"specification/v1\"]]"
                | "typing.ClassVar[typing.Literal['specification/v1']]"
        )
    });
    if annotation_matches && value_matches {
        PythonMarker::Valid
    } else {
        let position = assignment.start_position();
        PythonMarker::Invalid {
            message: "expected ClassVar[Literal[\"specification/v1\"]] = \"specification/v1\""
                .to_owned(),
            row: position.row,
            column: position.column,
        }
    }
}

fn is_marker_string_literal(node: Node<'_>, source: &[u8]) -> bool {
    match node.kind() {
        "string" => matches!(
            node_text(node, source).trim(),
            "\"specification/v1\"" | "'specification/v1'"
        ),
        "parenthesized_expression" if node.named_child_count() == 1 => node
            .named_child(0)
            .is_some_and(|child| is_marker_string_literal(child, source)),
        _ => false,
    }
}

fn normalize_type_expression(text: &str) -> String {
    let mut normalized = String::new();
    let mut quote = None;
    let mut escaped = false;
    for character in text.chars() {
        if let Some(quote_character) = quote {
            normalized.push(character);
            if escaped {
                escaped = false;
            } else if character == '\\' {
                escaped = true;
            } else if character == quote_character {
                quote = None;
            }
        } else if matches!(character, '\'' | '"') {
            quote = Some(character);
            normalized.push(character);
        } else if !character.is_whitespace() {
            normalized.push(character);
        }
    }
    normalized
}

fn specification_declaration(
    language: Language,
    node: Node<'_>,
    source: &[u8],
    swift_nominal_types: &HashSet<String>,
    swift_extension_specification_types: &HashSet<String>,
    rust_marker_context: &RustMarkerContext,
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
            let name = node.child_by_field_name("name")?;
            let marker_extension = swift_marker_extension(node, source);
            if marker_extension && !swift_nominal_types.contains(node_text(name, source).trim()) {
                return None;
            }
            let marked_type =
                swift_extension_specification_types.contains(node_text(name, source).trim());
            let mut cursor = node.walk();
            if !marked_type
                && !node
                    .named_children(&mut cursor)
                    .filter(|child| child.kind() == "inheritance_specifier")
                    .filter_map(|base| base.child_by_field_name("inherits_from"))
                    .any(|base| {
                        is_spec_base(node_text(base, source))
                            || is_swift_marker_protocol(node_text(base, source))
                    })
            {
                return None;
            }
            name
        }
        (Language::Rust, "struct_item" | "enum_item") => {
            let name = node.child_by_field_name("name")?;
            if !rust_marker_context
                .marked_type_nodes
                .contains(&node.start_byte())
            {
                return None;
            }
            name
        }
        (Language::Rust, "impl_item") => {
            let trait_node = node.child_by_field_name("trait")?;
            if rust_marker_trait_candidate(node, source) {
                if !rust_marker_implementation_is_resolved(node, source, rust_marker_context) {
                    return None;
                }
            } else if !is_spec_base(node_text(trait_node, source))
                || rust_marker_context
                    .marked_native_impls
                    .contains(&node.start_byte())
            {
                return None;
            }
            node.child_by_field_name("type")?
        }
        _ => return None,
    };
    let name = node_text(name, source).trim().to_owned();
    (!name.is_empty()).then_some((name, "declaration"))
}

fn rust_marker_trait_candidate(node: Node<'_>, source: &[u8]) -> bool {
    node.kind() == "impl_item"
        && node.child_by_field_name("trait").is_some_and(|trait_node| {
            node_text(trait_node, source)
                .trim()
                .rsplit("::")
                .next()
                .is_some_and(|name| name.trim() == "SpecificationMetricV1")
        })
}

fn rust_marker_implementation_is_resolved(
    node: Node<'_>,
    _source: &[u8],
    context: &RustMarkerContext,
) -> bool {
    node.kind() == "impl_item" && context.resolved_marker_impls.contains(&node.start_byte())
}

fn is_duplicate_rust_specification(
    node: Node<'_>,
    source: &[u8],
    context: &RustMarkerContext,
    recorded_symbols: &mut HashSet<RustSymbolPath>,
) -> bool {
    if node.kind() != "impl_item" {
        return false;
    }
    if rust_marker_trait_candidate(node, source)
        && rust_marker_implementation_is_resolved(node, source, context)
    {
        return true;
    }
    if context.marked_native_impls.contains(&node.start_byte()) {
        return true;
    }
    let Some(targets) = context.impl_target_symbols.get(&node.start_byte()) else {
        return false;
    };
    if targets.is_empty() {
        return false;
    }
    let duplicate = targets
        .iter()
        .all(|target| recorded_symbols.contains(target));
    recorded_symbols.extend(targets.iter().cloned());
    duplicate
}

fn rust_inherent_impl_for_specification(
    node: Node<'_>,
    _source: &[u8],
    context: &RustMarkerContext,
) -> bool {
    node.kind() == "impl_item"
        && context
            .specification_impl_nodes
            .contains(&node.start_byte())
}

fn swift_marker_extension(node: Node<'_>, source: &[u8]) -> bool {
    node.kind() == "class_declaration"
        && node
            .child_by_field_name("declaration_kind")
            .is_some_and(|kind| node_text(kind, source) == "extension")
        && node
            .named_children(&mut node.walk())
            .filter(|child| child.kind() == "inheritance_specifier")
            .filter_map(|base| base.child_by_field_name("inherits_from"))
            .any(|base| is_swift_marker_protocol(node_text(base, source)))
}

fn swift_specification_extension(node: Node<'_>, source: &[u8]) -> bool {
    node.kind() == "class_declaration"
        && node
            .child_by_field_name("declaration_kind")
            .is_some_and(|kind| node_text(kind, source) == "extension")
        && node
            .named_children(&mut node.walk())
            .filter(|child| child.kind() == "inheritance_specifier")
            .filter_map(|base| base.child_by_field_name("inherits_from"))
            .any(|base| {
                is_spec_base(node_text(base, source))
                    || is_swift_marker_protocol(node_text(base, source))
            })
}

fn swift_nominal_type_names(root: Node<'_>, source: &[u8]) -> HashSet<String> {
    fn collect(node: Node<'_>, source: &[u8], names: &mut HashSet<String>) {
        if node.kind() == "class_declaration"
            && node
                .child_by_field_name("declaration_kind")
                .is_some_and(|kind| node_text(kind, source) != "extension")
            && let Some(name) = node.child_by_field_name("name")
        {
            names.insert(node_text(name, source).trim().to_owned());
        }
        let mut cursor = node.walk();
        for child in node.named_children(&mut cursor) {
            collect(child, source, names);
        }
    }

    let mut names = HashSet::new();
    collect(root, source, &mut names);
    names
}

fn swift_extension_specification_type_names(
    root: Node<'_>,
    source: &[u8],
    nominal_types: &HashSet<String>,
) -> HashSet<String> {
    fn collect(
        node: Node<'_>,
        source: &[u8],
        nominal_types: &HashSet<String>,
        marked_types: &mut HashSet<String>,
    ) {
        if swift_specification_extension(node, source)
            && let Some(name) = node.child_by_field_name("name")
        {
            let name = node_text(name, source).trim();
            if nominal_types.contains(name) {
                marked_types.insert(name.to_owned());
            }
        }
        let mut cursor = node.walk();
        for child in node.named_children(&mut cursor) {
            collect(child, source, nominal_types, marked_types);
        }
    }

    let mut marked_types = HashSet::new();
    collect(root, source, nominal_types, &mut marked_types);
    marked_types
}

fn is_swift_marker_protocol(text: &str) -> bool {
    // Keep this Swift-specific: the similarly named Rust marker form is not
    // implemented yet, and qualified names could refer to another module.
    text.trim() == "SpecificationMetricV1"
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
    fn python_typed_marker_counts_class_and_ignores_its_internal_branches() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("policy.py"),
            "from dataclasses import dataclass\nfrom typing import ClassVar, Literal\n\n@dataclass\nclass _MarkedRule:\n    __specmetrics_specification__: ClassVar[Literal[\"specification/v1\"]] = (\n        \"specification/v1\"\n    )\n\n    def accepts(self, value):\n        if value:\n            return True\n        return False\n\nif unrelated:\n    pass\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        assert!(
            report.marker_issues.is_empty(),
            "{:?}",
            report.marker_issues
        );
        assert_eq!(report.specifications.len(), 1);
        assert_eq!(report.specifications[0].name, "_MarkedRule");
        assert_eq!(report.specifications[0].kind, "declaration");
        assert_eq!(report.candidates.len(), 2);
        assert!(report.candidates[0].inside_specification);
        assert!(!report.candidates[1].inside_specification);
    }

    #[test]
    fn python_marker_does_not_duplicate_a_native_specification() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("policy.py"),
            "from typing import ClassVar, Literal\nclass _MarkedRule(Specification):\n    __specmetrics_specification__: ClassVar[Literal['specification/v1']] = 'specification/v1'\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(
            report.marker_issues.is_empty(),
            "{:?}",
            report.marker_issues
        );
        assert_eq!(report.specifications.len(), 1);
    }

    #[test]
    fn invalid_python_marker_is_reported_and_makes_live_metric_provisional() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("policy.py"),
            "class _Unmarked:\n    __specmetrics_specification__ = True\n    if internal: pass\nif outside: pass\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.specifications.is_empty());
        assert_eq!(report.marker_issues.len(), 1);
        assert!(
            report.marker_issues[0]
                .message
                .contains("expected ClassVar")
        );
        assert!(
            report
                .candidates
                .iter()
                .all(|candidate| !candidate.inside_specification)
        );
        let metric = crate::live::measure(&report, None).unwrap();
        assert!(metric.provisional);
        assert_eq!(metric.marker_issues.len(), 1);
    }

    #[test]
    fn python_marker_declaration_uses_existing_liveness_rules() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("rules.py"),
            "from typing import ClassVar, Literal\nclass _MarkedRule:\n    __specmetrics_specification__: ClassVar[Literal[\"specification/v1\"]] = \"specification/v1\"\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("consumer.py"),
            "from rules import _MarkedRule\ndef evaluate():\n    return _MarkedRule()\n",
        )
        .unwrap();
        let scope = ScopeManifest::parse(
            "schema_version=1\n[liveness]\nclosed_world=true\n[[source_sets]]\nrole='application'\npaths=['.']\n",
        )
        .unwrap();

        let report = scan_with_scope(dir.path(), &[], Some(&scope)).unwrap();
        assert!(
            report.marker_issues.is_empty(),
            "{:?}",
            report.marker_issues
        );
        assert_eq!(report.specification_liveness.len(), 1);
        assert_eq!(
            report.specification_liveness[0].status,
            crate::model::SpecificationLivenessStatus::Live
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
    fn swift_marker_protocol_counts_direct_and_extension_conformances() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.swift"),
            "protocol SpecificationMetricV1 {}\nstruct DirectRule: SpecificationMetricV1 {\n    func accepts(_ value: Int) -> Bool {\n        if value > 0 { return true }\n        return false\n    }\n}\nstruct ExtendedRule {\n    func other(_ value: Int) -> Bool {\n        if value > 0 { return true }\n        return false\n    }\n}\nextension ExtendedRule: SpecificationMetricV1 {\n    func accepts(_ value: Int) -> Bool {\n        guard value > 0 else { return false }\n        return true\n    }\n}\nif unrelated { print(unrelated) }\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        assert_eq!(report.specifications.len(), 2);
        assert_eq!(
            report
                .specifications
                .iter()
                .map(|specification| specification.name.as_str())
                .collect::<Vec<_>>(),
            ["DirectRule", "ExtendedRule"]
        );
        assert_eq!(report.candidates.len(), 4);
        assert!(report.candidates[0].inside_specification);
        assert!(report.candidates[1].inside_specification);
        assert!(report.candidates[2].inside_specification);
        assert!(!report.candidates[3].inside_specification);
        assert_eq!(report.specification_liveness.len(), 2);
        assert!(
            report.specification_liveness.iter().all(|entry| {
                entry.status == crate::model::SpecificationLivenessStatus::Unknown
            })
        );
    }

    #[test]
    fn swift_marker_conformance_does_not_duplicate_native_specification() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.swift"),
            "struct MarkedRule: Specification {}\nextension MarkedRule: SpecificationMetricV1 {}\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert_eq!(report.specifications.len(), 1);
        assert_eq!(report.specifications[0].name, "MarkedRule");
    }

    #[test]
    fn swift_qualified_marker_name_is_not_the_reserved_local_protocol() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.swift"),
            "struct ExternalMarkerRule: OtherModule.SpecificationMetricV1 {}\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.specifications.is_empty());
    }

    #[test]
    fn swift_marker_extension_requires_a_local_nominal_type() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.swift"),
            "extension ImportedRule: SpecificationMetricV1 {}\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.specifications.is_empty());
        assert_eq!(report.marker_issues.len(), 1);
        assert!(
            report.marker_issues[0]
                .message
                .contains("declared in the same source file")
        );
    }

    #[test]
    fn rust_marker_trait_counts_local_struct_and_enum_once_and_covers_inherent_impls() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.rs"),
            include_str!("../tests/fixtures/markers/rust/SpecificationMetric.rs"),
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        assert!(
            report.marker_issues.is_empty(),
            "{:?}",
            report.marker_issues
        );
        assert_eq!(report.specifications.len(), 3);
        assert_eq!(report.specifications[0].name, "MarkedResponseSpec");
        assert_eq!(report.specifications[1].name, "AlternateResponseSpec");
        assert_eq!(report.specifications[2].name, "QualifiedResponseSpec");
        assert_eq!(report.candidates.len(), 4);
        assert!(report.candidates[0].inside_specification);
        assert!(report.candidates[1].inside_specification);
        assert!(report.candidates[2].inside_specification);
        assert!(!report.candidates[3].inside_specification);
        assert!(
            report.specification_liveness.iter().all(|entry| {
                entry.status == crate::model::SpecificationLivenessStatus::Unknown
            })
        );
    }

    #[test]
    fn rust_marker_resolves_crate_paths_and_rejects_unresolved_symbols() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.rs"),
            "trait SpecificationMetricV1 {}\nstruct LocalRule;\nmod unrelated { pub trait Other {} pub struct Rule; }\nimpl unrelated::Other for LocalRule {}\nimpl SpecificationMetricV1 for ImportedRule {}\nimpl SpecificationMetricV1 for unrelated::Rule {}\nimpl crate::SpecificationMetricV1 for LocalRule {}\n",
        )
        .unwrap();

        let scope = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n",
        )
        .unwrap();
        let report = scan_with_scope(dir.path(), &[], Some(&scope)).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        assert_eq!(report.specifications.len(), 2);
        assert_eq!(report.specifications[0].name, "LocalRule");
        assert_eq!(report.specifications[1].name, "Rule");
        assert_eq!(report.marker_issues.len(), 1);
        assert!(report.marker_issues.iter().all(|issue| {
            issue
                .message
                .contains("must resolve to a declared marker trait")
        }));
        let metric = crate::live::measure(&report, None).unwrap();
        assert!(metric.provisional);
    }

    #[test]
    fn rust_marker_resolves_external_module_paths_and_excludes_type_subtree() {
        let dir = tempdir().unwrap();
        let src = dir.path().join("src");
        fs::create_dir_all(&src).unwrap();
        fs::write(
            src.join("lib.rs"),
            "pub(crate) mod marker;\nmod rules;\npub(crate) mod types;\nmod nested { pub struct NestedReady; impl super::marker::SpecificationMetricV1 for crate::nested::NestedReady {} impl NestedReady { fn accepts(value: bool) -> bool { if value { true } else { false } } } }\n",
        )
        .unwrap();
        fs::write(
            src.join("marker.rs"),
            "pub(crate) trait SpecificationMetricV1 {}\n",
        )
        .unwrap();
        fs::write(
            src.join("types.rs"),
            "pub(crate) trait Specification<T> {}\npub(crate) trait Other {}\npub(crate) struct Ready;\nimpl Ready { fn accepts(value: bool) -> bool { if value { true } else { false } } }\nimpl Other for Ready { fn unrelated(value: bool) { if value {} else {} } }\n",
        )
        .unwrap();
        fs::write(
            src.join("rules.rs"),
            "impl crate::marker::SpecificationMetricV1 for crate::types::Ready {}\nimpl crate::types::Specification<bool> for crate::types::Ready {}\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.parse_issues.is_empty(), "{:?}", report.parse_issues);
        assert!(
            report.marker_issues.is_empty(),
            "{:?}",
            report.marker_issues
        );
        assert_eq!(report.specifications.len(), 2);
        let mut names = report
            .specifications
            .iter()
            .map(|specification| specification.name.as_str())
            .collect::<Vec<_>>();
        names.sort_unstable();
        assert_eq!(names, ["NestedReady", "Ready"]);
        assert_eq!(report.candidates.len(), 3);
        assert_eq!(
            report
                .candidates
                .iter()
                .filter(|candidate| candidate.inside_specification)
                .count(),
            2
        );
        assert!(
            report
                .candidates
                .iter()
                .any(|candidate| !candidate.inside_specification)
        );
    }

    #[test]
    fn rust_shared_module_file_keeps_each_crate_resolution_stable() {
        let dir = tempdir().unwrap();
        let src = dir.path().join("src");
        fs::create_dir_all(&src).unwrap();
        fs::write(
            src.join("lib.rs"),
            "trait SpecificationMetricV1 {}\nmod shared;\nimpl SpecificationMetricV1 for shared::Rule {}\n",
        )
        .unwrap();
        fs::write(src.join("main.rs"), "mod shared;\n").unwrap();
        fs::write(src.join("shared.rs"), "pub struct Rule;\n").unwrap();

        let reports = (0..5)
            .map(|_| scan(dir.path(), &[]).unwrap())
            .collect::<Vec<_>>();
        assert!(reports.iter().all(|report| {
            report.specifications.len() == 1
                && report.specifications[0].name == "Rule"
                && report.marker_issues.is_empty()
        }));
    }

    #[test]
    fn rust_deduplication_keeps_same_named_types_in_distinct_modules() {
        let dir = tempdir().unwrap();
        let src = dir.path().join("src");
        fs::create_dir_all(&src).unwrap();
        fs::write(
            src.join("lib.rs"),
            "trait SpecificationMetricV1 {}\ntrait Specification<T> {}\nmod a;\nmod b;\n",
        )
        .unwrap();
        fs::write(
            src.join("a.rs"),
            "pub struct Rule;\nimpl crate::SpecificationMetricV1 for Rule {}\n",
        )
        .unwrap();
        fs::write(
            src.join("b.rs"),
            "pub struct Rule;\nimpl crate::Specification<bool> for Rule {}\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert_eq!(report.specifications.len(), 2);
        assert!(report.marker_issues.is_empty());
    }

    #[test]
    fn rust_marker_does_not_guess_custom_path_module_ownership() {
        let dir = tempdir().unwrap();
        let src = dir.path().join("src");
        fs::create_dir_all(&src).unwrap();
        fs::write(
            src.join("lib.rs"),
            "trait SpecificationMetricV1 {}\n#[path = \"custom.rs\"] mod rules;\n",
        )
        .unwrap();
        fs::write(
            src.join("custom.rs"),
            "struct Rule;\nimpl SpecificationMetricV1 for Rule {}\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.specifications.is_empty());
        assert_eq!(report.marker_issues.len(), 1);
        assert!(crate::live::measure(&report, None).unwrap().provisional);
    }

    #[test]
    fn rust_marker_trait_declaration_alone_is_not_a_specification() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("example.rs"),
            "trait SpecificationMetricV1 {}\nstruct UnmarkedRule;\n",
        )
        .unwrap();

        let report = scan(dir.path(), &[]).unwrap();
        assert!(report.specifications.is_empty());
        assert!(report.marker_issues.is_empty());
    }

    #[test]
    fn rust_marker_implementation_in_test_sources_does_not_count() {
        let dir = tempdir().unwrap();
        fs::create_dir_all(dir.path().join("app")).unwrap();
        fs::write(dir.path().join("app/main.rs"), "// application source\n").unwrap();
        fs::create_dir_all(dir.path().join("tests")).unwrap();
        fs::write(
            dir.path().join("tests/marker.rs"),
            "trait SpecificationMetricV1 {}\nstruct TestOnlyRule;\nimpl SpecificationMetricV1 for TestOnlyRule {}\nimpl TestOnlyRule { fn check(value: bool) { if value {} } }\n",
        )
        .unwrap();
        let scope = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['app']\n[[source_sets]]\nrole='test'\npaths=['tests']\n",
        )
        .unwrap();

        let report = scan_with_scope(dir.path(), &[], Some(&scope)).unwrap();
        assert!(report.scope_issues.is_empty(), "{:?}", report.scope_issues);
        assert!(report.specifications.is_empty());
        assert!(report.marker_issues.is_empty());
        assert!(report.candidates.is_empty());
        assert_eq!(report.excluded_files, 1);
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
            "from typing import ClassVar, Literal\nclass Ready:\n    __specmetrics_specification__: ClassVar[Literal[\"specification/v1\"]] = \"specification/v1\"\n    def accepts(self, x):\n        if x: return True\nif business: pass\n",
        )
        .unwrap();
        for directory in ["vendor", "tests", "generated"] {
            fs::write(
                dir.path().join(directory).join("other.py"),
                "from typing import ClassVar, Literal\nclass Other:\n    __specmetrics_specification__: ClassVar[Literal[\"specification/v1\"]] = \"specification/v1\"\nif ignored: pass\n",
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

    #[test]
    fn explicit_file_and_directory_exclusions_remove_both_counts() {
        let dir = tempdir().unwrap();
        fs::create_dir(dir.path().join("app")).unwrap();
        fs::create_dir_all(dir.path().join("old/nested")).unwrap();
        fs::write(
            dir.path().join("app/current.py"),
            "class Current(Specification): pass\nif active: pass\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("app/legacy.py"),
            "class Legacy(Specification): pass\nif legacy: pass\n",
        )
        .unwrap();
        fs::write(
            dir.path().join("old/nested/another.py"),
            "class Old(Specification): pass\nif old: pass\n",
        )
        .unwrap();
        let manifest = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='excluded'\npaths=['app/legacy.py', 'old']\nreason='Reviewed outside adoption scope'\n",
        )
        .unwrap();
        let report = scan_with_scope(dir.path(), &[], Some(&manifest)).unwrap();
        assert!(report.scope_issues.is_empty());
        assert_eq!(report.application_files, 1);
        assert_eq!(report.excluded_files, 2);
        assert_eq!(report.specifications.len(), 1);
        assert_eq!(report.specifications[0].name, "Current");
        assert_eq!(report.candidates.len(), 1);
        assert_eq!(report.candidates[0].path, "app/current.py");
    }
}
