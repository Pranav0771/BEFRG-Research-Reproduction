"""Independent exponentially expensive search baselines for small instances."""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, inf, isfinite
from ..data import Problem
from ..energy import energy_rate


@dataclass(frozen=True)
class BaselineResult:
    """Objective, number of evaluated states and enumerated full solutions."""

    minutes: float
    calls: int
    feasible_plans: int


def exhaustive(problem: Problem, *, memoize: bool = False,
               full_charge: bool = False, max_calls: int = 500_000) -> BaselineResult:
    """Explore every candidate recursively; optional memoization for comparison.

    Deliberately does not import BEFRGSolver or its transition function.
    The test baseline enforces strictly positive route-node battery states.
    """
    rc, ch = problem.rc, problem.ch
    count = 0
    leaves = 0
    cache: dict[tuple[int, int], float] = {}

    def recurse(k: int, b: int) -> float:
        nonlocal count, leaves
        count += 1
        if count > max_calls:
            raise RuntimeError("Brute-force call budget exceeded")
        if b <= 0:
            return inf
        if k == len(problem.route) - 1:
            leaves += 1
            return 0.0
        key = (k, b)
        if memoize and key in cache:
            return cache[key]
        u, v = problem.route[k:k+2]
        rate = energy_rate(problem, k + 1)
        start = b * rc
        best = inf
        d = problem.distance(u, v)
        if isfinite(d) and start + 1e-10 >= d * rate:
            nxt = floor((start - d * rate) / rc + 1e-11)
            if nxt >= 1:
                best = min(best, d / problem.speed + recurse(k + 1, nxt))
        for station in problem.stations:
            d1 = problem.distance(u, station.node)
            d2 = problem.distance(station.node, v)
            if not isfinite(d1) or not isfinite(d2) or start + 1e-10 < d1 * rate:
                continue
            incoming = start - d1 * rate
            for level in (range(problem.gamma, problem.gamma + 1) if full_charge
                          else range(max(1, floor(incoming / ch + 1e-11) + 1), problem.gamma + 1)):
                target = level * ch
                if target <= incoming + 1e-10 or target + 1e-10 < d2 * rate:
                    continue
                nxt = floor((target - d2 * rate) / rc + 1e-11)
                if nxt <= 0:
                    continue
                ctime = station.curve.charging_time(incoming, target)
                best = min(best, (d1 + d2) / problem.speed + ctime + recurse(k + 1, nxt))
        if memoize:
            cache[key] = best
        return best

    result = recurse(0, problem.Gamma)
    return BaselineResult(result, count, leaves)


def no_memo(problem: Problem, *, max_calls: int = 500_000) -> BaselineResult:
    """Convenience alias for un-memoized Algorithm 1 recursion."""
    return exhaustive(problem, max_calls=max_calls)
