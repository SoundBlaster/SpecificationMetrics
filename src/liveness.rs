use std::collections::{HashMap, HashSet};

use tree_sitter::{Node, Parser, Tree};

use crate::model::{
    Language, SpecificationDefinition, SpecificationLiveness, SpecificationLivenessStatus,
};

pub struct PythonSource {
    pub path: String,
    pub source: String,
}

struct ParsedPythonSource {
    path: String,
    module: String,
    source: String,
    tree: Tree,
}

pub fn classify(
    definitions: &[SpecificationDefinition],
    python_sources: &[PythonSource],
    closed_world: bool,
    incomplete: bool,
) -> Vec<SpecificationLiveness> {
    let python = PythonLiveness::new(python_sources, definitions);
    definitions
        .iter()
        .map(|definition| {
            let (status, evidence) = if definition.kind == "factory" {
                (
                    SpecificationLivenessStatus::Live,
                    "factory site is counted by source presence".to_owned(),
                )
            } else if definition.language != Language::Python {
                (
                    SpecificationLivenessStatus::Unknown,
                    "liveness analysis is not implemented for this language".to_owned(),
                )
            } else if incomplete {
                (
                    SpecificationLivenessStatus::Unknown,
                    "source parse or role assignment is incomplete".to_owned(),
                )
            } else {
                python.classify(definition, definitions, closed_world)
            };
            SpecificationLiveness {
                language: definition.language,
                path: definition.path.clone(),
                name: definition.name.clone(),
                kind: definition.kind.clone(),
                line: definition.line,
                column: definition.column,
                status,
                evidence,
            }
        })
        .collect()
}

struct PythonLiveness {
    sources: Vec<ParsedPythonSource>,
    definitions_by_module: HashMap<(String, String), Vec<usize>>,
    parse_failed: HashSet<String>,
    dynamic_lookup: bool,
}

impl PythonLiveness {
    fn new(sources: &[PythonSource], definitions: &[SpecificationDefinition]) -> Self {
        let mut parser = Parser::new();
        parser
            .set_language(&tree_sitter_python::LANGUAGE.into())
            .expect("tree-sitter Python language is valid");
        let mut parsed_sources = Vec::new();
        let mut parse_failed = HashSet::new();
        let mut dynamic_lookup = false;
        for source in sources {
            let Some(tree) = parser.parse(&source.source, None) else {
                parse_failed.insert(source.path.clone());
                continue;
            };
            if tree.root_node().has_error() {
                parse_failed.insert(source.path.clone());
            }
            dynamic_lookup |= contains_dynamic_lookup(tree.root_node(), &source.source);
            parsed_sources.push(ParsedPythonSource {
                module: module_name(&source.path),
                path: source.path.clone(),
                source: source.source.clone(),
                tree,
            });
        }
        let mut definitions_by_module = HashMap::new();
        for (index, definition) in definitions.iter().enumerate() {
            if definition.language == Language::Python && definition.kind == "declaration" {
                definitions_by_module
                    .entry((module_name(&definition.path), definition.name.clone()))
                    .or_insert_with(Vec::new)
                    .push(index);
            }
        }
        Self {
            sources: parsed_sources,
            definitions_by_module,
            parse_failed,
            dynamic_lookup,
        }
    }

    fn classify(
        &self,
        definition: &SpecificationDefinition,
        definitions: &[SpecificationDefinition],
        closed_world: bool,
    ) -> (SpecificationLivenessStatus, String) {
        if self.parse_failed.contains(&definition.path) {
            return (
                SpecificationLivenessStatus::Unknown,
                "the declaration's source has a parse error".to_owned(),
            );
        }
        let module = module_name(&definition.path);
        let declaration_index = definitions
            .iter()
            .position(|item| {
                item.language == Language::Python
                    && item.path == definition.path
                    && item.name == definition.name
                    && item.kind == definition.kind
                    && item.line == definition.line
                    && item.column == definition.column
            })
            .expect("definition came from the same definition list");
        let own_symbol_count = self
            .definitions_by_module
            .get(&(module.clone(), definition.name.clone()))
            .map_or(0, Vec::len);
        if own_symbol_count != 1 {
            return (
                SpecificationLivenessStatus::Unknown,
                "the Python symbol is ambiguous within its module".to_owned(),
            );
        }

        let mut direct_use = false;
        let mut ambiguous_use = false;
        for source in &self.sources {
            let aliases = self.aliases_for(source);
            ambiguous_use |= unresolved_import_may_match(
                source.tree.root_node(),
                &source.path,
                &source.source,
                &self.definitions_by_module,
                definition,
            );
            let local_indices = aliases.values().flatten().copied().collect::<HashSet<_>>();
            if !local_indices.contains(&declaration_index) {
                continue;
            }
            let mut inspection = ReferenceInspection {
                source: &source.source,
                aliases: &aliases,
                target: declaration_index,
                direct_use: &mut direct_use,
                ambiguous_use: &mut ambiguous_use,
            };
            inspect_runtime_references(
                source.tree.root_node(),
                None,
                None,
                false,
                false,
                &mut inspection,
            );
        }
        if direct_use {
            return (
                SpecificationLivenessStatus::Live,
                "resolved constructor or Specification consumer use".to_owned(),
            );
        }
        if ambiguous_use || self.dynamic_lookup {
            return (
                SpecificationLivenessStatus::Unknown,
                "an unresolved runtime reference or dynamic lookup may use this declaration"
                    .to_owned(),
            );
        }
        if !definition.name.starts_with('_') || exported_from_package(definition, &self.sources) {
            return (
                SpecificationLivenessStatus::Unknown,
                "the declaration is importable or exported outside its source module".to_owned(),
            );
        }
        if !closed_world {
            return (
                SpecificationLivenessStatus::Unknown,
                "the manifest does not declare a closed-world source boundary".to_owned(),
            );
        }
        (
            SpecificationLivenessStatus::Dead,
            "private declaration has no resolved runtime use in the closed source set".to_owned(),
        )
    }

