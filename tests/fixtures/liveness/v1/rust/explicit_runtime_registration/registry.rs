inventory::submit! {
    SpecificationFactory::new("ready", || Box::new(crate::rules::_RegisteredRule))
}
