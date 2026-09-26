from rules import _RegisteredRule
from specification_runtime import registry


registry.register("ready", lambda: _RegisteredRule())
