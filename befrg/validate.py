"""Independent continuous-SoC route replay; never use the DP's floored trace."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .befrg import Solution
from .data import Problem
from .energy import energy_rate


@dataclass(frozen=True)
class ActualVisit:
    """Continuous state after reaching a node/station or charging."""

    node: str
    soc_kwh: float
    elapsed_min: float
    event: str


@dataclass(frozen=True)
class Validation:
    """Results of an entirely independent physical route replay."""

    feasible: bool
    errors: tuple[str, ...]
    visits: tuple[ActualVisit, ...]
    total_minutes: float
    total_charged_kwh: float
    final_soc_kwh: float


def validate_solution(problem: Problem, solution: Solution,
                      *, require_actual_charging: bool = True) -> Validation:
    """Verify actual SoC and charge targets with no intermediate flooring.

    A station visit charging target already reached by the *physical*
    trajectory is invalid if require_actual_charging=True, even if the
    rounded DP state made the nominal target appear larger.
    """
    errors: list[str] = []
    soc = problem.battery
    t = 0.0
    charged = 0.0
    visits = [ActualVisit(problem.route[0].id, soc, t, "initial")]
    if len(solution.actions) != len(problem.route) - 1:
        raise ValueError("Policy length does not match route")
    for k, action in enumerate(solution.actions):
        u, v = problem.route[k:k + 2]
        rate = energy_rate(problem, k + 1)
        legs = [(u, v)]
        station = None
        if action.kind == "detour":
            if action.station_index is None or action.charge_level is None:
                raise ValueError("Malformed station action")
            station = problem.stations[action.station_index]
            legs = [(u, station.node), (station.node, v)]
        for leg_i, (a, b) in enumerate(legs):
            distance = problem.distance(a, b)
            if not isfinite(distance):
                errors.append(f"Arc {a.id}->{b.id} unavailable")
                continue
            energy = rate * distance
            soc -= energy
            t += distance / problem.speed
            if soc < -1e-8:
                errors.append(f"Negative SoC on arc {a.id}->{b.id}: {soc:.6f}")
            if station is not None and leg_i == 0:
                if soc < -1e-8:
                    errors.append("Negative SoC at charging station")
                visits.append(ActualVisit(b.id, soc, t, "station_arrival"))
                target = action.charge_level * problem.ch
                if target <= soc + 1e-9:
                    if require_actual_charging:
                        errors.append(f"Non-increasing physical charge at {b.id}: {soc:.6f} -> {target:.6f}")
                else:
                    if target > problem.battery + 1e-9:
                        errors.append("Target exceeds battery capacity")
                    else:
                        t += station.curve.charging_time(max(soc, 0.), target)
                        charged += target - soc
                        soc = target
                visits.append(ActualVisit(b.id, soc, t, "station_departure"))
        if soc <= 1e-9:
            errors.append(f"Non-positive SoC at route node {v.id}: {soc:.6f}")
        if soc > problem.battery + 1e-8:
            errors.append("Battery capacity exceeded")
        visits.append(ActualVisit(v.id, soc, t, "node_arrival"))
    return Validation(not errors, tuple(errors), tuple(visits), t, charged, soc)
