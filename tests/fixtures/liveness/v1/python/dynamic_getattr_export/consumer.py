import package


def should_promote(value: object) -> bool:
    return package.Ready().is_satisfied_by(value)