    fn aliases_for(&self, source: &ParsedPythonSource) -> HashMap<String, Vec<usize>> {
        let mut aliases: HashMap<String, Vec<usize>> = HashMap::new();
        for ((module, name), indices) in &self.definitions_by_module {
            if module == &source.module {
                aliases.entry(name.clone()).or_default().extend(indices);
            }
        }
        collect_imports(
            source.tree.root_node(),
            &source.path,
            &source.source,
            &self.definitions_by_module,
            &mut aliases,
        );
        aliases
    }
}

fn module_name(path: &str) -> String {
    let path = path.strip_prefix("src/").unwrap_or(path);
    let module = path.strip_suffix(".py").unwrap_or(path);
    let module = module.strip_suffix("/__init__").unwrap_or(module);
    module.replace('/', ".")
}

fn collect_imports(
    node: Node<'_>,
    source_path: &str,
    source: &str,
    definitions_by_module: &HashMap<(String, String), Vec<usize>>,
    aliases: &mut HashMap<String, Vec<usize>>,
) {
    if node.kind() == "import_from_statement"
        && let Some(module_node) = node.child_by_field_name("module_name")
    {
        let imported_module = resolve_import_module(
            source_path,
            module_node.utf8_text(source.as_bytes()).unwrap_or_default(),
        );
        let mut cursor = node.walk();
        for imported in node.children_by_field_name("name", &mut cursor) {
            if imported.kind() == "wildcard_import" {
                aliases.entry("*".to_owned()).or_default().extend(
                    definitions_by_module
                        .iter()
                        .filter(|((module, _), _)| module == &imported_module)
                        .flat_map(|(_, indices)| indices.iter().copied()),
                );
                continue;
            }
            let (symbol, local) = if imported.kind() == "aliased_import" {
                (
                    imported
                        .child_by_field_name("name")
                        .map(|child| {
                            child
                                .utf8_text(source.as_bytes())
                                .unwrap_or_default()
                                .to_owned()
                        })
                        .unwrap_or_default(),
                    imported
                        .child_by_field_name("alias")
                        .map(|child| {
                            child
                                .utf8_text(source.as_bytes())
                                .unwrap_or_default()
                                .to_owned()
                        })
                        .unwrap_or_default(),
                )
            } else {
                let symbol = imported
                    .utf8_text(source.as_bytes())
                    .unwrap_or_default()
                    .to_owned();
                (
                    symbol.clone(),
                    symbol.rsplit('.').next().unwrap_or(&symbol).to_owned(),
                )
            };
            if symbol.is_empty() || local.is_empty() {
                continue;
            }
            if let Some(indices) = definitions_by_module.get(&(imported_module.clone(), symbol)) {
                aliases.entry(local).or_default().extend(indices);
            }
        }
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_imports(child, source_path, source, definitions_by_module, aliases);
    }
}

fn resolve_import_module(source_path: &str, import: &str) -> String {
    let dots = import
        .chars()
        .take_while(|character| *character == '.')
        .count();
    let suffix = import.trim_start_matches('.').replace('.', "/");
    if dots == 0 {
        return import.to_owned();
    }
    let module_path = source_path.strip_prefix("src/").unwrap_or(source_path);
    let module_path = module_path.strip_suffix(".py").unwrap_or(module_path);
    let mut package = module_path.split('/').collect::<Vec<_>>();
    package.pop();
    for _ in 1..dots {
        package.pop();
    }
    if !suffix.is_empty() {
        package.extend(suffix.split('/'));
    }
    package.join(".")
}

