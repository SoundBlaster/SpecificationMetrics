from . import rules as _rules


def __getattr__(name: str) -> object:
    return _rules.__dict__[name]
