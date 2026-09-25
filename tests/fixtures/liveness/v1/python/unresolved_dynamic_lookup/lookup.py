def resolve_rule(name: str) -> object:
    return globals()[name]()
