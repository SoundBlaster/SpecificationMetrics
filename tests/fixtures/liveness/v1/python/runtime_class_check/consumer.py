from rules import _Ready as RuntimeRule


def has_rule(value: object) -> bool:
    return isinstance(value, (RuntimeRule, str))
