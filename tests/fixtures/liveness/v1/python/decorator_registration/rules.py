class Registry:
    def register(self, rule):
        return rule


registry = Registry()


@registry.register
class _Registered(Specification[object]):
    def is_satisfied_by(self, value: object) -> bool:
        return bool(value)
