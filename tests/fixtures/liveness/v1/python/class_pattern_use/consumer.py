from rules import _Ready as RuntimeRule


def has_rule(value: object) -> bool:
    match value:
        case RuntimeRule():
            return True
        case _:
            return False
