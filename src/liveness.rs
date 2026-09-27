use std::collections::{HashMap, HashSet};

use tree_sitter::{Node, Parser, Tree};

use crate::model::{
    Language, SpecificationDefinition, SpecificationLiveness, SpecificationLivenessStatus,
};

pub struct PythonSource {
    pub path: String,
    pub source: String,
}

#[derive(Clone)]
pub struct RustModuleAssignment {
    pub crate_root: String,
    pub module_path: Vec<String>,
}

pub struct RustSource {
    pub path: String,
    pub source: String,
    pub assignments: Vec<RustModuleAssignment>,
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
    rust_sources: &[RustSource],
    closed_world: bool,
    incomplete: bool,
) -> Vec<SpecificationLiveness> {
    let python = PythonLiveness::new(python_sources, definitions);
    let rust = RustLiveness::new(rust_sources);
    definitions
        .iter()
        .map(|definition| {
            let (status, evidence) = if definition.kind == "factory" {
                (
                    SpecificationLivenessStatus::Live,
                    "factory site is counted by source presence".to_owned(),
                )
            } else if definition.language == Language::Rust {
                if incomplete {
                    (
                        SpecificationLivenessStatus::Unknown,
                        "source parse or role assignment is incomplete".to_owned(),
                    )
                } else {
                    rust.classify(definition, closed_world)
                }
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

struct ParsedRustSource {
    path: String,
    source: String,
    tree: Tree,
    assignments: Vec<RustModuleAssignment>,
}

struct RustLiveness {
    sources: Vec<ParsedRustSource>,
    parse_failed: HashSet<String>,
}

impl RustLiveness {
    fn new(sources: &[RustSource]) -> Self {
        let mut parser = Parser::new();
        parser
            .set_language(&tree_sitter_rust::LANGUAGE.into())
            .expect("tree-sitter Rust language is valid");
        let mut parsed = Vec::new();
        let mut parse_failed = HashSet::new();
        for source in sources {
            let Some(tree) = parser.parse(&source.source, None) else {
                parse_failed.insert(source.path.clone());
                continue;
            };
            if tree.root_node().has_error() {
                parse_failed.insert(source.path.clone());
            }
            parsed.push(ParsedRustSource {
                path: source.path.clone(),
                source: source.source.clone(),
                tree,
                assignments: source.assignments.clone(),
            });
        }
        Self {
            sources: parsed,
            parse_failed,
        }
    }

    fn classify(
        &self,
        definition: &SpecificationDefinition,
        closed_world: bool,
    ) -> (SpecificationLivenessStatus, String) {
        if self.parse_failed.contains(&definition.path) {
            return (
                SpecificationLivenessStatus::Unknown,
                "the declaration's source has a parse error".to_owned(),
            );
        }
        let Some(declaration_source) = self
            .sources
            .iter()
            .find(|source| source.path == definition.path)
        else {
            return (
                SpecificationLivenessStatus::Unknown,
                "the Rust declaration has no resolved crate or module owner".to_owned(),
            );
        };
        let type_name = rust_type_name(&definition.name);
        let assignments = declaration_source
            .assignments
            .iter()
            .filter_map(|assignment| {
                rust_definition_module(
                    declaration_source.tree.root_node(),
                    declaration_source.source.as_bytes(),
                    definition.line,
                    type_name,
                    &assignment.module_path,
                )
                .map(|module_path| RustModuleAssignment {
                    crate_root: assignment.crate_root.clone(),
                    module_path,
                })
            })
            .collect::<Vec<_>>();
        if assignments.is_empty() {
            return (
                SpecificationLivenessStatus::Unknown,
                "the Rust declaration has no resolved crate or module owner".to_owned(),
            );
        }
        if assignments.len() > 1 {
            return (
                SpecificationLivenessStatus::Unknown,
                "the Rust declaration belongs to multiple or ambiguous crate modules".to_owned(),
            );
        }
        let assignment = &assignments[0];
        let mut direct_use = false;
        let mut uncertain_use = false;
        let mut same_name_symbols = 0usize;
        for source in self.sources.iter().filter(|source| {
            source
                .assignments
                .iter()
                .any(|candidate| candidate.crate_root == assignment.crate_root)
        }) {
            let mut cursor = source.tree.root_node().walk();
            for node in source.tree.root_node().named_children(&mut cursor) {
                count_rust_type_declarations(
                    node,
                    source.source.as_bytes(),
                    type_name,
                    &mut same_name_symbols,
                );
            }
        }
        for source in self.sources.iter().filter(|source| {
            source
                .assignments
                .iter()
                .any(|candidate| candidate.crate_root == assignment.crate_root)
        }) {
            for source_assignment in source
                .assignments
                .iter()
                .filter(|candidate| candidate.crate_root == assignment.crate_root)
            {
                let imported_aliases = rust_import_aliases(
                    source.tree.root_node(),
                    source.source.as_bytes(),
                    &assignment.module_path.join("::"),
                    type_name,
                );
                let mut inspection = RustReferenceInspection {
                    source,
                    target_path: assignment.module_path.join("::"),
                    type_name,
                    imported_aliases,
                    declaration_line: definition.line,
                    declaration_path: &definition.path,
                    declaration_module: &assignment.module_path,
                    ambiguous_same_name: same_name_symbols > 1,
                    direct_use: &mut direct_use,
                    uncertain_use: &mut uncertain_use,
                };
                inspect_rust_references(
                    source.tree.root_node(),
                    &source_assignment.module_path,
                    &mut inspection,
                );
            }
            if has_unresolved_rust_dynamic_lookup(&source.source) {
                uncertain_use = true;
            }
        }
        if direct_use {
            return (
                SpecificationLivenessStatus::Live,
                "resolved Rust construction, runtime path use, or evaluator argument".to_owned(),
            );
        }
        if uncertain_use {
            return (
                SpecificationLivenessStatus::Unknown,
                "a Rust import, macro, type-only reference, or ambiguous name may use this declaration".to_owned(),
            );
        }
        if rust_type_is_public(declaration_source, type_name, &assignment.module_path) {
            return (
                SpecificationLivenessStatus::Unknown,
                "the Specification type is externally visible".to_owned(),
            );
        }
        if !closed_world {
            return (
                SpecificationLivenessStatus::Unknown,
                "the manifest does not declare a closed-world source boundary".to_owned(),
            );
        }
        if !is_conventional_rust_crate_root(&assignment.crate_root) {
            return (
                SpecificationLivenessStatus::Unknown,
                "the selected Rust files do not identify a complete crate root".to_owned(),
            );
        }
        (
            SpecificationLivenessStatus::Dead,
            "private Rust Specification has no resolved runtime use in the closed crate".to_owned(),
        )
    }
}

struct RustReferenceInspection<'a> {
    source: &'a ParsedRustSource,
    target_path: String,
    type_name: &'a str,
    imported_aliases: HashSet<String>,
    declaration_line: usize,
    declaration_path: &'a str,
    declaration_module: &'a [String],
    ambiguous_same_name: bool,
    direct_use: &'a mut bool,
    uncertain_use: &'a mut bool,
}

fn rust_definition_module(
    node: Node<'_>,
    source: &[u8],
    line: usize,
    type_name: &str,
    module_path: &[String],
) -> Option<Vec<String>> {
    if node.kind() == "impl_item"
        && node.start_position().row + 1 == line
        && node.child_by_field_name("trait").is_some_and(|trait_node| {
            trait_node
                .utf8_text(source)
                .unwrap_or_default()
                .rsplit("::")
                .next()
                .is_some_and(is_specification_trait)
        })
    {
        return Some(module_path.to_vec());
    }
    if matches!(node.kind(), "struct_item" | "enum_item" | "type_item")
        && node.start_position().row + 1 == line
        && node
            .child_by_field_name("name")
            .is_some_and(|name| name.utf8_text(source).ok() == Some(type_name))
    {
        return Some(module_path.to_vec());
    }
    let nested_module = if node.kind() == "mod_item" {
        node.child_by_field_name("name")
            .and_then(|name| name.utf8_text(source).ok())
    } else {
        None
    };
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        let mut child_module = module_path.to_vec();
        if child.kind() == "declaration_list"
            && let Some(name) = nested_module
        {
            child_module.push(name.to_owned());
        }
        if let Some(found) = rust_definition_module(child, source, line, type_name, &child_module) {
            return Some(found);
        }
    }
    None
}

fn rust_type_name(name: &str) -> &str {
    name.split('<')
        .next()
        .unwrap_or(name)
        .rsplit("::")
        .next()
        .unwrap_or(name)
        .trim()
}

fn is_conventional_rust_crate_root(path: &str) -> bool {
    let path = std::path::Path::new(path);
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

fn inspect_rust_references(
    node: Node<'_>,
    current_module: &[String],
    inspection: &mut RustReferenceInspection<'_>,
) {
    let line = node.start_position().row + 1;
    if node.kind() == "impl_item"
        && line == inspection.declaration_line
        && inspection.source.path == inspection.declaration_path
    {
        return;
    }
    let text = node
        .utf8_text(inspection.source.source.as_bytes())
        .unwrap_or_default()
        .trim();
    let matching_identifier = matches!(node.kind(), "identifier" | "type_identifier")
        && (text == inspection.type_name || inspection.imported_aliases.contains(text));
    let resolved_import_alias = inspection.imported_aliases.contains(text);
    let matching_path = matches!(node.kind(), "scoped_identifier" | "scoped_type_identifier")
        && rust_path_matches(text, &inspection.target_path, inspection.type_name);
    if matching_identifier || matching_path {
        let is_type_declaration_name = node.parent().is_some_and(|parent| {
            matches!(parent.kind(), "struct_item" | "enum_item")
                && parent.child_by_field_name("name") == Some(node)
        });
        if is_type_declaration_name {
            return;
        }
        if inside_rust_use_declaration(node) {
            *inspection.uncertain_use = true;
        } else if node_is_runtime_rust_use(node) {
            if matching_identifier
                && !resolved_import_alias
                && (inspection.ambiguous_same_name
                    || current_module != inspection.declaration_module)
            {
                *inspection.uncertain_use = true;
            } else {
                *inspection.direct_use = true;
            }
        } else {
            *inspection.uncertain_use = true;
        }
    }
    if node.kind() == "macro_invocation" && text.contains(inspection.type_name) {
        if rust_static_registration_macro(text) {
            *inspection.direct_use = true;
        } else {
            *inspection.uncertain_use = true;
        }
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        let mut child_module = current_module.to_vec();
        if child.kind() == "declaration_list"
            && node.kind() == "mod_item"
            && let Some(name) = node
                .child_by_field_name("name")
                .and_then(|name| name.utf8_text(inspection.source.source.as_bytes()).ok())
        {
            child_module.push(name.to_owned());
        }
        inspect_rust_references(child, &child_module, inspection);
    }
}

fn rust_import_aliases(
    node: Node<'_>,
    source: &[u8],
    module_path: &str,
    type_name: &str,
) -> HashSet<String> {
    let mut aliases = HashSet::new();
    fn collect(
        node: Node<'_>,
        source: &[u8],
        module_path: &str,
        type_name: &str,
        aliases: &mut HashSet<String>,
    ) {
        if node.kind() == "use_declaration" {
            let text = node.utf8_text(source).unwrap_or_default().trim();
            let text = text
                .strip_prefix("pub ")
                .unwrap_or(text)
                .strip_prefix("use ")
                .unwrap_or(text)
                .trim_end_matches(';')
                .trim();
            if let Some((path, alias)) = text.split_once(" as ")
                && rust_path_matches(path.trim(), module_path, type_name)
                && !alias.trim().is_empty()
            {
                aliases.insert(alias.trim().to_owned());
            } else if rust_path_matches(text, module_path, type_name) {
                aliases.insert(type_name.to_owned());
            }
            return;
        }
        let mut cursor = node.walk();
        for child in node.named_children(&mut cursor) {
            collect(child, source, module_path, type_name, aliases);
        }
    }
    collect(node, source, module_path, type_name, &mut aliases);
    aliases
}

fn rust_path_matches(text: &str, module_path: &str, type_name: &str) -> bool {
    let normalized = text
        .chars()
        .filter(|c| !c.is_whitespace())
        .collect::<String>();
    let target = if module_path.is_empty() {
        type_name.to_owned()
    } else {
        format!("{module_path}::{type_name}")
    };
    normalized == format!("crate::{target}")
        || normalized == format!("self::{target}")
        || normalized.ends_with(&format!("::{target}"))
        || normalized == target
}

fn node_is_runtime_rust_use(node: Node<'_>) -> bool {
    let mut parent = node.parent();
    while let Some(current) = parent {
        if current.kind() == "let_declaration" {
            return current.child_by_field_name("value").is_some_and(|value| {
                value.start_byte() <= node.start_byte() && value.end_byte() >= node.end_byte()
            });
        }
        if matches!(
            current.kind(),
            "call_expression"
                | "struct_expression"
                | "field_expression"
                | "match_pattern"
                | "tuple_struct_pattern"
                | "macro_invocation"
        ) {
            return current.kind() != "macro_invocation";
        }
        if matches!(
            current.kind(),
            "function_item" | "impl_item" | "source_file"
        ) {
            return false;
        }
        parent = current.parent();
    }
    false
}

fn rust_static_registration_macro(text: &str) -> bool {
    let prefix = text.trim_start();
    prefix.starts_with("inventory :: submit !")
        || prefix.starts_with("linkme :: distributed_slice !")
        || prefix.starts_with("inventory::submit!")
        || prefix.starts_with("linkme::distributed_slice!")
}

fn inside_rust_use_declaration(node: Node<'_>) -> bool {
    let mut ancestor = node.parent();
    while let Some(current) = ancestor {
        if current.kind() == "use_declaration" {
            return true;
        }
        if current.kind() == "source_file" {
            return false;
        }
        ancestor = current.parent();
    }
    false
}

fn has_unresolved_rust_dynamic_lookup(source: &str) -> bool {
    let source = source
        .chars()
        .filter(|character| !character.is_whitespace())
        .collect::<String>();
    source.contains("dynSpecification")
        && ["resolve(", "lookup(", "get_by_name("]
            .iter()
            .any(|call| source.contains(call))
}

fn count_rust_type_declarations(node: Node<'_>, source: &[u8], name: &str, count: &mut usize) {
    if matches!(node.kind(), "struct_item" | "enum_item")
        && node
            .child_by_field_name("name")
            .is_some_and(|name_node| name_node.utf8_text(source).ok() == Some(name))
    {
        *count += 1;
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        count_rust_type_declarations(child, source, name, count);
    }
}

fn rust_type_is_public(source: &ParsedRustSource, name: &str, _module_path: &[String]) -> bool {
    fn visit(node: Node<'_>, source: &[u8], name: &str) -> bool {
        if matches!(node.kind(), "struct_item" | "enum_item" | "type_item")
            && node
                .child_by_field_name("name")
                .is_some_and(|name_node| name_node.utf8_text(source).ok() == Some(name))
        {
            return node.child_by_field_name("visibility_modifier").is_some()
                || node
                    .utf8_text(source)
                    .unwrap_or_default()
                    .trim_start()
                    .starts_with("pub ");
        }
        let mut cursor = node.walk();
        node.named_children(&mut cursor)
            .any(|child| visit(child, source, name))
    }
    visit(source.tree.root_node(), source.source.as_bytes(), name)
}

fn is_specification_trait(name: &str) -> bool {
    let name = name.split('<').next().unwrap_or(name).trim();
    matches!(
        name,
        "SpecificationMetricV1"
            | "Specification"
            | "AsyncSpecification"
            | "DecisionSpec"
            | "AsyncDecisionSpec"
            | "DecisionSpecification"
            | "AutoContextSpecification"
    )
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
            dynamic_lookup |= contains_dynamic_lookup(tree.root_node(), &source.source)
                || has_module_getattr(tree.root_node(), &source.source)
                || has_dynamic_all(tree.root_node(), &source.source);
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
        if self.sources.iter().any(|source| {
            source.path == definition.path
                && has_registration_decorator(source.tree.root_node(), &source.source, definition)
        }) {
            direct_use = true;
        }
        for source in &self.sources {
            let imports = self.aliases_for(source);
            ambiguous_use |= imports.ambiguous_targets.contains(&declaration_index);
            let has_symbol_alias = imports
                .aliases
                .values()
                .flatten()
                .any(|index| *index == declaration_index);
            let target_module = module_name(&definition.path);
            let has_module_alias = imports.module_aliases.values().flatten().any(|module| {
                target_module == *module || target_module.starts_with(&format!("{module}."))
            });
            if !has_symbol_alias && !has_module_alias {
                continue;
            }
            let mut inspection = ReferenceInspection {
                resolver: self,
                source: &source.source,
                imports: &imports,
                target: declaration_index,
                direct_use: &mut direct_use,
                ambiguous_use: &mut ambiguous_use,
            };
            inspect_runtime_references(
                source.tree.root_node(),
                None,
                None,
                None,
                false,
                false,
                &mut inspection,
            );
        }
        if ambiguous_use {
            return (
                SpecificationLivenessStatus::Unknown,
                "a runtime reference may be shadowed or dynamically resolved".to_owned(),
            );
        }
        if direct_use {
            return (
                SpecificationLivenessStatus::Live,
                "resolved constructor or Specification consumer use".to_owned(),
            );
        }
        if self.dynamic_lookup {
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

    fn aliases_for(&self, source: &ParsedPythonSource) -> ImportResolution {
        let mut imports = ImportResolution::default();
        for ((module, name), indices) in &self.definitions_by_module {
            if module == &source.module {
                imports
                    .aliases
                    .entry(name.clone())
                    .or_default()
                    .extend(indices);
            }
        }
        collect_imports(
            self,
            source.tree.root_node(),
            &source.path,
            &source.source,
            &mut imports,
        );
        imports
    }

    fn module_exists(&self, module: &str) -> bool {
        self.sources.iter().any(|source| source.module == module)
    }

    fn module_has_dynamic_export_assignment(&self, module: &str, name: &str) -> bool {
        let sources = self
            .sources
            .iter()
            .filter(|source| source.module == module)
            .collect::<Vec<_>>();
        if sources.len() != 1 {
            return false;
        }
        let source = sources[0];
        let mut cursor = source.tree.root_node().walk();
        source
            .tree
            .root_node()
            .named_children(&mut cursor)
            .any(|statement| {
                let assignments = if statement.kind() == "expression_statement" {
                    let mut statement_cursor = statement.walk();
                    statement
                        .named_children(&mut statement_cursor)
                        .collect::<Vec<_>>()
                } else {
                    vec![statement]
                };
                assignments.into_iter().any(|assignment| {
                    matches!(assignment.kind(), "assignment" | "augmented_assignment")
                        && assignment
                            .child_by_field_name("left")
                            .and_then(|left| left.utf8_text(source.source.as_bytes()).ok())
                            == Some(name)
                        && assignment
                            .child_by_field_name("right")
                            .is_some_and(|right| match right.kind() {
                                "string" | "integer" | "float" | "true" | "false" | "none" => false,
                                "identifier" => {
                                    let assigned_name = right
                                        .utf8_text(source.source.as_bytes())
                                        .unwrap_or_default();
                                    !self.definitions_by_module.contains_key(&(
                                        module.to_owned(),
                                        assigned_name.to_owned(),
                                    ))
                                }
                                "call" => {
                                    let called_name = right
                                        .child_by_field_name("function")
                                        .and_then(|function| {
                                            function.utf8_text(source.source.as_bytes()).ok()
                                        })
                                        .unwrap_or_default()
                                        .rsplit('.')
                                        .next()
                                        .unwrap_or_default();
                                    !self
                                        .definitions_by_module
                                        .contains_key(&(module.to_owned(), called_name.to_owned()))
                                }
                                _ => true,
                            })
                })
            })
    }

    fn resolve_symbol(
        &self,
        module: &str,
        name: &str,
        visited: &mut HashSet<(String, String)>,
    ) -> SymbolResolution {
        let key = (module.to_owned(), name.to_owned());
        if !visited.insert(key.clone()) {
            return SymbolResolution {
                ambiguous: true,
                ..SymbolResolution::default()
            };
        }
        if let Some(indices) = self
            .definitions_by_module
            .get(&(module.to_owned(), name.to_owned()))
        {
            return SymbolResolution {
                indices: indices.clone(),
                ambiguous: indices.len() != 1,
            };
        }
        let matching_sources = self
            .sources
            .iter()
            .filter(|source| source.module == module)
            .collect::<Vec<_>>();
        if matching_sources.len() != 1 {
            return SymbolResolution {
                ambiguous: !matching_sources.is_empty(),
                ..SymbolResolution::default()
            };
        }
        let source = matching_sources[0];
        if self.parse_failed.contains(&source.path) {
            return SymbolResolution {
                ambiguous: true,
                ..SymbolResolution::default()
            };
        }
        let mut result = SymbolResolution::default();
        let mut cursor = source.tree.root_node().walk();
        let module_statements = source
            .tree
            .root_node()
            .named_children(&mut cursor)
            .collect::<Vec<_>>();
        for import_node in &module_statements {
            if import_node.kind() != "import_from_statement" {
                continue;
            }
            for binding in from_import_bindings(*import_node, &source.path, &source.source) {
                if binding.wildcard {
                    result.ambiguous = true;
                    continue;
                }
                if binding.local != name {
                    continue;
                }
                if self.module_exists(&format!("{}.{}", binding.module, binding.name)) {
                    continue;
                }
                let mut branch = visited.clone();
                let resolved = self.resolve_symbol(&binding.module, &binding.name, &mut branch);
                result.indices.extend(resolved.indices);
                result.ambiguous |= resolved.ambiguous;
            }
        }
        let mut conditional_imports = Vec::new();
        for statement in module_statements {
            if is_module_compound_statement(statement.kind()) {
                collect_module_level_imports(
                    statement,
                    &source.path,
                    &source.source,
                    &mut conditional_imports,
                );
            }
        }
        for binding in conditional_imports {
            if binding.local != name || binding.wildcard {
                continue;
            }
            if self.module_exists(&format!("{}.{}", binding.module, binding.name)) {
                result.ambiguous = true;
                continue;
            }
            let mut branch = visited.clone();
            let resolved = self.resolve_symbol(&binding.module, &binding.name, &mut branch);
            result.indices.extend(resolved.indices);
            result.ambiguous = true;
        }
        result.indices.sort_unstable();
        result.indices.dedup();
        result.ambiguous |= result.indices.len() > 1;
        visited.remove(&key);
        result
    }
}

#[derive(Default)]
struct SymbolResolution {
    indices: Vec<usize>,
    ambiguous: bool,
}

#[derive(Default)]
struct ImportResolution {
    aliases: HashMap<String, Vec<usize>>,
    module_aliases: HashMap<String, Vec<String>>,
    ambiguous_targets: HashSet<usize>,
}

fn module_name(path: &str) -> String {
    let path = path.strip_prefix("src/").unwrap_or(path);
    let module = path.strip_suffix(".py").unwrap_or(path);
    let module = module.strip_suffix("/__init__").unwrap_or(module);
    module.replace('/', ".")
}

#[derive(Clone)]
struct FromImportBinding {
    module: String,
    name: String,
    local: String,
    wildcard: bool,
}

fn from_import_bindings(node: Node<'_>, source_path: &str, source: &str) -> Vec<FromImportBinding> {
    let mut bindings = Vec::new();
    if node.kind() == "import_from_statement"
        && let Some(module_node) = node.child_by_field_name("module_name")
    {
        let module = resolve_import_module(
            source_path,
            module_node.utf8_text(source.as_bytes()).unwrap_or_default(),
        );
        let mut cursor = node.walk();
        for imported in node.children_by_field_name("name", &mut cursor) {
            if imported.kind() == "wildcard_import" {
                bindings.push(FromImportBinding {
                    module: module.clone(),
                    name: "*".to_owned(),
                    local: "*".to_owned(),
                    wildcard: true,
                });
                continue;
            }
            let (name, local) = if imported.kind() == "aliased_import" {
                (
                    imported
                        .child_by_field_name("name")
                        .and_then(|child| child.utf8_text(source.as_bytes()).ok())
                        .unwrap_or_default()
                        .to_owned(),
                    imported
                        .child_by_field_name("alias")
                        .and_then(|child| child.utf8_text(source.as_bytes()).ok())
                        .unwrap_or_default()
                        .to_owned(),
                )
            } else {
                let name = imported.utf8_text(source.as_bytes()).unwrap_or_default();
                (
                    name.to_owned(),
                    name.rsplit('.').next().unwrap_or(name).to_owned(),
                )
            };
            if !name.is_empty() && !local.is_empty() {
                bindings.push(FromImportBinding {
                    module: module.clone(),
                    name,
                    local,
                    wildcard: false,
                });
            }
        }
    }
    bindings
}

fn collect_imports(
    python: &PythonLiveness,
    node: Node<'_>,
    source_path: &str,
    source: &str,
    imports: &mut ImportResolution,
) {
    if node.kind() == "wildcard_import" {
        imports
            .ambiguous_targets
            .extend(python.definitions_by_module.values().flatten().copied());
        return;
    }
    if node.kind() == "import_statement" {
        let mut cursor = node.walk();
        for imported in node.named_children(&mut cursor) {
            let (module, local) = if imported.kind() == "aliased_import" {
                (
                    imported
                        .child_by_field_name("name")
                        .and_then(|child| child.utf8_text(source.as_bytes()).ok())
                        .unwrap_or_default()
                        .to_owned(),
                    imported
                        .child_by_field_name("alias")
                        .and_then(|child| child.utf8_text(source.as_bytes()).ok())
                        .unwrap_or_default()
                        .to_owned(),
                )
            } else {
                let module = imported.utf8_text(source.as_bytes()).unwrap_or_default();
                let root = module.split('.').next().unwrap_or(module);
                (root.to_owned(), root.to_owned())
            };
            let has_measured_module = python.module_exists(&module)
                || python
                    .sources
                    .iter()
                    .any(|candidate| candidate.module.starts_with(&format!("{module}.")));
            if has_measured_module && !local.is_empty() {
                imports
                    .module_aliases
                    .entry(local)
                    .or_default()
                    .push(module);
            }
        }
    }
    if node.kind() == "import_from_statement" {
        for binding in from_import_bindings(node, source_path, source) {
            if binding.wildcard {
                imports
                    .ambiguous_targets
                    .extend(python.definitions_by_module.values().flatten().copied());
                continue;
            }
            let submodule = format!("{}.{}", binding.module, binding.name);
            if python.module_exists(&submodule) {
                imports
                    .module_aliases
                    .entry(binding.local)
                    .or_default()
                    .push(submodule);
                continue;
            }
            let resolved =
                python.resolve_symbol(&binding.module, &binding.name, &mut HashSet::new());
            if !resolved.indices.is_empty() {
                imports
                    .aliases
                    .entry(binding.local)
                    .or_default()
                    .extend(resolved.indices.iter().copied());
            }
            if resolved.ambiguous {
                imports
                    .ambiguous_targets
                    .extend(resolved.indices.iter().copied());
            }
            if resolved.indices.is_empty() {
                imports.ambiguous_targets.extend(
                    python
                        .definitions_by_module
                        .iter()
                        .filter(|((_, name), _)| name == &binding.name)
                        .flat_map(|(_, indices)| indices.iter().copied()),
                );
                if python.module_has_dynamic_export_assignment(&binding.module, &binding.name) {
                    let prefix = format!("{}.", binding.module);
                    imports.ambiguous_targets.extend(
                        python
                            .definitions_by_module
                            .iter()
                            .filter(|((module, _), _)| {
                                module == &binding.module || module.starts_with(&prefix)
                            })
                            .flat_map(|(_, indices)| indices.iter().copied()),
                    );
                }
            }
        }
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_imports(python, child, source_path, source, imports);
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

struct ReferenceInspection<'a> {
    resolver: &'a PythonLiveness,
    source: &'a str,
    imports: &'a ImportResolution,
    target: usize,
    direct_use: &'a mut bool,
    ambiguous_use: &'a mut bool,
}

fn inspect_runtime_references(
    node: Node<'_>,
    parent: Option<Node<'_>>,
    grandparent: Option<Node<'_>>,
    great_grandparent: Option<Node<'_>>,
    in_type: bool,
    in_import: bool,
    inspection: &mut ReferenceInspection<'_>,
) {
    if inspection
        .imports
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
    if node.kind() == "attribute"
        && !node_is_type
        && let Some(path) = expression_path(node, inspection.source)
    {
        for (alias, modules) in &inspection.imports.module_aliases {
            let Some(suffix) = path.strip_prefix(&format!("{alias}.")) else {
                continue;
            };
            let mut parts = suffix.split('.').collect::<Vec<_>>();
            let Some(symbol) = parts.pop() else {
                continue;
            };
            for module in modules {
                let resolved_module = if parts.is_empty() {
                    module.clone()
                } else {
                    format!("{module}.{}", parts.join("."))
                };
                let resolved = inspection.resolver.resolve_symbol(
                    &resolved_module,
                    symbol,
                    &mut HashSet::new(),
                );
                if resolved.indices.contains(&inspection.target) {
                    if modules.len() == 1
                        && !resolved.ambiguous
                        && is_runtime_use(
                            node,
                            parent,
                            grandparent,
                            great_grandparent,
                            inspection.source,
                        )
                    {
                        *inspection.direct_use = true;
                    } else {
                        *inspection.ambiguous_use = true;
                    }
                }
            }
        }
    }
    if node.kind() == "identifier" && !node_is_type && !node_is_import {
        let name = node
            .utf8_text(inspection.source.as_bytes())
            .unwrap_or_default();
        let is_declaration_name = parent.is_some_and(|parent| {
            parent.kind() == "class_definition" && parent.child_by_field_name("name") == Some(node)
        });
        let is_module_prefix = parent.is_some_and(|parent| {
            parent.kind() == "attribute" && parent.child_by_field_name("object") == Some(node)
        });
        if !is_module_prefix && inspection.imports.module_aliases.contains_key(name) {
            *inspection.ambiguous_use = true;
        }
        if !is_declaration_name
            && let Some(indices) = inspection.imports.aliases.get(name)
            && indices.contains(&inspection.target)
        {
            if is_runtime_use(
                node,
                parent,
                grandparent,
                great_grandparent,
                inspection.source,
            ) {
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
            grandparent,
            node_is_type,
            node_is_import,
            inspection,
        );
    }
}

fn expression_path(node: Node<'_>, source: &str) -> Option<String> {
    match node.kind() {
        "identifier" => Some(node.utf8_text(source.as_bytes()).ok()?.to_owned()),
        "attribute" => {
            let object = expression_path(node.child_by_field_name("object")?, source)?;
            let attribute = node
                .child_by_field_name("attribute")?
                .utf8_text(source.as_bytes())
                .ok()?;
            Some(format!("{object}.{attribute}"))
        }
        _ => None,
    }
}

fn is_runtime_use(
    node: Node<'_>,
    parent: Option<Node<'_>>,
    grandparent: Option<Node<'_>>,
    great_grandparent: Option<Node<'_>>,
    source: &str,
) -> bool {
    let class_pattern = parent.zip(grandparent).is_some_and(|(parent, pattern)| {
        parent.kind() == "dotted_name"
            && pattern.kind() == "class_pattern"
            && pattern.named_child(0) == Some(parent)
    });
    let mapping_value = parent.is_some_and(|pair| {
        pair.kind() == "pair" && pair.child_by_field_name("value") == Some(node)
    });
    let called = parent.is_some_and(|parent| {
        parent.kind() == "call" && parent.child_by_field_name("function") == Some(node)
    });
    let generic_constructor = parent.is_some_and(|subscript| {
        subscript.kind() == "subscript"
            && subscript.child_by_field_name("value") == Some(node)
            && grandparent.is_some_and(|call| {
                call.kind() == "call" && call.child_by_field_name("function") == Some(subscript)
            })
    });
    let class_factory_call = parent.is_some_and(|attribute| {
        attribute.kind() == "attribute"
            && attribute.child_by_field_name("object") == Some(node)
            && grandparent.is_some_and(|call| {
                call.kind() == "call" && call.child_by_field_name("function") == Some(attribute)
            })
    });
    let call_consumed = |arguments: Node<'_>, call: Option<Node<'_>>| {
        call.is_some_and(|call| {
            call.kind() == "call"
                && call.child_by_field_name("arguments") == Some(arguments)
                && call
                    .child_by_field_name("function")
                    .is_some_and(|function| {
                        is_specification_consumer(
                            function.utf8_text(source.as_bytes()).unwrap_or_default(),
                        )
                    })
        })
    };
    let consumed = parent.is_some_and(|parent| {
        (parent.kind() == "argument_list" && call_consumed(parent, grandparent))
            || (parent.kind() == "tuple"
                && grandparent.is_some_and(|arguments| {
                    arguments.kind() == "argument_list"
                        && call_consumed(arguments, great_grandparent)
                }))
    });
    called
        || generic_constructor
        || class_factory_call
        || consumed
        || class_pattern
        || mapping_value
}

fn is_specification_consumer(function: &str) -> bool {
    let name = function.rsplit('.').next().unwrap_or(function);
    matches!(
        name,
        "evaluate"
            | "isinstance"
            | "issubclass"
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

fn has_registration_decorator(
    node: Node<'_>,
    source: &str,
    definition: &SpecificationDefinition,
) -> bool {
    if node.kind() == "decorated_definition" {
        let mut cursor = node.walk();
        let children = node.named_children(&mut cursor).collect::<Vec<_>>();
        let decorates_target = children.iter().any(|child| {
            child.kind() == "class_definition"
                && child.start_position().row + 1 == definition.line
                && child
                    .child_by_field_name("name")
                    .and_then(|name| name.utf8_text(source.as_bytes()).ok())
                    == Some(definition.name.as_str())
        });
        if decorates_target {
            return children
                .iter()
                .filter(|child| child.kind() == "decorator")
                .any(|decorator| {
                    let decorator = decorator.utf8_text(source.as_bytes()).unwrap_or_default();
                    let function = decorator
                        .trim_start_matches('@')
                        .split('(')
                        .next()
                        .unwrap_or_default()
                        .rsplit('.')
                        .next()
                        .unwrap_or_default();
                    matches!(function, "register" | "register_factory")
                });
        }
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| has_registration_decorator(child, source, definition))
}

fn contains_dynamic_lookup(node: Node<'_>, source: &str) -> bool {
    if node.kind() == "call"
        && let Some(function) = node.child_by_field_name("function")
    {
        let name = function.utf8_text(source.as_bytes()).unwrap_or_default();
        let name = name.rsplit('.').next().unwrap_or(name);
        if matches!(
            name,
            "getattr"
                | "globals"
                | "locals"
                | "eval"
                | "exec"
                | "__import__"
                | "import_module"
                | "__subclasses__"
        ) {
            return true;
        }
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| contains_dynamic_lookup(child, source))
}

fn has_module_getattr(node: Node<'_>, source: &str) -> bool {
    if node.kind() == "class_definition" {
        return false;
    }
    if node.kind() == "function_definition" {
        return node
            .child_by_field_name("name")
            .and_then(|name| name.utf8_text(source.as_bytes()).ok())
            == Some("__getattr__");
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| has_module_getattr(child, source))
}

fn collect_module_level_imports(
    node: Node<'_>,
    source_path: &str,
    source: &str,
    imports: &mut Vec<FromImportBinding>,
) {
    if matches!(
        node.kind(),
        "class_definition" | "function_definition" | "lambda"
    ) {
        return;
    }
    if node.kind() == "import_from_statement" {
        imports.extend(from_import_bindings(node, source_path, source));
        return;
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_module_level_imports(child, source_path, source, imports);
    }
}

fn is_module_compound_statement(kind: &str) -> bool {
    matches!(
        kind,
        "if_statement"
            | "try_statement"
            | "with_statement"
            | "for_statement"
            | "while_statement"
            | "match_statement"
    )
}

fn has_dynamic_all(node: Node<'_>, source: &str) -> bool {
    let mut cursor = node.walk();
    node.named_children(&mut cursor).any(|child| {
        let statements = if child.kind() == "expression_statement" {
            let mut statement_cursor = child.walk();
            child
                .named_children(&mut statement_cursor)
                .collect::<Vec<_>>()
        } else {
            vec![child]
        };
        statements.into_iter().any(|statement| {
            if statement.kind() == "augmented_assignment"
                && statement
                    .child_by_field_name("left")
                    .and_then(|left| left.utf8_text(source.as_bytes()).ok())
                    == Some("__all__")
            {
                return true;
            }
            if statement.kind() == "assignment"
                && statement
                    .child_by_field_name("left")
                    .and_then(|left| left.utf8_text(source.as_bytes()).ok())
                    == Some("__all__")
            {
                let Some(right) = statement.child_by_field_name("right") else {
                    return true;
                };
                if !matches!(right.kind(), "list" | "tuple") {
                    return true;
                }
                let mut values = right.walk();
                return right
                    .named_children(&mut values)
                    .any(|value| value.kind() != "string" && value.kind() != "comment");
            }
            if statement.kind() == "call" {
                return statement
                    .child_by_field_name("function")
                    .is_some_and(|function| {
                        function.kind() == "attribute"
                            && function
                                .child_by_field_name("object")
                                .and_then(|object| object.utf8_text(source.as_bytes()).ok())
                                == Some("__all__")
                    });
            }
            false
        })
    })
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

    use super::PythonSource;
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

        let results = super::classify(&definitions, &[], &[], false, true);
        assert!(
            results
                .iter()
                .all(|result| result.status == SpecificationLivenessStatus::Live)
        );
    }

    #[test]
    fn conflicting_reexports_are_unknown_for_each_target() {
        let definitions = ["package/a.py", "package/b.py"].map(|path| SpecificationDefinition {
            language: Language::Python,
            path: path.to_owned(),
            name: "_Ready".to_owned(),
            kind: "declaration".to_owned(),
            line: 1,
            column: 1,
        });
        let sources = [
            PythonSource {
                path: "package/a.py".to_owned(),
                source: "class _Ready(Specification):\n    pass\n".to_owned(),
            },
            PythonSource {
                path: "package/b.py".to_owned(),
                source: "class _Ready(Specification):\n    pass\n".to_owned(),
            },
            PythonSource {
                path: "package/__init__.py".to_owned(),
                source: "from .a import _Ready as Ready\nfrom .b import _Ready as Ready\n"
                    .to_owned(),
            },
            PythonSource {
                path: "consumer.py".to_owned(),
                source: "import package\npackage.Ready()\n".to_owned(),
            },
        ];

        let results = super::classify(&definitions, &sources, &[], true, false);
        assert_eq!(results.len(), 2);
        assert!(
            results
                .iter()
                .all(|result| result.status == SpecificationLivenessStatus::Unknown)
        );
    }

    #[test]
    fn language_liveness_matches_versioned_acceptance_fixtures() {
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
            let expected = if case.language == "swift" {
                SpecificationLivenessStatus::Unknown
            } else {
                match case.status.as_str() {
                    "live" => SpecificationLivenessStatus::Live,
                    "dead" => SpecificationLivenessStatus::Dead,
                    "unknown" => SpecificationLivenessStatus::Unknown,
                    status => panic!("unsupported status in fixture {}: {status}", case.id),
                }
            };
            assert_eq!(
                actual, expected,
                "{}: {}",
                case.id, report.specification_liveness[0].evidence
            );

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
