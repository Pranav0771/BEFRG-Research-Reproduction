"""Delivery-load-dependent energy consumption (Mandal et al., Eqs. 4–6)."""
from __future__ import annotations

from .data import Problem


def residual_load(problem: Problem, destination_index: int) -> float:
    """Load remaining immediately before serving the destination node."""
    if not 0 <= destination_index < len(problem.route):
        raise IndexError(destination_index)
    return sum(v.demand for v in problem.route[destination_index:])


def energy_rate(problem: Problem, destination_index: int) -> float:
    """Consumption (kWh/km) for an arc ending at destination_index."""
    return problem.theta * (problem.veh_mass + residual_load(problem, destination_index))


def arc_energy(problem: Problem, k: int, station_index: int | None = None) -> tuple[float, float]:
    """Return (first-leg, second-leg) energy for route arc k->k+1.

    Both detour legs use L(v_(k+1)); no deliveries occur at the station.
    Direct travel returns (direct_energy, 0).
    """
    if not 0 <= k < len(problem.route) - 1:
        raise IndexError(k)
    u, v = problem.route[k:k + 2]
    rate = energy_rate(problem, k + 1)
    if station_index is None:
        return rate * problem.distance(u, v), 0.0
    station = problem.stations[station_index].node
    return rate * problem.distance(u, station), rate * problem.distance(station, v)
