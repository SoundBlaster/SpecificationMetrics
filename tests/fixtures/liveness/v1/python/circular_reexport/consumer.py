from package.a import Ready as RuntimeRule


def should_promote(value: object) -> bool:
    return RuntimeRule().is_satisfied_by(value)
