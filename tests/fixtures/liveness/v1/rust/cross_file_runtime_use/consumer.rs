fn should_promote(value: bool) -> bool {
    let rule = crate::rules::_Ready;
    if rule.is_satisfied_by(&value) { true } else { false }
}
