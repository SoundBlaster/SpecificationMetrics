//! Resolve static module-level ancestry before counting Specification bodies.
use std::collections::{HashMap, HashSet};

use tree_sitter::Node;

use super::{ParsedPythonSource, PythonLiveness, PythonSource, from_import_bindings, module_name};
use crate::model::{Candidate, Language, SpecificationDefinition};

pub(crate) fn discover_python_specifications(
    sources: &[PythonSource],
    definitions: &mut Vec<SpecificationDefinition>,
    candidates: &mut [Candidate],
) {
    let original_count = definitions.len();
    let mut resolver = PythonLiveness::new(sources, definitions);
    let mut catalog = definitions.clone();
    let mut positions = HashMap::new();
    for (index, definition) in catalog.iter().enumerate() {
        positions.insert(
            (definition.path.clone(), definition.line, definition.column),
            index,
        );
    }
    for source in &resolver.sources {
        for class in module_classes(source.tree.root_node()) {
            let position = class.start_position();
            let key = (source.path.clone(), position.row + 1, position.column + 1);
            if positions.contains_key(&key) {
                continue;
            }
            let Some(name) = class.child_by_field_name("name") else {
                continue;
            };
            let index = catalog.len();
            positions.insert(key, index);
            catalog.push(SpecificationDefinition {
                language: Language::Python,
                path: source.path.clone(),
                name: name
                    .utf8_text(source.source.as_bytes())
                    .unwrap_or_default()
                    .to_owned(),
                kind: "declaration".to_owned(),
                line: position.row + 1,
                column: position.column + 1,
            });
        }
    }
    resolver.definitions_by_module.clear();
    for (index, definition) in catalog.iter().enumerate() {
        if definition.language == Language::Python && definition.kind == "declaration" {
            resolver
                .definitions_by_module
                .entry((module_name(&definition.path), definition.name.clone()))
                .or_default()
                .push(index);
        }
    }
    // Only explicit native/marker declarations seed the fixed point. Unseeded
    // cycles and unrelated classes cannot become Specifications by name alone.
    let mut known: HashSet<_> = (0..original_count).collect();
    loop {
        let mut added = false;
        for source in &resolver.sources {
            if resolver.parse_failed.contains(&source.path) {
                continue;
            }
            for class in module_classes(source.tree.root_node()) {
                let position = class.start_position();
                let index =
                    positions[&(source.path.clone(), position.row + 1, position.column + 1)];
                if known.contains(&index) {
                    continue;
                }
                let Some(bases) = class.child_by_field_name("superclasses") else {
                    continue;
                };
                let mut cursor = bases.walk();
                if bases.named_children(&mut cursor).any(|base| {
                    resolve_base(&resolver, source, base)
                        .is_some_and(|parent| known.contains(&parent))
                }) {
                    known.insert(index);
                    added = true;
                }
            }
        }
        if !added {
            break;
        }
    }
    for source in &resolver.sources {
        for class in module_classes(source.tree.root_node()) {
            let start = class.start_position();
            let end = class.end_position();
            let index = positions[&(source.path.clone(), start.row + 1, start.column + 1)];
            if index < original_count || !known.contains(&index) {
                continue;
            }
            // Test against the original catalog boundary, not the growing
            // definitions vector (which can contain earlier discovered types).
            definitions.push(catalog[index].clone());
            for candidate in candidates
                .iter_mut()
                .filter(|item| item.language == Language::Python && item.path == source.path)
            {
                let point = (candidate.line - 1, candidate.column - 1);
                if (start.row, start.column) <= point && point < (end.row, end.column) {
                    candidate.inside_specification = true;
                }
            }
        }
    }
}

