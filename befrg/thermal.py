"""Temperature, HVAC and charging-throughput surrogate extensions.

All parameters are configurable *assumptions*, not calibrated cell models.
Temperature is held constant across one route; ``health_fraction`` is a
fixed input, NOT a battery-health state transition.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .charging import ChargingCurve
from .data import Problem
from .energy import residual_load


@dataclass(frozen=True)
class ThermalConfig:
    """A bounded asymmetric capacity derating and HVAC power model.

    ``alpha_*`` have units degC^-2; ``heat_kw_per_c`` and ``cool_kw_per_c``
    are kW/degC. The degradation weight is *equivalent minutes* per unit
    normalized charge-increment raised to beta; it is not measured aging.
    """

    temperature_c: float = 25.0
    reference_c: float = 25.0
    health_fraction: float = 1.0
    alpha_cold: float = 0.00045
    alpha_hot: float = 0.00012
    minimum_capacity_fraction: float = 0.35
    heat_below_c: float = 19.0
    cool_above_c: float = 27.0
    heat_kw_per_c: float = 0.16
    cool_kw_per_c: float = 0.12
    hvac_max_kw: float = 6.0
    degradation_weight_min: float = 0.0
    degradation_beta: float = 1.4

    def __post_init__(self) -> None:
        values = vars(self)
        if any(not isfinite(float(v)) for v in values.values()):
            raise ValueError('Thermal parameters must be finite')
        if not (0.0 < self.health_fraction <= 1.0):
            raise ValueError('SOH fraction must be in (0, 1]')
        if not (0.0 < self.minimum_capacity_fraction <= 1.0):
            raise ValueError('Capacity floor must be in (0, 1]')
        if self.alpha_cold < 0 or self.alpha_hot < 0:
            raise ValueError('Temperature derating coefficients must be nonnegative')
        if self.heat_below_c > self.cool_above_c:
            raise ValueError('HVAC comfort-band limits are reversed')
        if min(self.heat_kw_per_c,self.cool_kw_per_c,self.hvac_max_kw,
               self.degradation_weight_min) < 0:
            raise ValueError('HVAC and degradation coefficients must be nonnegative')
        if self.degradation_beta < 1.0:
            raise ValueError('beta >= 1 required for this nonnegative convex surrogate')

    def usable_capacity(self, nominal_capacity_kwh: float) -> float:
        """Usable capacity at a constant temperature and state of health."""
        if nominal_capacity_kwh <= 0:
            raise ValueError('Nominal capacity must be positive')
        cold = max(0.0, self.reference_c - self.temperature_c)
        hot = max(0.0, self.temperature_c - self.reference_c)
        factor = max(self.minimum_capacity_fraction,
                     1.0 - self.alpha_cold*cold*cold - self.alpha_hot*hot*hot)
        return nominal_capacity_kwh * self.health_fraction * factor

    def hvac_kw(self) -> float:
        """Auxiliary consumption while driving, zero inside comfort band."""
        heat = self.heat_kw_per_c * max(0.0, self.heat_below_c - self.temperature_c)
        cool = self.cool_kw_per_c * max(0.0, self.temperature_c - self.cool_above_c)
        return min(self.hvac_max_kw, heat + cool)

    def charge_penalty_min(self, arrival: float, target: float,
                           usable_capacity: float) -> float:
        """Nonnegative throughput surrogate, NOT true lifetime wear estimation."""
        delta = max(0.0, target - arrival)
        return self.degradation_weight_min * (delta / usable_capacity) ** self.degradation_beta


def derated_curve(curve: ChargingCurve, usable_capacity_kwh: float) -> ChargingCurve:
    """Scale SoC breakpoints but preserve time at normalized SoC.

    Assumes a charger delivering the same C-rate at every normalized SoC.
    This does not model temperature-driven charge power limits/thermal throttling.
    """
    factor = usable_capacity_kwh / curve.capacity
    if factor <= 0 or factor > 1 + 1e-9:
        raise ValueError('Derated battery capacity must be in (0, nominal capacity]')
    return ChargingCurve(tuple(z * factor for z in curve.z), curve.x)


def temperature_arc_energy(problem: Problem, k: int, thermal: ThermalConfig,
                           station_index: int | None = None) -> tuple[float, float]:
    """Traction energy plus HVAC power times travel hours, per route leg."""
    if k < 0 or k + 1 >= len(problem.route):
        raise IndexError(k)
    u, v = problem.route[k:k + 2]
    rate = problem.theta * (problem.veh_mass + residual_load(problem, k + 1))
    rate += thermal.hvac_kw() / (60.0 * problem.speed)
    if station_index is None:
        return (rate * problem.distance(u, v), 0.0)
    c = problem.stations[station_index].node
    return rate * problem.distance(u, c), rate * problem.distance(c, v)
