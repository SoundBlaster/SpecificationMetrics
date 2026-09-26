class _Ready(Specification[object]):
    def is_satisfied_by(self, value: object) -> bool:
        return bool(value)
