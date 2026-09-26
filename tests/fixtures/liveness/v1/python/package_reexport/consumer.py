from package import Ready as RuntimeRule
import package


def should_promote(value: object) -> bool:
    return RuntimeRule().is_satisfied_by(value) and package.Ready().is_satisfied_by(value)
