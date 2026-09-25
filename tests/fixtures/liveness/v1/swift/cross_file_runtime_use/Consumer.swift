func shouldPromote(_ value: Bool) -> Bool {
    let rule = _Ready()
    if rule.isSatisfiedBy(value) { return true }
    return false
}
