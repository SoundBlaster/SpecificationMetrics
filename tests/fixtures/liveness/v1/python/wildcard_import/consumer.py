from dynamically_selected_rules import *


def should_promote(value: object) -> bool:
    return _Ready().is_satisfied_by(value)
