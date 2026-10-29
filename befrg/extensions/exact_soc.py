"""Exact continuous-SoC label DP with *discrete charging targets*.

An independent comparison for the paper's floor-projected DP. Charging targets
remain l*ch; battery states do NOT get rounded. In contrast to continuous MILP,
this does NOT optimize arbitrary real charge targets. Labels with identical
energy (up to 1e-9 kWh) retain the cheapest prefix; no unsafe dominance tests.

After a detour, SoC is target minus the second-leg energy, independent of the
incoming label. This makes exact-state label counts finite and polynomial for
a fixed tour even though continuous SoC is tracked between stops.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, inf, isfinite
from time import perf_counter

from befrg.befrg import Action, Solution, Visit
from befrg.data import Problem
from befrg.energy import arc_energy
from befrg.validate import validate_solution


@dataclass(frozen=True)
class Label:
    """A least-cost partial route reaching an exact SoC at a given node."""

    position: int
    soc: float
    elapsed: float
    parent: int | None
    action: Action | None
    immediate_travel: float
    immediate_charge_time: float
    charge_added: float
    station_arrival_soc: float | None


@dataclass(frozen=True)
class LabelResult:
    """Best physically realizable policy and label search statistics."""

    solution: Solution
    labels_created: int
    transitions_examined: int
    maximum_frontier: int
    wall_seconds: float


def solve_exact_discrete_targets(problem: Problem, *, full_charge: bool = False,
                                 max_labels: int = 1_000_000) -> LabelResult:
    """Shortest path through continuous energy labels and discrete charge targets.

    Correct for a fixed directed graph, at most one station per original arc,
    piecewise-linear charge times, and strictly positive energy at route nodes.
    Battery zero may be reached at a station (as allowed by Eq. 12).

    Label keys round SoC to 9 decimals for floating-point deduplication. This
    is a numerical tolerance, NOT a coarse residual-energy state grid.
    """
    start = perf_counter()
    p = problem
    labels: list[Label] = [Label(0, p.battery, 0., None, None, 0., 0., 0., None)]
    current: dict[int, int] = {round(p.battery * 1e9): 0}
    transitions = 0
    max_frontier = 1
    for k in range(len(p.route) - 1):
        u, v = p.route[k:k + 2]
        nd: dict[int, int] = {}
        e_direct = arc_energy(p, k)[0]
        candidates_energy = [arc_energy(p, k, j) for j in range(len(p.stations))]

        def push(soc: float, cost: float, parent: int, action: Action,
                 travel: float, charging: float, added: float,
                 arrival: float | None) -> None:
            if soc <= 1e-9 or soc > p.battery + 1e-8:
                return
            key = round(soc * 1e9)
            existing = nd.get(key)
            if existing is not None and cost >= labels[existing].elapsed - 1e-10:
                return
            if len(labels) >= max_labels:
                raise RuntimeError(f'Exact-SoC label limit {max_labels} exceeded')
            labels.append(Label(k + 1, soc, cost, parent, action, travel, charging,
                                added, arrival))
            nd[key] = len(labels) - 1

        for index in current.values():
            source = labels[index]
            soc = source.soc
            if isfinite(e_direct) and soc - e_direct > 1e-9:
                transitions += 1
                tt = p.distance(u, v) / p.speed
                next_soc = soc - e_direct
                push(next_soc, source.elapsed + tt, index,
                     Action('direct', None, None, max(0, floor(next_soc/p.rc + 1e-10))),
                     tt, 0., 0., None)
            for j, station in enumerate(p.stations):
                e1, e2 = candidates_energy[j]
                if not all(map(isfinite, (e1, e2))) or soc + 1e-10 < e1:
                    continue
                arrival = max(0., soc-e1)
                choices = (p.gamma,) if full_charge else range(
                    max(1, floor(arrival/p.ch + 1e-10) + 1), p.gamma+1)
                for level in choices:
                    target = level*p.ch
                    if target <= arrival + 1e-9 or target-e2 <= 1e-9:
                        continue
                    transitions += 1
                    tt = (p.distance(u,station.node)+p.distance(station.node,v))/p.speed
                    ct = station.curve.charging_time(arrival,target)
                    new_soc = target-e2
                    push(new_soc, source.elapsed+tt+ct,index,
                         Action('detour',j,level,max(0,floor(new_soc/p.rc+1e-10))),
                         tt,ct,target-arrival,arrival)
        if not nd:
            raise ValueError(f'No continuous-SoC discrete-target route at leg {k}')
        current = nd
        max_frontier = max(max_frontier,len(current))

    best_index = min(current.values(),key=lambda i:labels[i].elapsed)
    chosen: list[Label] = []
    i = best_index
    while labels[i].parent is not None:
        chosen.append(labels[i])
        i = labels[i].parent  # type: ignore[assignment]
    chosen.reverse()

    model_visits=[Visit(p.route[0].id,p.battery,'initial',0.)]
    actions=[]; states=[p.Gamma]; travel=charging=total_added=elapsed=0.
    for k, item in enumerate(chosen):
        assert item.action is not None
        action=item.action
        actions.append(action)
        if action.kind=='detour':
            assert action.station_index is not None and action.charge_level is not None
            station=p.stations[action.station_index]
            leg1=p.distance(p.route[k],station.node)/p.speed
            model_visits.append(Visit(station.node.id,float(item.station_arrival_soc),
                                      'station_arrival_model',elapsed+leg1))
            model_visits.append(Visit(station.node.id,action.charge_level*p.ch,
                                      'station_departure_model',elapsed+leg1+item.immediate_charge_time))
        elapsed=item.elapsed
        travel+=item.immediate_travel
        charging+=item.immediate_charge_time
        total_added+=item.charge_added
        states.append(action.next_b)
        model_visits.append(Visit(p.route[k+1].id,item.soc,'node_arrival_model',elapsed))
    solution=Solution(labels[best_index].elapsed,tuple(actions),tuple(model_visits),
                      tuple(states),charging,travel,total_added,'exact_soc_labels')
    check=validate_solution(p,solution)
    if not check.feasible or abs(check.total_minutes-solution.total_minutes)>1e-7:
        raise AssertionError(f'Exact-label reconstruction failed: {check.errors}')
    return LabelResult(solution,len(labels),transitions,max_frontier,perf_counter()-start)
