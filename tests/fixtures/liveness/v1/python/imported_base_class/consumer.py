from rules import Specification
from rules import _Ready as RuntimeRule


def should_promote() -> bool:
    return isinstance(RuntimeRule(), Specification)