fn unresolved_import_may_match(
    node: Node<'_>,
    source_path: &str,
    source: &str,
    definitions_by_module: &HashMap<(String, String), Vec<usize>>,
    target: &SpecificationDefinition,
) -> bool {
    if node.kind() == "wildcard_import" {
        return true;
    }
    let target_module = module_name(&target.path);
    if node.kind() == "import_statement" {
        let mut cursor = node.walk();
        for imported in node.named_children(&mut cursor) {
            let imported = imported.utf8_text(source.as_bytes()).unwrap_or_default();
            let imported = imported.split_whitespace().next().unwrap_or(imported);
            if target_module == imported || target_module.starts_with(&format!("{imported}.")) {
                return true;
            }
        }
    }
    if node.kind() == "import_from_statement"
        && let Some(module_node) = node.child_by_field_name("module_name")
    {
        let imported_module = module_node.utf8_text(source.as_bytes()).unwrap_or_default();
        let resolved = resolve_import_module(source_path, imported_module);
        let mut cursor = node.walk();
        for imported in node.children_by_field_name("name", &mut cursor) {
            if imported.kind() == "wildcard_import" {
                return true;
            }
            let name = if imported.kind() == "aliased_import" {
                imported
                    .child_by_field_name("name")
                    .and_then(|child| child.utf8_text(source.as_bytes()).ok())
                    .unwrap_or_default()
            } else {
                imported.utf8_text(source.as_bytes()).unwrap_or_default()
            };
            if name == target.name
                && !definitions_by_module.contains_key(&(resolved.clone(), name.to_owned()))
                && definitions_by_module
                    .keys()
                    .any(|(_, candidate)| candidate == name)
            {
                return true;
            }
            let target_parent = target_module.rsplit_once('.').map(|(parent, _)| parent);
            if target_module.rsplit('.').next() == Some(name)
                && target_parent == Some(resolved.as_str())
            {
                return true;
            }
        }
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor).any(|child| {
        unresolved_import_may_match(child, source_path, source, definitions_by_module, target)
    })
}

struct ReferenceInspection<'a> {
    source: &'a str,
    aliases: &'a HashMap<String, Vec<usize>>,
    target: usize,
    direct_use: &'a mut bool,
    ambiguous_use: &'a mut bool,
}

fn inspect_runtime_references(
    node: Node<'_>,
    parent: Option<Node<'_>>,
    grandparent: Option<Node<'_>>,
    in_type: bool,
    in_import: bool,
    inspection: &mut ReferenceInspection<'_>,
) {
    if inspection
        .aliases
        .get("*")
        .is_some_and(|indices| indices.contains(&inspection.target))
    {
        *inspection.ambiguous_use = true;
    }
    let node_is_type = in_type
        || node.kind() == "type"
        || parent.is_some_and(|parent| {
            ["type", "return_type", "type_parameters"]
                .iter()
                .any(|field| parent.child_by_field_name(field) == Some(node))
        });
    let node_is_import =
        in_import || node.kind() == "import_from_statement" || node.kind() == "import_statement";
    if node.kind() == "identifier" && !node_is_type && !node_is_import {
        let name = node
            .utf8_text(inspection.source.as_bytes())
            .unwrap_or_default();
        let is_declaration_name = parent.is_some_and(|parent| {
            parent.kind() == "class_definition" && parent.child_by_field_name("name") == Some(node)
        });
        if !is_declaration_name
            && let Some(indices) = inspection.aliases.get(name)
            && indices.contains(&inspection.target)
        {
            let parent = parent.expect("identifier has parent");
            let called =
                parent.kind() == "call" && parent.child_by_field_name("function") == Some(node);
            let consumed = parent.kind() == "argument_list"
                && grandparent.is_some_and(|call| {
                    call.kind() == "call"
                        && call.child_by_field_name("arguments") == Some(parent)
                        && call
                            .child_by_field_name("function")
                            .is_some_and(|function| {
                                is_specification_consumer(
                                    function
                                        .utf8_text(inspection.source.as_bytes())
                                        .unwrap_or_default(),
                                )
                            })
                });
            if called || consumed {
                *inspection.direct_use = true;
            } else {
                *inspection.ambiguous_use = true;
            }
        }
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        inspect_runtime_references(
            child,
            Some(node),
            parent,
            node_is_type,
            node_is_import,
            inspection,
        );
    }
}

fn is_specification_consumer(function: &str) -> bool {
    let name = function.rsplit('.').next().unwrap_or(function);
    matches!(
        name,
        "evaluate"
            | "is_satisfied_by"
            | "is_satisfied"
            | "matches"
            | "and"
            | "or"
            | "not"
            | "all_of"
            | "any_of"
            | "compose"
            | "register"
            | "register_factory"
    )
}

