import package.rules


def should_promote(value: object) -> bool:
    return package.rules._Ready().is_satisfied_by(value)
