import rules as rule_module


def should_promote(value: object) -> bool:
    return rule_module._Ready().is_satisfied_by(value)