fn module_classes(root: Node<'_>) -> Vec<Node<'_>> {
    let mut cursor = root.walk();
    root.named_children(&mut cursor)
        .filter_map(|node| {
            if node.kind() == "class_definition" {
                return Some(node);
            }
            if node.kind() == "decorated_definition" {
                let mut cursor = node.walk();
                return node
                    .named_children(&mut cursor)
                    .find(|child| child.kind() == "class_definition");
            }
            None
        })
        .collect()
}

enum Binding {
    Class,
    Imported(String, String),
    Module(String),
    Other,
}

fn unique_binding(source: &ParsedPythonSource, name: &str) -> Option<(usize, Binding)> {
    let text = source.source.as_bytes();
    let mut bindings = Vec::new();
    let mut cursor = source.tree.root_node().walk();
    for node in source.tree.root_node().named_children(&mut cursor) {
        match node.kind() {
            "class_definition" | "decorated_definition" => {
                let class = if node.kind() == "decorated_definition" {
                    let mut cursor = node.walk();
                    node.named_children(&mut cursor)
                        .find(|child| child.kind() == "class_definition")
                } else {
                    Some(node)
                };
                if let Some(class) = class
                    && class
                        .child_by_field_name("name")
                        .and_then(|n| n.utf8_text(text).ok())
                        == Some(name)
                {
                    bindings.push((node.start_byte(), Binding::Class));
                } else if binds_name(node, name, text) {
                    bindings.push((node.start_byte(), Binding::Other));
                }
            }
            "import_from_statement" => {
                let mut cursor = node.walk();
                if node
                    .named_children(&mut cursor)
                    .any(|child| child.kind() == "wildcard_import")
                {
                    bindings.push((node.start_byte(), Binding::Other));
                    continue;
                }
                for binding in from_import_bindings(node, &source.path, &source.source) {
                    if binding.wildcard {
                        bindings.push((node.start_byte(), Binding::Other));
                    } else if binding.local == name {
                        bindings.push((
                            node.start_byte(),
                            Binding::Imported(binding.module, binding.name),
                        ));
                    }
                }
            }
            "import_statement" => {
                let mut cursor = node.walk();
                for imported in node.named_children(&mut cursor) {
                    let (module, local) = if imported.kind() == "aliased_import" {
                        let module = imported.child_by_field_name("name")?.utf8_text(text).ok()?;
                        let local = imported
                            .child_by_field_name("alias")?
                            .utf8_text(text)
                            .ok()?;
                        (module, local)
                    } else {
                        let module = imported.utf8_text(text).ok()?.split('.').next()?;
                        (module, module)
                    };
                    if local == name {
                        bindings.push((node.start_byte(), Binding::Module(module.to_owned())));
                    }
                }
            }
            _ if binds_name(node, name, text) => bindings.push((node.start_byte(), Binding::Other)),
            _ => {}
        }
    }
    if bindings.len() == 1 {
        bindings.pop()
    } else {
        None
    }
}

fn binds_name(node: Node<'_>, name: &str, source: &[u8]) -> bool {
    if matches!(node.kind(), "class_definition" | "function_definition") {
        return node
            .child_by_field_name("name")
            .and_then(|n| n.utf8_text(source).ok())
            == Some(name);
    }
    if node.kind() == "lambda" {
        return false;
    }
    if matches!(node.kind(), "import_statement" | "import_from_statement") {
        // Conditional imports are intentionally not promoted to definite ancestry.
        return true;
    }
    if matches!(
        node.kind(),
        "assignment" | "augmented_assignment" | "named_expression" | "for_statement"
    ) && node
        .child_by_field_name(if node.kind() == "named_expression" {
            "name"
        } else {
            "left"
        })
        .is_some_and(|target| target_contains(target, name, source))
    {
        return true;
    }
    if node.kind() == "as_pattern"
        && node
            .child_by_field_name("alias")
            .is_some_and(|alias| target_contains(alias, name, source))
    {
        return true;
    }
    if node.kind() == "delete_statement" && target_contains(node, name, source) {
        return true;
    }
    if node.kind() == "call"
        && node
            .child_by_field_name("function")
            .and_then(|n| n.utf8_text(source).ok())
            .is_some_and(|f| matches!(f, "exec" | "eval" | "globals" | "locals"))
    {
        return true;
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .any(|child| binds_name(child, name, source))
}

fn target_contains(node: Node<'_>, name: &str, source: &[u8]) -> bool {
    match node.kind() {
        "identifier" => node.utf8_text(source).ok() == Some(name),
        "attribute" | "subscript" => false,
        _ => {
            let mut cursor = node.walk();
            node.named_children(&mut cursor)
                .any(|child| target_contains(child, name, source))
        }
    }
}

fn resolve_symbol(
    resolver: &PythonLiveness,
    module: &str,
    name: &str,
    visited: &mut HashSet<(String, String)>,
) -> Option<usize> {
    if !visited.insert((module.to_owned(), name.to_owned())) {
        return None;
    }
    let mut sources = resolver
        .sources
        .iter()
        .filter(|source| source.module == module);
    let source = sources.next()?;
    if sources.next().is_some() || resolver.parse_failed.contains(&source.path) {
        return None;
    }
    match unique_binding(source, name)?.1 {
        Binding::Class => {
            let indices = resolver
                .definitions_by_module
                .get(&(module.to_owned(), name.to_owned()))?;
            if indices.len() != 1 {
                return None;
            }
            Some(indices[0])
        }
        Binding::Imported(module, name) => resolve_symbol(resolver, &module, &name, visited),
        _ => None,
    }
}

pub(super) fn resolve_base(
    resolver: &PythonLiveness,
    source: &ParsedPythonSource,
    mut base: Node<'_>,
) -> Option<usize> {
    if base.kind() == "subscript" {
        base = base.child_by_field_name("value")?;
    }
    let path = super::expression_path(base, &source.source)?;
    let mut parts = path.split('.');
    let name = parts.next()?;
    let (position, binding) = unique_binding(source, name)?;
    if position >= base.start_byte() {
        return None;
    }
    let suffix = parts.collect::<Vec<_>>();
    if suffix.is_empty() {
        return resolve_symbol(resolver, &source.module, name, &mut HashSet::new());
    }
    let module = match binding {
        Binding::Module(module) => module,
        Binding::Imported(module, name) => {
            let module = format!("{module}.{name}");
            if !resolver.module_exists(&module) {
                return None;
            }
            module
        }
        _ => return None,
    };
    let (symbol, modules) = suffix.split_last()?;
    let module = if modules.is_empty() {
        module
    } else {
        format!("{module}.{}", modules.join("."))
    };
    resolve_symbol(resolver, &module, symbol, &mut HashSet::new())
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::Path;

    use tempfile::tempdir;

    use crate::model::SpecificationLivenessStatus;
    use crate::{live, scan};

    fn write(root: &Path, path: &str, source: &str) {
        let path = root.join(path);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, source).unwrap();
    }

    #[test]
    fn bdd_policy_family_is_counted_and_its_internal_branches_are_covered() {
        let dir = tempdir().unwrap();
        write(
            dir.path(),
            "tools/native_bdd/policy.py",
            "\
from specification_core import Specification
class BDDPolicy(Specification[BDDContext]):
    def skip_reason(self, context):
        if context.invalid: return 'invalid'
",
        );
        let mut composition = String::new();
        for name in [
            "Fields",
            "IDs",
            "Presence",
            "Profile",
            "References",
            "Values",
        ] {
            let module = name.to_lowercase();
            write(
                dir.path(),
                &format!("tools/native_bdd/{module}_spec.py"),
                &format!(
                    "\
from .policy import BDDPolicy
class BDD{name}Spec(BDDPolicy):
    def findings(self, context):
        if context.invalid: return ('invalid',)
        return ()
"
                ),
            );
            composition.push_str(&format!("from .{module}_spec import BDD{name}Spec\n"));
        }
        composition.push_str("POLICIES = (BDDFieldsSpec(), BDDIDsSpec(), BDDPresenceSpec(), BDDProfileSpec(), BDDReferencesSpec(), BDDValuesSpec())\nif enabled: apply(POLICIES)\n");
        write(dir.path(), "tools/native_bdd/composition.py", &composition);
        let report = scan::scan(dir.path(), &["tools".to_owned()]).unwrap();
        assert!(report.parse_issues.is_empty());
        assert_eq!(report.specifications.len(), 7);
        assert_eq!(report.candidates.len(), 8);
        let metric = live::measure(&report, None).unwrap();
        assert_eq!(
            metric.live_specifications, 7,
            "{:?}",
            report.specification_liveness
        );
        assert_eq!(metric.unknown_specifications, 0);
        assert_eq!(metric.covered_candidates, 7);
        assert_eq!(metric.remaining_opportunities, 1);
        assert!(!metric.provisional);
    }

    #[test]
    fn transitive_ancestry_resolves_generic_aliases_reexports_and_module_paths() {
        let dir = tempdir().unwrap();
        write(
            dir.path(),
            "pkg/policy.py",
            "from specification_core import Specification\nclass Policy(Specification): pass\n",
        );
        write(
            dir.path(),
            "pkg/api/__init__.py",
            "from ..policy import Policy as PublicPolicy\n",
        );
        write(
            dir.path(),
            "pkg/z_bridge.py",
            "\
from .api import PublicPolicy as Parent
class Bridge(Parent[int]):
    def evaluate(self, x):
        if x: return True
",
        );
        // The leaf sorts before its base; discovery must reach a fixed point.
        write(
            dir.path(),
            "pkg/a_leaf.py",
            "\
from . import z_bridge as rules
class Mixin: pass
class Leaf(Mixin, rules.Bridge):
    def evaluate(self, x):
        if x: return True
Leaf()
",
        );
        write(
            dir.path(),
            "pkg/qualified.py",
            "\
import pkg.a_leaf
class Final(pkg.a_leaf.Leaf):
    def evaluate(self, x):
        if x: return True
Final()
",
        );
        let report = scan::scan(dir.path(), &["pkg".to_owned()]).unwrap();
        let metric = live::measure(&report, None).unwrap();
        assert_eq!(
            report.specifications.len(),
            4,
            "{:?}",
            report.specifications
        );
        assert_eq!(
            metric.live_specifications, 4,
            "{:?}",
            report.specification_liveness
        );
        assert_eq!(metric.remaining_opportunities, 0);
        assert!(!metric.provisional);
    }

    #[test]
    fn ambiguous_and_rebound_bases_cannot_remove_candidates_from_u() {
        for (name, source) in [
            (
                "assignment",
                "from .policy import Policy\nPolicy = object\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
            (
                "function",
                "from .policy import Policy\ndef Policy(): pass\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
            (
                "conditional",
                "if enabled:\n    from .policy import Policy\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
            (
                "nested_import",
                "def load():\n    from .policy import Policy\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
            (
                "duplicate_import",
                "from .policy import Policy\nfrom .other import Policy\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
            (
                "reexport_rebound",
                "from .api import Policy\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
            (
                "wildcard_import",
                "from .policy import Policy\nfrom .other import *\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
            (
                "module_rebound",
                "import pkg.policy as rules\nrules = object\nclass Child(rules.Policy):\n    if enabled: apply()\n",
            ),
            (
                "reexport_cycle",
                "from .api import Policy\nclass Child(Policy):\n    if enabled: apply()\n",
            ),
        ] {
            let dir = tempdir().unwrap();
            write(
                dir.path(),
                "pkg/policy.py",
                "from specification_core import Specification\nclass Policy(Specification): pass\n",
            );
            write(dir.path(), "pkg/other.py", "class Policy: pass\n");
            if name == "reexport_rebound" {
                write(
                    dir.path(),
                    "pkg/api.py",
                    "from .policy import Policy\nPolicy = object\n",
                );
            } else if name == "reexport_cycle" {
                write(dir.path(), "pkg/api.py", "from .bridge import Policy\n");
                write(dir.path(), "pkg/bridge.py", "from .api import Policy\n");
            }
            write(dir.path(), "pkg/child.py", source);
            let report = scan::scan(dir.path(), &["pkg".to_owned()]).unwrap();
            assert_eq!(
                report.specifications.len(),
                1,
                "{name}: {:?}",
                report.specifications
            );
            assert!(
                report
                    .candidates
                    .iter()
                    .filter(|c| c.path == "pkg/child.py")
                    .all(|c| !c.inside_specification),
                "{name}"
            );
            assert!(
                report
                    .specification_liveness
                    .iter()
                    .all(|s| s.status == SpecificationLivenessStatus::Unknown),
                "{name}: {:?}",
                report.specification_liveness
            );
        }
    }

    #[test]
    fn walrus_rebinding_never_establishes_specification_ancestry() {
        for (binding, import, base, reexport) in [
            (
                "if (Policy := object): pass",
                "from .policy import Policy",
                "Policy",
                false,
            ),
            (
                "(Policy := object)",
                "from .policy import Policy",
                "Policy",
                false,
            ),
            (
                "[(Policy := object) for _ in items]",
                "from .policy import Policy",
                "Policy",
                false,
            ),
            (
                "if (rules := other): pass",
                "import pkg.policy as rules",
                "rules.Policy",
                false,
            ),
            (
                "if (Policy := object): pass",
                "from .policy import Policy",
                "Policy",
                true,
            ),
        ] {
            let dir = tempdir().unwrap();
            write(
                dir.path(),
                "pkg/policy.py",
                "from specification_core import Specification\nclass Policy(Specification): pass\n",
            );
            let source = if reexport {
                write(dir.path(), "pkg/api.py", &format!("{import}\n{binding}\n"));
                "from .api import Policy\n".to_owned()
            } else {
                format!("{import}\n{binding}\n")
            };
            write(
                dir.path(),
                "pkg/child.py",
                &format!("{source}class Child({base}):\n    if enabled: apply()\n"),
            );
            let report = scan::scan(dir.path(), &["pkg".to_owned()]).unwrap();
            assert!(
                report.parse_issues.is_empty(),
                "{binding}: {:?}",
                report.parse_issues
            );
            assert_eq!(
                report.specifications.len(),
                1,
                "{binding}: {:?}",
                report.specifications
            );
            assert!(
                report
                    .candidates
                    .iter()
                    .filter(|c| c.path == "pkg/child.py")
                    .all(|c| !c.inside_specification),
                "{binding}"
            );
            assert!(live::measure(&report, None).unwrap().provisional);
        }
    }

    #[test]
    fn same_file_marker_ancestry_preserves_sibling_decisions() {
        let dir = tempdir().unwrap();
        write(
            dir.path(),
            "policy.py",
            "\
from typing import ClassVar, Literal
class Marked:
    __specmetrics_specification__: ClassVar[Literal['specification/v1']] = 'specification/v1'
class Child(Marked):
    if enabled: apply()
Child()
if unrelated: apply()
",
        );
        let report = scan::scan(dir.path(), &["policy.py".to_owned()]).unwrap();
        let metric = live::measure(&report, None).unwrap();
        assert_eq!(metric.live_specifications, 2);
        assert_eq!(metric.covered_candidates, 1);
        assert_eq!(metric.remaining_opportunities, 1);
        assert!(!metric.provisional);
    }

    #[test]
    fn unseeded_inheritance_cycles_and_same_named_unrelated_bases_are_not_specs() {
        let dir = tempdir().unwrap();
        write(
            dir.path(),
            "a.py",
            "from b import B\nclass A(B):\n    if enabled: apply()\n",
        );
        write(dir.path(), "b.py", "from a import A\nclass B(A): pass\n");
        write(
            dir.path(),
            "plain.py",
            "class Policy: pass\nclass Child(Policy):\n    if enabled: apply()\n",
        );
        let report = scan::scan(dir.path(), &[]).unwrap();
        assert!(report.specifications.is_empty());
        assert_eq!(report.candidates.len(), 2);
        assert!(report.candidates.iter().all(|c| !c.inside_specification));
    }
}
