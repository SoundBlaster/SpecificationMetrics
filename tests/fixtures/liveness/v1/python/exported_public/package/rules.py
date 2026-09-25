from specification_core import Specification


class Published(Specification[object]):
    def is_satisfied_by(self, value: object) -> bool:
        return bool(value)
