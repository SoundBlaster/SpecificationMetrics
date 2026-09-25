fn resolve_rule(name: &str) -> Option<Box<dyn Specification<bool>>> {
    plugin_registry::resolve(name)
}
