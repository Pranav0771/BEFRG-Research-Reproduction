"""Exact-SoC label DP over a finite charge-target set (new extension #1).

Unlike BEFRG, this forward DP preserves *physical* SoC between all nodes,
never rounds it to a battery-state grid, and only considers charge targets
strictly above the true station arrival SoC. No unsound SoC dominance rule is
used: only equal SoC states are merged. This is exact for the specified
finite charge target set when ``max_labels_per_stage=None``; it is NOT the
unrestricted continuous-charging optimum.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, inf, isfinite
from typing import Literal

from .befrg import Action, Solution, Visit
from .data import Problem
from .energy import energy_rate
from .thermal import ThermalConfig, derated_curve, temperature_arc_energy


@dataclass(frozen=True)
class PhysicalResult:
    """Solution, time-equivalent objective and label-search accounting."""
    solution: Solution
    objective_equivalent_min: float
    degradation_penalty_min: float
    effective_capacity_kwh: float
    labels_created: int
    max_labels_at_stage: int
    certified_grid_optimal: bool


@dataclass(slots=True)
class _Label:
    soc: float
    objective: float
    time_min: float
    travel_min: float
    charging_min: float
    charge_kwh: float
    penalty_min: float
    prior: _Label | None
    action_kind: str = 'start'
    station_index: int | None = None
    charge_level: int | None = None


def solve_physical_grid(problem: Problem, *, mode: Literal['DPC','FC']='DPC',
                        thermal: ThermalConfig | None = None,
                        max_labels_per_stage: int | None = None,
                        dominance_pruning: bool = False) -> PhysicalResult:
    """Shortest path on exact physical SoC labels for discrete target levels.

    Only station target charge is gridded; route-node SoC is never rounded.
    An optional beam limit is heuristic and sets certified_grid_optimal=False.
    ``dominance_pruning=True`` is exact under the triangle inequality and
    a nonnegative monotone cost per charge increment (as in this model):
    at one route node, higher SoC at lower/equal cost dominates lower SoC.
    Restricted to Euclidean geometry to avoid sparse/directed detour errors.
    In a sparse graph unavailable detour distances remain unavailable.
    """
    if mode not in ('DPC','FC'):
        raise ValueError('Invalid charging mode')
    if max_labels_per_stage is not None and max_labels_per_stage < 1:
        raise ValueError('Beam limit must be positive')
    if dominance_pruning and (not problem.euclidean_fallback or problem.distances):
        raise ValueError('SoC dominance pruning requires Euclidean complete metric distances')
    B = thermal.usable_capacity(problem.battery) if thermal else problem.battery
    curves = tuple(derated_curve(s.curve, B) if thermal else s.curve
                   for s in problem.stations)
    root = _Label(B, 0., 0., 0., 0., 0., 0., None)
    current: dict[float, _Label] = {round(B, 11): root}
    generated, max_seen = 1, 1
    pruned = False
    eps = 1e-9

    def update(dest: dict[float, _Label], label: _Label) -> None:
        nonlocal generated
        generated += 1
        key = round(label.soc, 11)
        prev = dest.get(key)
        if prev is None or label.objective < prev.objective - 1e-10:
            dest[key] = label

    for k, (u, v) in enumerate(zip(problem.route, problem.route[1:])):
        rate = energy_rate(problem, k + 1)
        rate += thermal.hvac_kw() / (60 * problem.speed) if thermal else 0.
        d_direct = problem.distance(u, v)
        next_stage: dict[float, _Label] = {}
        for prior in current.values():
            if isfinite(d_direct):
                soc = prior.soc - rate*d_direct
                if soc > eps:
                    dt = d_direct/problem.speed
                    update(next_stage, _Label(soc,prior.objective+dt,
                           prior.time_min+dt,prior.travel_min+dt,
                           prior.charging_min,prior.charge_kwh,prior.penalty_min,
                           prior,'direct'))
            for j, station in enumerate(problem.stations):
                d1 = problem.distance(u,station.node)
                d2 = problem.distance(station.node,v)
                if not (isfinite(d1) and isfinite(d2)):
                    continue
                arrival = prior.soc - rate*d1
                if arrival < -eps:
                    continue
                arrival = max(0.0, arrival)
                if mode == 'FC':
                    levels = (problem.gamma,)
                else:
                    first = max(1, floor(arrival/(B/problem.gamma)+1e-10)+1)
                    levels = range(first,problem.gamma+1)
                for level in levels:
                    target = B*level/problem.gamma
                    if target <= arrival + eps:
                        continue
                    soc = target-rate*d2
                    if soc <= eps:
                        continue
                    dt_travel = (d1+d2)/problem.speed
                    dt_charge = curves[j].charging_time(arrival,target)
                    penalty = (thermal.charge_penalty_min(arrival,target,B)
                               if thermal else 0.)
                    update(next_stage, _Label(soc,prior.objective+dt_travel+dt_charge+penalty,
                           prior.time_min+dt_travel+dt_charge,
                           prior.travel_min+dt_travel,
                           prior.charging_min+dt_charge,
                           prior.charge_kwh+target-arrival,
                           prior.penalty_min+penalty,prior,'detour',j,level))
        if not next_stage:
            raise ValueError(f'No physically executable policy at stage {k}')
        max_seen = max(max_seen, len(next_stage))
        if dominance_pruning:
            # Higher SoC is no worse at any subsequent arc when direct
            # Euclidean travel is available; charging shorter to the same
            # target cannot cost more. Compare against all higher-SoC labels.
            survivors: dict[float, _Label] = {}
            cheapest_higher = float('inf')
            for key in sorted(next_stage, reverse=True):
                label = next_stage[key]
                if label.objective < cheapest_higher - 1e-10:
                    survivors[key] = label
                    cheapest_higher = label.objective
            next_stage = survivors
        if max_labels_per_stage is not None and len(next_stage)>max_labels_per_stage:
            ordered = sorted(next_stage.values(),key=lambda s:(s.objective,-s.soc))
            next_stage = {round(s.soc,11):s for s in ordered[:max_labels_per_stage]}
            pruned = True
        current = next_stage
    end = min(current.values(),key=lambda s:(s.objective,-s.soc))
    labels: list[_Label] = []
    p: _Label | None = end
    while p is not None:
        labels.append(p)
        p=p.prior
    labels.reverse()
    if len(labels) != len(problem.route):
        raise RuntimeError('Label parent chain is malformed')
    actions = []
    visits = [Visit(problem.route[0].id,B,'initial',0.)]
    states = [problem.Gamma]
    for k in range(len(problem.route)-1):
        prior, nxt = labels[k:k+2]
        if nxt.action_kind=='direct':
            b=min(problem.Gamma,max(0,floor((nxt.soc/B)*problem.Gamma+1e-10)))
            actions.append(Action('direct',None,None,b))
        else:
            j, level = nxt.station_index, nxt.charge_level
            assert j is not None and level is not None
            station = problem.stations[j]
            rate = energy_rate(problem,k+1)
            rate += thermal.hvac_kw()/(60*problem.speed) if thermal else 0.
            d1 = problem.distance(problem.route[k],station.node)
            arrival = max(0.0,prior.soc-rate*d1)
            target = level*B/problem.gamma
            t_arrive = prior.time_min+d1/problem.speed
            t_depart = t_arrive+curves[j].charging_time(arrival,target)
            visits.append(Visit(station.node.id,arrival,'station_arrival_model',t_arrive))
            visits.append(Visit(station.node.id,target,'station_departure_model',t_depart))
            b=min(problem.Gamma,max(0,floor((nxt.soc/B)*problem.Gamma+1e-10)))
            actions.append(Action('detour',j,level,b))
        states.append(b)
        visits.append(Visit(problem.route[k+1].id,nxt.soc,'node_arrival_model',nxt.time_min))
    sol = Solution(end.time_min,tuple(actions),tuple(visits),tuple(states),
                   end.charging_min,end.travel_min,end.charge_kwh,
                   'physical_grid' if thermal is None else 'physical_grid_thermal')
    assert abs(sol.total_minutes - sol.travel_minutes-sol.charging_minutes)<1e-7
    return PhysicalResult(sol,end.objective,end.penalty_min,B,generated,max_seen,not pruned)


def validate_physical_result(problem: Problem, result: PhysicalResult,
                             *, thermal: ThermalConfig | None = None) -> tuple[bool,tuple[str,...]]:
    """Independent replay of actions using continuous SoC (no label states).

    Validates charging and route node positivity, effective capacity, total
    driving time, charge amount, actual route time, and penalty in minutes.
    """
    B = thermal.usable_capacity(problem.battery) if thermal else problem.battery
    if abs(result.effective_capacity_kwh-B)>1e-7:
        return False, ('Battery capacity mismatch',)
    errors: list[str] = []
    soc, time, charge, penalty = B,0.,0.,0.
    for k, action in enumerate(result.solution.actions):
        u,v = problem.route[k:k+2]
        rate = problem.theta*(problem.veh_mass+sum(n.demand for n in problem.route[k+1:]))
        if thermal:
            rate += thermal.hvac_kw()/(60*problem.speed)
        if action.kind=='direct':
            d=problem.distance(u,v)
            if not isfinite(d):
                errors.append(f'Unavailable direct edge {k}')
                continue
            soc -= d*rate
            time += d/problem.speed
        else:
            j,level=action.station_index,action.charge_level
            if j is None or level is None:
                errors.append(f'Missing station selection at {k}')
                continue
            s=problem.stations[j]
            d1,d2=problem.distance(u,s.node),problem.distance(s.node,v)
            if not isfinite(d1+d2):
                errors.append(f'Unavailable detour edge {k}')
                continue
            arrival=soc-rate*d1
            target=B*level/problem.gamma
            if arrival < -1e-8 or target <= arrival + 1e-9 or target>B+1e-8:
                errors.append(f'Invalid station charge at stage {k}: {arrival}->{target}')
                continue
            curve=derated_curve(s.curve,B) if thermal else s.curve
            time += (d1+d2)/problem.speed+curve.charging_time(arrival,target)
            charge += target-arrival
            if thermal:
                penalty += thermal.charge_penalty_min(arrival,target,B)
            soc=target-d2*rate
        if soc <= 1e-9 or soc>B+1e-8:
            errors.append(f'Invalid node SoC at stage {k}: {soc}')
    if abs(time-result.solution.total_minutes)>1e-7:
        errors.append('Actual route time mismatch')
    if abs(charge-result.solution.total_charge_kwh)>1e-7:
        errors.append('Charge amount mismatch')
    if abs(penalty-result.degradation_penalty_min)>1e-7:
        errors.append('Degradation penalty mismatch')
    if abs(time+penalty-result.objective_equivalent_min)>1e-7:
        errors.append('Total objective mismatch')
    return (not errors),tuple(errors)
