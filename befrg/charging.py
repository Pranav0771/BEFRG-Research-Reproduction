"""Exact piecewise-linear charge times, in kWh and minutes (Eqs. 1–3)."""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class ChargingCurve:
    """Cumulative energy ``z`` (kWh) and time ``x`` (minutes)."""

    z: tuple[float, ...]
    x: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.z) != len(self.x) or len(self.z) < 2:
            raise ValueError("Charging breakpoints must be equally sized, with >=2 entries")
        if not isclose(self.z[0], 0.0, abs_tol=1e-9) or not isclose(self.x[0], 0.0, abs_tol=1e-9):
            raise ValueError("Charging curves must start at (0,0)")
        if any(b <= a for a, b in zip(self.z, self.z[1:])):
            raise ValueError("Charge levels must increase strictly")
        if any(b <= a for a, b in zip(self.x, self.x[1:])):
            raise ValueError("Charging times must increase strictly")

    @property
    def capacity(self) -> float:
        """Full battery capacity represented by this charging curve."""
        return self.z[-1]

    def charging_time(self, arrival: float, target: float) -> float:
        """Return charging duration, using exact segment intersections."""
        eps = 1e-9
        if arrival < -eps or target > self.capacity + eps or target + eps < arrival:
            raise ValueError(f"Invalid charge interval {arrival} -> {target}")
        arrival = max(0.0, arrival)
        target = min(self.capacity, target)
        if target <= arrival:
            return 0.0
        minutes = 0.0
        for i in range(1, len(self.z)):
            overlap = max(0.0, min(target, self.z[i]) - max(arrival, self.z[i - 1]))
            slope = (self.z[i] - self.z[i - 1]) / (self.x[i] - self.x[i - 1])
            minutes += overlap / slope
        return minutes


STATION_CURVES: dict[str, ChargingCurve] = {
    "fast": ChargingCurve((0.0, 13.6, 15.2, 16.0), tuple(v * 60 for v in (0, .31, .39, .51))),
    "normal": ChargingCurve((0.0, 13.6, 15.2, 16.0), tuple(v * 60 for v in (0, .62, .77, 1.01))),
    "slow": ChargingCurve((0.0, 13.6, 15.2, 16.0), tuple(v * 60 for v in (0, 1.26, 1.54, 2.04))),
}
