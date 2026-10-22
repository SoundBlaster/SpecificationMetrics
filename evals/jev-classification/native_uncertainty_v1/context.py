"""Facts prepared from a source-bound, SDK-validated native capture."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AxisMass:
    axis: str
    choice: str
    selected_mass: Decimal
    alternative_mass: Decimal
    reported_confidence: float | None


@dataclass(frozen=True)
class RoutingFacts:
    baseline_route: str
    incomplete: bool
    axes: tuple[AxisMass, ...]
