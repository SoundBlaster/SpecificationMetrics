from specification_core import Specification


class _RegisteredRule(Specification[object]):
    def is_satisfied_by(self, value: object) -> bool:
        return bool(value)
