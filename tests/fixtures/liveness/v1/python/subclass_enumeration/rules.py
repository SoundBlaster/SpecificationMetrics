class _Discovered(Specification[object]):
    def is_satisfied_by(self, value: object) -> bool:
        return bool(value)