fn contains_dynamic_lookup(node: Node<'_>, source: &str) -> bool {
    if node.kind() == "call"
        && let Some(function) = node.child_by_field_name("function")
    {
        let name = function.utf8_text(source.as_bytes()).unwrap_or_default();
        let name = name.rsplit('.').next().unwrap_or(name);
        if matches!(
            name,
            "getattr" | "globals" | "locals" | "eval" | "exec" | "__import__" | "import_module"
        ) {
            return true;
        }
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| contains_dynamic_lookup(child, source))
}

fn exported_from_package(
    definition: &SpecificationDefinition,
    sources: &[ParsedPythonSource],
) -> bool {
    let module = module_name(&definition.path);
    let package = module.rsplit_once('.').map(|(parent, _)| parent);
    let Some(source) = sources.iter().find(|source| {
        source.module == module || package.is_some_and(|package| source.module == package)
    }) else {
        return false;
    };
    source.source.contains("__all__")
        && (source.source.contains(&format!("\"{}\"", definition.name))
            || source.source.contains(&format!("'{}'", definition.name)))
}

#[cfg(test)]
mod tests {
    use std::fs;

    use serde::Deserialize;

    use crate::model::{Language, SpecificationDefinition, SpecificationLivenessStatus};
    use crate::scan::scan_with_scope;
    use crate::scope::ScopeManifest;

    #[derive(Deserialize)]
    struct FixtureSet {
        cases: Vec<FixtureCase>,
    }

    #[derive(Deserialize)]
    struct FixtureCase {
        id: String,
        language: String,
        status: String,
        world: String,
        files: Vec<String>,
    }

    #[test]
    fn factory_sites_remain_live_without_declaration_analysis() {
        let definitions = [Language::Python, Language::Swift, Language::Rust].map(|language| {
            SpecificationDefinition {
                language,
                path: "src/factory".to_owned(),
                name: "FirstMatchSpec".to_owned(),
                kind: "factory".to_owned(),
                line: 1,
                column: 1,
            }
        });

        let results = super::classify(&definitions, &[], false, true);
        assert!(
            results
                .iter()
                .all(|result| result.status == SpecificationLivenessStatus::Live)
        );
    }

    #[test]
    fn python_liveness_matches_versioned_acceptance_fixtures() {
        let fixture_root =
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/liveness/v1");
        let manifest: FixtureSet =
            serde_json::from_slice(&fs::read(fixture_root.join("cases.json")).unwrap()).unwrap();

        for case in manifest.cases {
            for file in &case.files {
                assert!(fixture_root.join(file).is_file(), "{}: {file}", case.id);
            }
            let (language, case_name) = case.id.split_once('.').unwrap();
            let case_root = fixture_root.join(language).join(case_name);
            let closed_world = case.world == "closed";
            let scope = ScopeManifest::parse(&format!(
                "schema_version=1\n[liveness]\nclosed_world={closed_world}\n[[source_sets]]\nrole='application'\npaths=['.']\n"
            ))
            .unwrap();
            let report = scan_with_scope(&case_root, &[], Some(&scope)).unwrap();
            assert!(
                report.parse_issues.is_empty(),
                "{}: {:?}",
                case.id,
                report.parse_issues
            );
            assert_eq!(report.specification_liveness.len(), 1, "{}", case.id);
            let actual = report.specification_liveness[0].status;
            let expected = if case.language == "python" {
                match case.status.as_str() {
                    "live" => SpecificationLivenessStatus::Live,
                    "dead" => SpecificationLivenessStatus::Dead,
                    "unknown" => SpecificationLivenessStatus::Unknown,
                    status => panic!("unsupported status in fixture {}: {status}", case.id),
                }
            } else {
                SpecificationLivenessStatus::Unknown
            };
            assert_eq!(actual, expected, "{}", case.id);

            let metric = crate::live::measure(&report, None).unwrap();
            match actual {
                SpecificationLivenessStatus::Live => {
                    assert_eq!(metric.specification_definitions, 1, "{}", case.id);
                    assert_eq!(metric.live_specifications, 1, "{}", case.id);
                    assert!(!metric.provisional, "{}", case.id);
                }
                SpecificationLivenessStatus::Dead => {
                    assert_eq!(metric.specification_definitions, 0, "{}", case.id);
                    assert_eq!(metric.dead_specifications, 1, "{}", case.id);
                    assert_eq!(metric.remaining_opportunities, 1, "{}", case.id);
                    assert_eq!(metric.ratio, Some(0.0), "{}", case.id);
                    assert!(!metric.provisional, "{}", case.id);
                }
                SpecificationLivenessStatus::Unknown => {
                    assert_eq!(metric.specification_definitions, 1, "{}", case.id);
                    assert_eq!(metric.unknown_specifications, 1, "{}", case.id);
                    assert!(metric.provisional, "{}", case.id);
                }
            }
        }
    }
}
