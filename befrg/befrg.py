"""Independent implementation of BEFRG Algorithm 1, with two DP backends.

The finite-state optimum is NOT a continuous-SoC optimum. In particular,
flooring can discard usable energy and cause unnecessary station visits.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import ceil, floor, inf, isfinite
from typing import Iterator, Literal

from .data import Problem
from .energy import arc_energy

Rounding = Literal["floor", "round", "ceil"]
Mode = Literal["DPC", "FC"]


@dataclass(frozen=True)
class Action:
    """One direct move or one detour followed by a discrete charge target."""

    kind: Literal["direct", "detour"]
    station_index: int | None
    charge_level: int | None
    next_b: int


@dataclass(frozen=True)
class Visit:
    """Arrival or departure event recorded in the *model* state trace."""

    node: str
    soc_kwh: float
    event: str
    elapsed_min: float


@dataclass(frozen=True)
class Solution:
    """Policy, discrete state trace and objective (all times in minutes)."""

    total_minutes: float
    actions: tuple[Action, ...]
    model_visits: tuple[Visit, ...]
    state_trace: tuple[int, ...]
    charging_minutes: float
    travel_minutes: float
    total_charge_kwh: float
    solver: str

    @property
    def full_path(self) -> tuple[str, ...]:
        """Physical visit order (initial depot, stations, original-route nodes)."""
        return tuple(v.node for v in self.model_visits
                     if v.event in ("initial", "station_arrival_model", "node_arrival_model"))

    @property
    def detours(self) -> int:
        """Number of charging stops selected by the policy."""
        return sum(a.kind == "detour" for a in self.actions)


class BEFRGSolver:
    """Finite-state DP with stable direct-first, station/level tie-breaking.

    ``strict_positive=False`` reproduces Algorithm 1's literal zero-state
    behavior; True (default) enforces Eq. 11 at every route node.
    ``safety_check=True`` independently validates continuous SoC and raises
    if the chosen plan is physically non-executable. It does not repair plans.
    """

    def __init__(self, problem: Problem, *, mode: Mode = "DPC",
                 rounding: Rounding = "floor", strict_positive: bool = True) -> None:
        if mode not in ("DPC", "FC") or rounding not in ("floor", "round", "ceil"):
            raise ValueError("Unknown mode or rounding")
        self.p = problem
        self.mode = mode
        self.rounding = rounding
        self.strict_positive = strict_positive
        self.rtime: dict[tuple[int, int], float] = {}
        self.policy: dict[tuple[int, int], Action | None] = {}
        self._direct = [arc_energy(problem, k)[0] for k in range(len(problem.route) - 1)]
        self._detours = [[arc_energy(problem, k, j) for j in range(len(problem.stations))]
                         for k in range(len(problem.route) - 1)]

    def _quantize(self, energy: float) -> int:
        # Numerical tolerance avoids loss of a grid unit on exact multiples.
        ratio = energy / self.p.rc
        if self.rounding == "floor":
            state = floor(ratio + 1e-11)
        elif self.rounding == "ceil":
            state = ceil(ratio - 1e-11)
        else:
            state = floor(ratio + 0.5 + 1e-11)
        return min(self.p.Gamma, max(0, state))

    def _valid_state(self, b: int) -> bool:
        return (1 if self.strict_positive else 0) <= b <= self.p.Gamma

    def _transitions(self, k: int, b: int) -> Iterator[tuple[float, Action]]:
        """Enumerate (immediate cost, action), in deterministic order."""
        p = self.p
        current = b * p.rc
        u, v = p.route[k:k + 2]
        e_direct = self._direct[k]
        if isfinite(e_direct) and current + 1e-10 >= e_direct:
            next_b = self._quantize(max(0., current - e_direct))
            if self._valid_state(next_b):
                yield p.distance(u, v) / p.speed, Action("direct", None, None, next_b)
        for j, station in enumerate(p.stations):
            e1, e2 = self._detours[k][j]
            if not isfinite(e1) or not isfinite(e2) or current + 1e-10 < e1:
                continue
            arrival = max(0.0, current - e1)
            if self.mode == "FC":
                charge_levels = (p.gamma,)
            else:
                first = max(1, floor(arrival / p.ch + 1e-11) + 1)
                charge_levels = range(first, p.gamma + 1)
            for level in charge_levels:
                target = level * p.ch
                if target <= arrival + 1e-10 or target + 1e-10 < e2:
                    continue
                next_b = self._quantize(max(0.0, target - e2))
                if not self._valid_state(next_b):
                    continue
                travel = (p.distance(u, station.node) + p.distance(station.node, v)) / p.speed
                cost = travel + station.curve.charging_time(arrival, target)
                yield cost, Action("detour", j, level, next_b)

    def top_down(self, *, safety_check: bool = False) -> Solution:
        """Recursive memoized BEFRG, practical for moderate route length."""
        self.rtime.clear()
        self.policy.clear()
        n = len(self.p.route)

        @lru_cache(maxsize=None)
        def dp(k: int, b: int) -> float:
            if not self._valid_state(b):
                return inf
            if k == n - 1:
                self.rtime[k, b] = 0.0
                self.policy[k, b] = None
                return 0.0
            best = inf
            action_best: Action | None = None
            for immediate, action in self._transitions(k, b):
                result = immediate + dp(k + 1, action.next_b)
                if result < best - 1e-10:
                    best, action_best = result, action
            self.rtime[k, b] = best
            self.policy[k, b] = action_best
            return best

        objective = dp(0, self.p.Gamma)
        return self._reconstruct(objective, "top_down", safety_check)

    def bottom_up(self, *, safety_check: bool = False) -> Solution:
        """Iterative backward DP; avoids recursion limit even for 1600 nodes."""
        self.rtime.clear()
        self.policy.clear()
        n = len(self.p.route)
        for b in range(0 if not self.strict_positive else 1, self.p.Gamma + 1):
            self.rtime[n - 1, b] = 0.0
            self.policy[n - 1, b] = None
        for k in range(n - 2, -1, -1):
            for b in range(0 if not self.strict_positive else 1, self.p.Gamma + 1):
                best = inf
                chosen: Action | None = None
                for immediate, action in self._transitions(k, b):
                    candidate = immediate + self.rtime.get((k + 1, action.next_b), inf)
                    if candidate < best - 1e-10:
                        best, chosen = candidate, action
                self.rtime[k, b] = best
                self.policy[k, b] = chosen
        return self._reconstruct(self.rtime[0, self.p.Gamma], "bottom_up", safety_check)

    def _reconstruct(self, objective: float, backend: str, safety_check: bool) -> Solution:
        if not isfinite(objective):
            raise ValueError("No feasible discretized policy on this graph")
        p = self.p
        b = p.Gamma
        actions: list[Action] = []
        events: list[Visit] = [Visit(p.route[0].id, p.battery, "initial", 0.0)]
        states = [b]
        travel_time = 0.0
        charging_time = 0.0
        charge_amount = 0.0
        for k in range(len(p.route) - 1):
            a = self.policy[k, b]
            if a is None:
                raise RuntimeError(f"Policy missing at {(k,b)}")
            actions.append(a)
            if a.kind == "direct":
                travel_time += p.distance(p.route[k], p.route[k + 1]) / p.speed
            else:
                assert a.station_index is not None and a.charge_level is not None
                station = p.stations[a.station_index]
                e1, _ = self._detours[k][a.station_index]
                arrival = b * p.rc - e1
                target = a.charge_level * p.ch
                leg1_time = p.distance(p.route[k], station.node) / p.speed
                leg2_time = p.distance(station.node, p.route[k + 1]) / p.speed
                travel_time += leg1_time
                events.append(Visit(station.node.id, arrival, "station_arrival_model",
                                    travel_time + charging_time))
                charge_amount += target - arrival
                charging_time += station.curve.charging_time(arrival, target)
                events.append(Visit(station.node.id, target, "station_departure_model",
                                    travel_time + charging_time))
                travel_time += leg2_time
            b = a.next_b
            states.append(b)
            events.append(Visit(p.route[k + 1].id, b * p.rc, "node_arrival_model",
                                travel_time + charging_time))
        result = Solution(objective, tuple(actions), tuple(events), tuple(states),
                          charging_time, travel_time, charge_amount, backend)
        if abs(result.total_minutes - travel_time - charging_time) > 1e-7:
            raise AssertionError("Policy reconstruction differs from objective")
        if safety_check:
            from .validate import validate_solution
            validation = validate_solution(p, result)
            if not validation.feasible:
                raise ValueError(f"Continuous verification failed: {validation.errors}")
        return result
