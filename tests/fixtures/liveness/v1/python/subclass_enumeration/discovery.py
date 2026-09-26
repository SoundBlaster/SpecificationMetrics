def available_rules() -> list[type]:
    return Specification.__subclasses__()
