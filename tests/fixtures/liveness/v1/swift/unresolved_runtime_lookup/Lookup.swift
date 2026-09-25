func resolveRule(_ configuredName: String) -> AnyClass? {
    NSClassFromString(configuredName)
}
