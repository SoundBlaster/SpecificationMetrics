from missing_runtime_module import _Ready


def should_promote(value: object) -> bool:
    return _Ready().is_satisfied_by(value)
