# Original Montoya Extension Validation — source and documentation updates
Each complete file is listed with its original relative repository path. Original Montoya XML data are supplied separately by the user, not redistributed.

## `befrg/physical.py`

`````python
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
`````

## `experiments/montoya_extension_validation.py`

`````python
"""Validate the physically executable Extension 1 on genuine Montoya XML.

The customer tour is INDEPENDENT cheapest-insertion, not the original authors'
Solomon tour. Calibration is fixed to the previous benchmark_montoya pilot.
This script does not make a numerical reproduction claim about Mandal 2025.

Usage:
  python -m experiments.montoya_extension_validation --suite all
  python -m experiments.montoya_extension_validation --suite G
  python -m experiments.montoya_extension_validation --suite small
  python -m experiments.montoya_extension_validation --suite thermal
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import platform
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from befrg import BEFRGSolver, make_problem, read_montoya_xml, validate_solution
from befrg.physical import solve_physical_grid, validate_physical_result
from befrg.route_init import cheapest_insertion
from befrg.thermal import ThermalConfig
from experiments.milp import continuous_milp

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = '[original-XML; independent-tour; our-model]'
CASES = {
    'A': ('tc1c320s38ct2', [(n, 40, 40) for n in (50, 70, 90, 100, 150)]),
    'E': ('tc1c320s38ct2', [(320, g, 40) for g in (2, 4, 8, 16)]),
    'G': ('tc2c320s38cf0', [(n, 16, 16) for n in (40, 80, 120, 160, 200, 240, 280, 320)]),
}


def save_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as handle:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare():
    data = {}
    for name in sorted({case[0] for case in CASES.values()}):
        path = ROOT / 'data/raw/montoya' / f'{name}.xml'
        if not path.is_file():
            raise FileNotFoundError(f'Original input required; copy XML to {path}')
        raw = read_montoya_xml(path)
        customers = cheapest_insertion(raw)
        data[name] = (raw, customers, sha256(path.read_bytes()).hexdigest())
    return data


def run_one(raw, ordered, n, gamma, Gamma, *, test_baseline=True, stations=None):
    problem = make_problem(raw, ordered[:n], gamma=gamma, Gamma=Gamma)
    if stations is not None:
        problem = replace(problem, stations=problem.stations[:stations])
    state = {
        'provenance': PROVENANCE,
        'dataset': raw.name,
        'customers': n,
        'stations': len(problem.stations),
        'gamma': gamma,
        'Gamma': Gamma,
        'route_hash': sha256(','.join(node.id for node in problem.route).encode()).hexdigest()[:16],
        'battery_kwh': problem.battery,
        'veh_mass_kg': problem.veh_mass,
        'theta_kwh_per_kg_km': problem.theta,
        'speed_km_min': problem.speed,
        'original_dp_time_min': None,
        'original_dp_wall_s': None,
        'original_dp_physically_valid': None,
        'original_dp_first_error': '',
    }
    if test_baseline:
        start = time.perf_counter()
        original = BEFRGSolver(problem, mode='DPC').bottom_up()
        original_duration = time.perf_counter() - start
        original_check = validate_solution(problem, original)
        state.update(original_dp_time_min=round(original.total_minutes, 9),
                     original_dp_wall_s=round(original_duration, 6),
                     original_dp_physically_valid=original_check.feasible,
                     original_dp_first_error='; '.join(original_check.errors[:2]))
    try:
        start = time.perf_counter()
        result = solve_physical_grid(problem, dominance_pruning=True)
        runtime = time.perf_counter() - start
        valid, errors = validate_physical_result(problem, result)
        state.update(corrected_time_min=round(result.solution.total_minutes, 9),
                     corrected_wall_s=round(runtime, 6),
                     corrected_physically_valid=valid,
                     corrected_error='; '.join(errors),
                     corrected_certified_finite_grid=result.certified_grid_optimal,
                     corrected_detours=result.solution.detours,
                     corrected_total_charge_kwh=round(result.solution.total_charge_kwh, 7),
                     corrected_final_soc_kwh=round(result.solution.model_visits[-1].soc_kwh, 8),
                     labels_created=result.labels_created,
                     max_stage_labels_before_dominance=result.max_labels_at_stage,
                     improvement_vs_original_pct=round(100 * (state['original_dp_time_min'] - result.solution.total_minutes)
                                                       / state['original_dp_time_min'], 5)
                                                       if state['original_dp_time_min'] else None,
                     computation_error='')
        return state, problem, result
    except (ValueError, RuntimeError) as exc:
        state.update(corrected_time_min=None, corrected_wall_s=None,
                     corrected_physically_valid=False,
                     corrected_error='', corrected_certified_finite_grid=False,
                     corrected_detours=None, corrected_total_charge_kwh=None,
                     corrected_final_soc_kwh=None,labels_created=None,
                     max_stage_labels_before_dominance=None,
                     improvement_vs_original_pct=None, computation_error=f'{type(exc).__name__}: {exc}')
        return state, problem, None


def plot_comparison(rows, out: Path, suite: str):
    xkey = 'gamma' if suite == 'E' else 'customers'
    xs = [int(r[xkey]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.8, 5))
    for key, name, style in [('original_dp_time_min', 'BEFRG floored-state model', 'o-'),
                             ('corrected_time_min', 'Physical-SoC corrected', 's-')]:
        ys = [r[key] if r[key] is not None else float('nan') for r in rows]
        ax.plot(xs, ys, style, linewidth=2, label=name)
    ax.set_xlabel('Charging target levels (gamma)' if suite == 'E' else 'Customer stops')
    ax.set_ylabel('Modeled route time (minutes)')
    ax.set_title(f'Montoya XML {suite}: same independent tour, two state models')
    ax.grid(alpha=.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / f'extension1_{suite.lower()}_route_comparison.png', dpi=180)
    plt.close(fig)


def run_small(raw, tour, out, continuous_limit):
    rows=[]
    for n in (6, 10):
        # Same subset and charge resolution as the earlier certified small MILP pilot.
        row,p,physical=run_one(raw,tour,n,8,12,stations=6)
        start=time.perf_counter()
        benchmark=continuous_milp(p,time_limit=continuous_limit)
        elapsed=time.perf_counter()-start
        row.update(continuous_milp_min=benchmark.objective_min,
                   continuous_milp_certified=benchmark.certified_optimal,
                   continuous_milp_wall_s=round(elapsed,6),
                   gap_to_continuous_pct=(round(100*(physical.solution.total_minutes-benchmark.objective_min)/benchmark.objective_min,5)
                           if physical and benchmark.objective_min and benchmark.certified_optimal else None))
        rows.append(row)
        save_csv(out/'small_milp_crosschecks.csv',rows)
        print('MILP-CHECK',n,'physical',row['corrected_time_min'],'milp',benchmark.objective_min,'cert',benchmark.certified_optimal,flush=True)
    return rows


def run_thermal(raw, tour, out):
    # Sensitivity only: coefficients not fitted to particular Montoya vehicle or cell.
    rows=[]
    for n in (40, 80):
        p=make_problem(raw,tour[:n],gamma=16,Gamma=16)
        choices=[('reference',25.,0.,1.,1.),
                 ('mild_cold',10.,0.,1.,1.),
                 ('cold',0.,0.,1.,1.),
                 ('cold_plus_penalty',0.,8.,1.,1.),
                 ('hot',40.,0.,1.,1.),
                 ('aged',25.,0.,.9,1.),
                 ('cold_half_derating',0.,0.,1.,.5),
                 ('cold_double_derating',0.,0.,1.,2.)]
        for scenario,T,weight,health,coef_mult in choices:
            # HVAC assumptions are deliberately lower than synthetic truck demo;
            # use an illustrative 0.04 kW per Celsius delta.
            t=ThermalConfig(temperature_c=T,health_fraction=health,
                            heat_kw_per_c=.04,cool_kw_per_c=.04,
                            alpha_cold=.00045*coef_mult,
                            degradation_weight_min=weight)
            started=time.perf_counter()
            try:
                sol=solve_physical_grid(p,thermal=t,dominance_pruning=True)
                valid,errors=validate_physical_result(p,sol,thermal=t)
                data={'route_min':round(sol.solution.total_minutes,9),
                      'degradation_equivalent_min':round(sol.degradation_penalty_min,8),
                      'objective_equivalent_min':round(sol.objective_equivalent_min,9),
                      'replay_valid':valid,'grid_certified':sol.certified_grid_optimal,
                      'detours':sol.solution.detours,'error':'; '.join(errors)}
            except ValueError as exc:
                data={'route_min':None,'degradation_equivalent_min':None,
                      'objective_equivalent_min':None,'replay_valid':False,
                      'grid_certified':False,'detours':None,'error':str(exc)}
            row=dict(provenance=PROVENANCE,customer_count=n,scenario=scenario,
                     ambient_c=T,health_fraction=health,capacity_kwh=round(t.usable_capacity(p.battery),5),
                     hvac_kw=round(t.hvac_kw(),5),coefficient_multiplier=coef_mult,
                     penalty_weight_equiv_min=weight,wall_s=round(time.perf_counter()-started,6),**data)
            rows.append(row)
            save_csv(out/'thermal_robustness_original_xml.csv',rows)
            print('THERMAL',n,scenario,'RT',row['route_min'],'valid',row['replay_valid'],flush=True)
    return rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--suite',choices=['all','A','E','G','small','thermal'],default='all')
    ap.add_argument('--output',type=Path,default=ROOT/'results/montoya_extension1')
    ap.add_argument('--milp-time-limit',type=float,default=30.)
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    dat=prepare()
    meta={'input_source':'original Montoya et al. (2017) VRP-REP XML files, user-provided',
          'data_sha256':{k:item[2] for k,item in dat.items()},
          'route_construction':'independent deterministic cheapest insertion on all 320; then use prefixes',
          'paper_route_matched':False,'paper_calibration_matched':False,
          'distance':'original XML coordinates with Euclidean distance (metric)',
          'gamma':'set separately per experiment; discrete station targets only',
          'Gamma':'residual levels of original BEFRG; physical solver does not round SoC',
          'energy_calibration':'veh_mass=1000kg, theta=source_nominal_kwhkm/1000; synthetic unit customer loads',
          'exactness':'only finite-target model, Euclidean dominance, no beam pruning, 11-decimal SoC key',
          'physical_validation':'independent route/charge replay, strict SoC>0 at customer nodes',
          'provenance':PROVENANCE,'python':platform.python_version(),'platform':platform.platform(),
          'runtime_note':'local wall times exclude tour construction; vary across hardware',
          'thermal_note':'illustrative coefficients, not measured Montoya battery behavior'}
    (args.output/'methodology.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    for suite in 'AEG':
        if args.suite not in ('all',suite): continue
        name,params=CASES[suite]
        raw,tour,_=dat[name]
        rows=[]
        for n,g,G in params:
            row,_,result=run_one(raw,tour,n,g,G)
            row['suite']=suite
            rows.append(row)
            save_csv(args.output/f'extension1_{suite.lower()}_original_xml.csv',rows)
            print('EXPERIMENT',suite,n,g,'baseline',row['original_dp_time_min'],'corrected',row['corrected_time_min'],
                  'valid',row['corrected_physically_valid'],'s',row['corrected_wall_s'],flush=True)
        plot_comparison(rows,args.output,suite)
    raw,tour,_=dat['tc2c320s38cf0']
    if args.suite in ('all','small'):
        run_small(raw,tour,args.output,args.milp_time_limit)
    if args.suite in ('all','thermal'):
        run_thermal(raw,tour,args.output)

if __name__=='__main__':main()
`````

## `tests/test_montoya_extension.py`

`````python
"""Tests for correctness of dominance pruning and genuine-XML optional regression."""
from dataclasses import replace
from pathlib import Path

import pytest

from befrg import make_problem, read_montoya_xml, synthetic_instance
from befrg.physical import solve_physical_grid, validate_physical_result
from befrg.route_init import cheapest_insertion
from befrg.thermal import ThermalConfig


def test_euclidean_dominance_pruning_preserves_finite_grid_optimum():
    raw = synthetic_instance(seed=42,customers=8,stations=3)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16)
    unpruned=solve_physical_grid(p)
    dominated=solve_physical_grid(p,dominance_pruning=True)
    assert unpruned.certified_grid_optimal and dominated.certified_grid_optimal
    assert dominated.solution.total_minutes == pytest.approx(unpruned.solution.total_minutes)
    assert validate_physical_result(p,dominated)[0]


def test_dominance_with_temperature_and_degradation():
    raw=synthetic_instance(seed=44,customers=7,stations=3)
    p=make_problem(raw,cheapest_insertion(raw),gamma=6,Gamma=12)
    therm=ThermalConfig(temperature_c=10,heat_kw_per_c=.04,degradation_weight_min=7.)
    a=solve_physical_grid(p,thermal=therm)
    b=solve_physical_grid(p,thermal=therm,dominance_pruning=True)
    assert a.objective_equivalent_min==pytest.approx(b.objective_equivalent_min)
    assert validate_physical_result(p,b,thermal=therm)[0]


def test_dominance_refuses_sparse_or_directed_distance_overrides():
    raw=synthetic_instance(seed=42,customers=5,stations=2)
    p=make_problem(raw,cheapest_insertion(raw),gamma=6,Gamma=12)
    with pytest.raises(ValueError,match='Euclidean'):
        solve_physical_grid(replace(p,euclidean_fallback=False),dominance_pruning=True)
    with pytest.raises(ValueError,match='Euclidean'):
        solve_physical_grid(replace(p,distances={(p.route[0].id,p.route[1].id):10.}),dominance_pruning=True)


def test_dominance_full_charge_same_result_as_unpruned():
    raw=synthetic_instance(seed=47,customers=8,stations=3)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16)
    original=solve_physical_grid(p,mode='FC')
    pruned=solve_physical_grid(p,mode='FC',dominance_pruning=True)
    assert original.solution.total_minutes==pytest.approx(pruned.solution.total_minutes)
    assert validate_physical_result(p,pruned)[0]


def test_actual_montoya_regression_if_xml_available():
    path=Path(__file__).resolve().parents[1]/'data/raw/montoya/tc2c320s38cf0.xml'
    if not path.exists(): pytest.skip('Original Montoya XML is not shipped in code release')
    raw=read_montoya_xml(path)
    tour=cheapest_insertion(raw)
    p=make_problem(raw,tour[:40],gamma=16,Gamma=16)
    result=solve_physical_grid(p,dominance_pruning=True)
    assert result.certified_grid_optimal
    assert validate_physical_result(p,result)[0]
    assert result.solution.total_minutes==pytest.approx(471.826053970,rel=1e-7)
`````

## `tests/test_montoya_saved_results.py`

`````python
"""Archive consistency checks for the original-XML extension report (no XML needed)."""
from pathlib import Path
import csv

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results/montoya_extension1'


def read(name):
    with (RESULTS/name).open(newline='',encoding='utf8') as handle:
        return list(csv.DictReader(handle))


def test_montoya_extension_results_independent_physical_replay():
    groups=[read('extension1_a_original_xml.csv'),
            read('extension1_e_original_xml.csv'),
            read('extension1_g_original_xml.csv')]
    assert list(map(len,groups))==[5,4,8]
    rows=[r for group in groups for r in group]
    assert sum(r['original_dp_physically_valid']=='True' for r in rows)==2
    assert sum(r['corrected_physically_valid']=='True' for r in rows)==17
    assert all(r['corrected_certified_finite_grid']=='True' for r in rows)
    assert all(float(r['corrected_time_min'])<float(r['original_dp_time_min']) for r in rows)
    assert all('original-XML' in r['provenance'] for r in rows)


def test_original_xml_baseline_against_saved_pilot():
    rows=read('old_baseline_regression_checks.csv')
    assert len(rows)==17
    assert all(r['matched']=='True' for r in rows)


def test_saved_cross_machine_objectives():
    rows=read('cross_machine_objectives.csv')
    assert len(rows)==36
    assert all(r['match_at_1e_6']=='True' for r in rows)


def test_thermal_original_xml_is_labeled_uncalibrated():
    rows=read('thermal_robustness_original_xml.csv')
    assert len(rows)==16
    assert all(r['replay_valid']=='True' and r['grid_certified']=='True' for r in rows)
    assert all('independent-tour' in r['provenance'] for r in rows)


def test_dominance_ablation_exact_objective_equal():
    rows=read('dominance_ablation.csv')
    assert len(rows)==6
    for n in ('10','20','40'):
        subset=[r for r in rows if r['customers']==n]
        assert len(subset)==2
        assert subset[0]['objective_min']==subset[1]['objective_min']
        assert all(r['grid_certified']=='True' and r['feasible']=='True' for r in subset)
`````

## `scripts/verify_results.py`

`````python
"""Audit the presence and provenance of committed Phase 2–4 result files.

Does NOT claim that the numbers were regenerated on the current hardware.
Run: python -m scripts.verify_results
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'phase2': 'results/tables/phase2_paper_ours_overview.csv',
    'phase3': 'results/phase3/grid_comparison.csv',
    'phase4': 'results/phase4/use_cases.csv',
    'phase4_inputs': 'results/phase4/scenario_inputs.json',
    'original_montoya_extension': 'results/montoya_extension1/extension1_g_original_xml.csv',
}


def _verify_manifest() -> None:
    """Verify archived CSV, JSON and PNG bytes against the committed manifest."""
    manifest = ROOT / 'results/MANIFEST.sha256'
    if not manifest.is_file():
        raise SystemExit('Missing results/MANIFEST.sha256')
    checked = 0
    for line in manifest.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split('  ', 1)
        except ValueError as exc:
            raise SystemExit(f'Invalid manifest line: {line}') from exc
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f'Missing result from manifest: {relative}')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Checksum mismatch for {relative}. Regeneration may change outputs.')
        checked += 1
    print(f'OK committed-result checksums: {checked} files')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-hashes', action='store_true',
                        help='verify exact archive contents against results/MANIFEST.sha256')
    args = parser.parse_args()
    for label, relative in EXPECTED.items():
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f'Missing/empty result artifact: {relative}')
        print(f'OK {label}: {relative}')
    for relative in (
        'results/phase3/grid_comparison.csv',
        'results/phase4/use_cases.csv',
    ):
        with (ROOT / relative).open(newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise SystemExit(f'No result records: {relative}')
        if any(row.get('provenance', '').strip('[]') != 'ours-scaled-down' for row in rows):
            raise SystemExit(f'Mislabeled provenance in {relative}')
        print(f'OK provenance: {relative} ({len(rows)} rows)')
    # Saved original-XML results have a separate provenance label from the
    # Phase 2–4 synthetic surrogates. The external XML source is not bundled.
    with (ROOT / 'results/montoya_extension1/extension1_g_original_xml.csv').open(
            newline='', encoding='utf-8') as src:
        recorded = list(csv.DictReader(src))
    if len(recorded) != 8 or any('original-XML' not in r['provenance'] for r in recorded):
        raise SystemExit('Invalid original-XML Extension 1 result provenance')
    data_path = ROOT / 'data/raw/montoya'
    for archive in data_path.glob('**/*'):
        if archive.is_file() and archive.name != '.gitkeep':
            print(f'INFO: user-provided source benchmark present: {archive.name}')
    if args.check_hashes:
        _verify_manifest()
    print('This is an artifact-integrity audit, not a full numerical reproduction test.')


if __name__ == '__main__':
    main()
`````

## `docs/model_assumption_strengthening.md`

`````markdown
# Extension 2: physical assumption strengthening without claiming field calibration

This is an **engineering assumption audit** supported by new genuine-Montoya-geometric sensitivity tests, not by measured battery telemetry. We retain exactly two research extensions.

| Component | In model | Evidence / next real calibration needed |
|---|---|---|
| Temperature derating | Asymmetric bounded quadratic `B_use/B0` vs constant ambient T | Battery chemistry and vehicle-specific discharge capacity tests across T and SoC |
| HVAC | Drive-only power `min(6kW, k_heat*(19-T)_+ + k_cool*(T-27)_+)` | Actual HVAC duty cycle, cabin loads, vehicle heating type, passenger occupancy |
| Charge speed | Original Montoya charging times rescaled at fixed normalized SoC as capacity changes | 2D/3D charge-power-vs-SoC-vs-battery-temperature map; manufacturer charge acceptance and thermal throttling |
| Health | Fixed exogenous SOH multiplier | Time-varying measured SOH and temperatures, validated across cycling history |
| Degradation | Equivalent-minute cost `omega*(Δcharge/B_use)^beta` | Cycling-depth/cycle-history model, observed capacity fade, monetary aging cost and calendar aging |

**Sensitivity setup:** Original Montoya `tc2c320s38cf0.xml` geometry, independent fixed route prefixes n=40/80; ambient T ∈ {0,10,25,40} °C with separate aging and cold-derating sweeps. For this stress test only, cabin coefficients are `heat_kw_per_c = cool_kw_per_c = 0.04`; battery capacity coefficients are `alpha_cold = 0.00045`, `alpha_hot = 0.00012`, SOH default 1, optional .9; cold coefficient multiplied by .5 or 2. Degradation penalty weight 0 or 8 equivalent minutes, beta 1.4. **None of these are fitted from the XML or a measured cell.** Results are in `results/montoya_extension1/thermal_robustness_original_xml.csv` (16/16 independently replay-valid).

**Scientific grounding, not calibration:** U.S. DOE, September 23, 2024, *Impact of Cold Ambient Temperature and Extreme Conditions on Electric Vehicles*, https://www.energy.gov/cmei/vehicles/articles/program-record-impact-cold-ambient-temperature-and-extreme-conditions . Its findings substantiate the relevance of cold cell performance and HVAC to driving energy/range, **not** our numerical coefficients nor a universal capacity-loss function. Real charging power is temperature dependent, unlike the project model. The fixed-temperature, equal-C-rate synthetic assumption is a major potential source of model error.

## Interpretation

These tests answer a limited *conditional* question: given an invented temperature-to-capacity map and ancillary power demand, how would the optimizer's policy change on a known road-network geometry? They do not answer how much a real EV battery degrades per trip, whether Montoya's vehicle would accept the modeled charger at low temperature, or whether the same policy would hold under weather/traffic uncertainty.
`````

## `results/montoya_extension1/EXTENSION1_ORIGINAL_MONTOYA_REPORT.md`

`````markdown
# BEFRG Extension 1 — original Montoya XML verification

> **Result type:** `[original-XML; independent-tour; our-model]`. This is a genuine Montoya benchmark input study, **not** a reproduction of Mandal et al.'s exact customer routes or calibrated vehicle parameters. No original Montoya XML is redistributed in this archive. The data here use the same independent cheapest-insertion tours and assumed 1,000 kg vehicle / nominal-rate-derived θ as the previous user's original-XML pilot.

## Executive result

The old floored-BEFRG run passes independent physical replay for **2/17** policies across the 5 Experiment A, 4 Experiment E, and 8 Experiment G configurations. Replacing floor-projected route-node battery states with physically continuous SoC labels while retaining finite charge-target actions yields **17/17 feasible policies**, all independently validated and certified finite-target-grid optimal under the stated Euclidean dominance theorem and numerical label resolution. The corrected objective is lower in all 17 comparisons, but **the original modeled times of invalid policies are not executable trip times**; therefore those percentage changes are mathematical model-objective comparisons, not field time savings.

Small independent continuous-charge MILPs agree with the corrected planner on the 6- and 10-customer configurations. An optimized dominance rule is also validated against the unpruned label algorithm for 10, 20 and 40-customer cases at γ=16 and all 38 stations. Thermal robustness runs on the original Montoya geometry use *uncalibrated illustrative* parameters and are not OEM battery validation.

## Experiment G — 40–320 original Montoya customers, γ=Γ=16

| Customers | Floored BEFRG model (min) | Corrected physical-SoC (min) | Modeled reduction | Old physically valid? | Corrected physically valid? |
|---:|---:|---:|---:|:---:|:---:|
| 40 | 579.41 | 471.83 | 18.57% | Yes | Yes |
| 80 | 1,159.60 | 950.15 | 18.06% | No | Yes |
| 120 | 1,703.27 | 1,389.33 | 18.43% | No | Yes |
| 160 | 2,367.12 | 1,938.73 | 18.10% | No | Yes |
| 200 | 2,797.07 | 2,312.75 | 17.32% | No | Yes |
| 240 | 3,390.12 | 2,817.66 | 16.89% | No | Yes |
| 280 | 3,988.54 | 3,248.84 | 18.55% | No | Yes |
| 320 | 4,636.69 | 3,719.68 | 19.78% | No | Yes |

At 320 customers, the corrected finite-target grid's route time is approximately **3,719.68 minutes**, against the floored model's **4,636.69 minutes**. The 19.78% difference is **relative to the old model's route-time output**, and cannot be interpreted as a physically realized fleet time saving when the old policy is infeasible. The new solver's run took roughly 2.48 seconds in this execution; do not generalize this runtime to all instances or all hardware.

## Experiment A — 50–150 customers, γ=Γ=40

| Customers | Floored DP (min) | Corrected (min) | Old valid? | Corrected valid? |
|---:|---:|---:|:---:|:---:|
| 50 | 529.90 | 497.21 | True | True |
| 70 | 701.47 | 638.31 | False | True |
| 90 | 1,043.92 | 961.24 | False | True |
| 100 | 1,134.56 | 1,046.63 | False | True |
| 150 | 1,711.84 | 1,549.93 | False | True |

## Experiment E — 320 customers, Γ=40 and varying γ

| Charging levels γ | Floored DP (min) | Corrected (min) | Old valid? | Corrected valid? |
|---:|---:|---:|:---:|:---:|
| 2 | 3,915.02 | 3,464.23 | False | True |
| 4 | 3,776.03 | 3,382.45 | False | True |
| 8 | 3,673.34 | 3,313.45 | False | True |
| 16 | 3,636.66 | 3,302.37 | False | True |

## Independent continuous MILP checks — original XML subcases

| Customers | Corrected finite-target (min) | Continuous-charge MILP (min) | MILP optimality certified? | Physical replay passed? |
|---:|---:|---:|:---:|:---:|
| 6 | 90.99 | 90.99 | True | True |
| 10 | 145.55 | 145.55 | True | True |

The 6/10 customer checks use **six selected stations** on the **tc2c320s38cf0** data, not the `tc1c320s38ct2` six-station cross-check used by the previous pilot. Thus their numerical values are **new**, and should not be confused with the original pilot's small 84.44/167.80 min checks.

## Euclidean SoC dominance: exactness and performance

At a given fixed-route node, a state A with more SoC and no higher accumulated objective than state B dominates B when (i) all direct edges exist and satisfy the triangle inequality, (ii) remaining energy demand is nonnegative and independent of battery history, (iii) charging costs are nonnegative, nondecreasing in charged energy, and time-independent, and (iv) the objective is additive. To reproduce any feasible low-SoC future action from the higher-SoC state: charge to the same target using no more charging time, or, when higher arrival SoC is already above that target, skip the station and use the no-longer-than-detour direct Euclidean arc. Therefore eliminating B cannot lose a better finite-target solution. The implementation *rejects* this option for arbitrary/sparse/directed distance overrides; it is **not** a universal dominance property of real directed road graphs. SoC keys are numerically rounded to 11 decimal places, consistent with the original Phase 3 solver's precision limits.

| Customers | Unpruned (sec) | Dominance (sec) | Same objective? | Corrected physically valid? |
|---:|---:|---:|:---:|:---:|
| 10 | 2.96 | 0.04 | Yes | True |
| 20 | 11.69 | 0.17 | Yes | True |
| 40 | 28.83 | 0.51 | Yes | True |

These are local wall times from one run, not stable hardware-independent speedup estimates. The dominance method is **an internal acceleration of Extension 1**, not a new third research extension. Any optional beam search is disabled; all reported corrected policies are grid-optimal within the model assumptions.

## Extension 2 — robustness on *original benchmark geometry*, NOT calibrated cells

At the same 40-customer original-XML tour, route time changes from 471.83 min at 25°C to 587.12 min at 0°C under the chosen quadratic usable-capacity derating and a hypothetical HVAC rate 0.04 kW/°C. At 80 customers it changes from 950.15 to 1,154.07 min. Doubling the *assumed* cold coefficient increases the 40-customer result to 878.31 min, underscoring that the response depends strongly on uncalibrated parameters. A charging-throughput equivalent-minute penalty was included in a separate cold scenario; it is **not measured electrochemical aging**, and it must not be added to driving time as if it were physical charging duration.

The U.S. DOE/Argonne 2024 impact report supports the qualitative relevance of ambient temperature, cell performance and HVAC load; it does **not** calibrate this model for the Montoya vehicle, determine `alpha_cold`, or validate its battery chemistry: https://www.energy.gov/cmei/vehicles/articles/program-record-impact-cold-ambient-temperature-and-extreme-conditions . For measured deployment, obtain vehicle-specific temperature-vs-usable-capacity tests, charger-power-vs-SoC-vs-temperature maps, HVAC duty cycles, charging availability and original-route road grades.

## Cross-machine numerical reproducibility (original floored baseline)

The user's local Ubuntu run matches the earlier environment on **36/36** stored objective metrics within 1e-6 minute, across Experiments A, E, F, G and small MILP checks. This is separate from the new Extension 1 validation, which was executed in the current environment only. Repeating the new runner on the user's laptop is recommended before claiming cross-machine validation of the corrected implementation. `cross_machine_objectives.csv` and `old_baseline_regression_checks.csv` contain the complete reconciliation.

## Configuration, limitations and reproducibility

- **Inputs:** Actual Montoya VRP-REP XML, checksums in `methodology.json`. Source archive must be downloaded separately, not redistributed with this code.
- **Tour:** One independently constructed deterministic cheapest-insertion tour for the full 320 customers, using prefixes for smaller runs; the authors' exact tour is unknown.
- **Calibration:** Customer deliveries assumed 1 kg each; 1,000 kg empty mass; θ chosen so empty consumption equals the original XML nominal kWh/km. This was the original pilot's assumption, not a recovered paper value.
- **Charging:** Original nonlinear station profiles from XML; finite target grid γ; at most one station per original route arc; all 38 stations unless explicitly reported as 6 in the small continuous MILP checks.
- **Guarantees:** Physical-SoC solver is optimal within the finite-target, Euclidean-metric action model (up to 11-decimal SoC merge tolerance) **without beam pruning**; continuous charging optimum is only provided by separately certified MILP on 6/10 customer cases.
- **Feasibility:** Independent continuous replay validates positivity at fixed-route nodes, monotone station charging, charger limits, and objective accounting. It does not model queue waiting, traffic, hills, charging losses or a safety energy reserve.
- **Comparability:** Paper's numerical Table 2/6/7 values **cannot** be directly attributed to algorithmic differences because their routes/vehicle calibration are not matched. The new results demonstrate reproduced benchmark-input behavior, not exact numerical reproduction of Mandal et al.'s results.
- **Timing:** Local wall time depends on CPU, Python and dependency versions; route construction is excluded. Absent original SUMO data and authors' CPLEX environment, no fair paper-to-ours speed claim exists.

### Re-run

```bash
python -m pip install -e '.[test]'
# Place your externally downloaded XMLs in data/raw/montoya/
python -m pytest -q
python -m experiments.montoya_extension_validation --suite all --output results/my_extension_validation
python -m experiments.montoya_extension_validation --suite G --output results/my_extension_validation
```

The first command may take longer for γ=40 cases or small MILP solves; a single run avoids overwriting saved results by choosing its own output directory. The report is deterministic in objective values but not necessarily runtime measurements.

### Traceability

- Source code: `befrg/physical.py` (`dominance_pruning=True`), `experiments/montoya_extension_validation.py` and `tests/test_montoya_extension.py`.
- Saved evidence: `results/montoya_extension1/extension1_{a,e,g}_original_xml.csv`, `small_milp_crosschecks.csv`, `thermal_robustness_original_xml.csv`, `dominance_ablation.csv`, `cross_machine_objectives.csv`.
- Existing baseline and local-run evaluation: `results/montoya_pilot/`, `cross_machine_objectives.csv`.
- Exact model derivation: `docs/phase3_math_review.md` plus additional Euclidean dominance argument above.
`````

## `README.md`

`````markdown
# BEFRG: Independent Reproduction and Extensions

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Tests](https://img.shields.io/badge/local%20tests-63%20passed-brightgreen) ![Status](https://img.shields.io/badge/benchmark-original%20XML%20%2B%20synthetic-orange)

**Independent implementation of** Mandal, Sarkar & Mondal (2025), *A Discrete Partial Charging Enabled Dynamic Programming Strategy for Optimal Fixed-Route Electric Vehicle Charging*, ACM TECS 24(5s), Article 154. DOI: https://doi.org/10.1145/3762188.

> **Reproduction status:** Saved evidence includes `[ours-scaled-down]` synthetic experiments and `[original-XML; independent-tour]` Montoya-input experiments, alongside separate `[paper]` references. Exact numerical reproduction of the original 120-instance published tables and original SUMO/CRAWDAD simulation was **not achieved**. Matching trends on synthetic data must not be called a full reproduction. Full explanations: [Reproducibility](docs/reproducibility.md), [Review](docs/paper_review.md), [Assumptions](docs/assumptions.md).

## Abstract

The fixed-route EV charging problem asks where to insert charging detours and what battery charge target to use while preserving an already chosen customer sequence. This repository independently implements BEFRG's finite-state dynamic programming algorithm and compares its modeled outcomes against exhaustive enumeration and discrete/continuous mixed-integer programming. It documents the limits of residual-charge flooring and implements two user-selected research extensions: (1) continuous physical SoC tracking with discrete charge targets and independent route validation, and (2) bounded temperature-dependent battery capacity, HVAC consumption, and a synthetic charging-throughput degradation penalty. Four further synthetic use cases study Indian last-mile delivery, regional coaches, heavy freight, and charger outage/density. All numbers are from executed Python experiments; original-XML experiments use independent customer tours and synthetic vehicle calibration, not calibrated vehicle field measurements.

## Results at a glance

| Claim / experiment | [paper] reference | [ours-scaled-down] executed evidence | Reproduction status |
|---|---|---|---|
| A: BEFRG vs MILP | Reported 8–15% gap at Γ=40 on selected Montoya prefixes | Synthetic 17/17 discrete MILP matches; original-XML prefix runs and certified small-instance MILP checks | Original XML used but paper tour unmatched |
| B: memoization | Exponential no-memo growth | Recursion hit defined 100,000-call cap in small synthetic cases | Partial trend |
| C: route size | Table 4b RT 137–531 min | 102.63–187.97 min on other synthetic routes | Partial trend, not comparable magnitude |
| D: station count | Table 5a RT 5761→4692 min | 303.82→265.18 min on other synthetic routes | Partial trend |
| E: charge level γ | Table 6a RT 84.17→77.75 h | 267.56→248.36 min on different model | Partial trend |
| F: scalability | 5–19 sec for 320–1600 nodes, 47 sec for 120 instances | 0.207→5.853 sec for 20–320 synthetic customers | Partial scale test |
| G: FC vs DPC | Table 7a at 320 nodes: 5132 vs 4602 min | Lower modeled DPC cost; some baseline actions failed physical replay | Partial with validation caveat |
| H: traffic | EFRGen on SF and Amsterdam | Hourly-speed substitute only, not SUMO | Could not reproduce original experiment |

The above is a **cross-dataset summary**, not a numerical gap analysis. For per-experiment CSVs and explicit N/A numeric differences, see [`results/tables/phase2_paper_ours_overview.csv`](results/tables/phase2_paper_ours_overview.csv). Configuration, run provenance and plots are committed under [`results/`](results/).

## Installation / quickstart

Python 3.10+ (CPU only) and pip are required; no IBM CPLEX is needed. HiGHS is available via SciPy. On Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
python -m pytest -q
python -m scripts.run_example
python -m scripts.phase3_demo
python -m scripts.verify_results --check-hashes
```

On Windows, activate with `.venv\Scripts\activate` and use `python` commands. To run the Jupyter notebooks: `python -m pip install -e '.[notebook]'` and `jupyter lab`.

## One-command reproduction recipes

**By default, Phase 2 uses deterministic synthetic surrogates.** `--quick` reduces workload; Phase 4 `--quick` uses a heuristic beam and cannot certify grid optimality.

| Target | Command | Outputs |
|---|---|---|
| Tests | `python -m pytest -q` | Local pass/fail |
| Paper Fig. 2 running example | `python -m scripts.run_example` | Policy and SoC trace |
| A / Fig. 4: grid–MILP | `python -m experiments.exp_a` | `results/tables/exp_a.csv`, `results/figures/exp_a_gap.png` |
| B / Table 4a: memoization | `python -m experiments.exp_b` | `results/tables/exp_b.csv`, `results/figures/exp_b_memoization.png` |
| C / Table 4b: route size | `python -m experiments.exp_c` | `results/tables/exp_c.csv`, `results/figures/exp_c_route_time.png` |
| D / Table 5a: stations | `python -m experiments.exp_d` | `results/tables/exp_d.csv`, `results/figures/exp_d_stations.png` |
| E / Table 6a: γ | `python -m experiments.exp_e` | `results/tables/exp_e.csv`, `results/figures/exp_e_charge_levels.png` |
| F / Table 6b: scale | `python -m experiments.exp_f` | `results/tables/exp_f.csv`, `results/figures/exp_f_scaling.png` |
| G / Table 7a: FC vs DPC | `python -m experiments.exp_g` | `results/tables/exp_g.csv`, `results/figures/exp_g_fc_dpc.png` |
| H / Tables 5b,7b **substitute** | `python -m experiments.exp_h` | `results/tables/exp_h_substitute.csv`, `results/figures/exp_h_traffic.png` |
| All Phase 2 synthetic | `python -m experiments.run_all` | `results/tables/`, `results/figures/` |
| Rebuild Phase 2 summary | `python -m experiments.summarize && python -m experiments.overview` | Verdicts and comparison overview |
| Extension 1 + 2 | `python -m experiments.phase3` | `results/phase3/*.csv`, `*.png` |
| New use cases | `python -m experiments.phase4` | `results/phase4/*.csv`, `*.json`, `*.png` |
| Montoya Extension 1 audit | `python -m experiments.montoya_extension_validation --suite all` | `results/montoya_extension1/` (external XML needed) |
| Fast verification smoke | `bash run_all.sh smoke` | Tests, running example and committed-result checksums |
| Regenerate quick experiment subsets | `bash run_all.sh quick` | Separate outputs under `results/recomputed_quick` etc.; may still be time-consuming |
| Rebuild all synthetic experiments | `bash run_all.sh full-synthetic` | Overwrites the corresponding checked-in results (runtime varies) |

Run any experiment with `--help` for additional flags. To avoid touching the committed outputs, supply `--output results/your_run`. `make help` lists Makefile targets, e.g. `make exp-a` and `make phase4`.

## Original dataset download (manual)

- **Montoya nonlinear EVRP benchmark:** https://www.vrp-rep.org/datasets/item/2016-0020.html — extract VRP-REP XML files into `data/raw/montoya/`. To use original XML, run `python -m experiments.exp_a --full` or `python -m experiments.exp_f --full`. `--full` requires the source files and does **not** silently substitute synthetic input. The original Solomon-like initial tour and paper's calibration remain not fully known, so even a successful `--full` run is not automatically a reproduced paper value.
- **San Francisco CRAWDAD traces:** https://doi.org/10.15783/C7J010 — save in `data/raw/crawdad/`. Historical traffic replay requires a separately configured SUMO/OSM environment; the included `simulators/traci_controller.py` is only a skeleton.
- **OpenStreetMap:** https://www.openstreetmap.org/ — place local network extracts under `data/raw/osm/` for custom simulation.

No downloaded benchmark/traces are distributed in the repository, although executed original-XML summary CSVs are included. See [`data/README.md`](data/README.md).

## Algorithm and research contribution map

| Original paper's contribution | Independent work in this repository |
|---|---|
| FRVCP-DPC formulation and BEFRG recurrence | Python top-down and bottom-up implementations with deterministic tie-breaking, policy trace and independent physical replay |
| Full-charge vs discrete partial charging | Independent FC/DPC comparison and station/target policy validation |
| Nonlinear charging curves | Exact piecewise-linear charge-time calculations with unit tests |
| Reported MILP baseline | New independent discretized-flow MILP and continuous-charge MILP in `experiments/milp.py` |
| Snapshot traffic discussion | Static vs hourly-speed substitute (`exp_h`); **not** a true time-expanded planner |
| No grid error correction | Physical-SoC label DP with charge-level grid, validator and objective/runtime sensitivity |
| No thermal degradation objective | Bounded capacity derating, driving HVAC consumption and uncalibrated per-charge throughput cost |
| Montoya/SF/Amsterdam evaluations | Four additional **synthetic**, non-georeferenced practical stories |

## Original Montoya XML: physically executable extension (new evidence)

**See [`results/montoya_extension1/EXTENSION1_ORIGINAL_MONTOYA_REPORT.md`](results/montoya_extension1/EXTENSION1_ORIGINAL_MONTOYA_REPORT.md).** Three existing original-XML experiment groups (A/E/G) were rerun on the same independent cheapest-insertion customer tours before and after Extension 1, using no beam pruning. The floored BEFRG policy passed continuous physical replay in **2/17** configurations, versus **17/17** for Extension 1. At 320 customers and γ=Γ=16, original modeled route time was 4,636.69 min (physically invalid policy) and corrected time was 3,719.68 min (physically valid). This is a *modeled objective difference*, not a realized driving-time improvement. Small 6/10 customer continuous MILP solves certified equality with the corrected finite-target optimum. The original XML input and paper numerical benchmark tour/energy calibration are **not** the same thing.

An opt-in exact Euclidean-SoC dominance filter safely reduces the label search for those metric instances. It is rejected on sparse or directed distances because the needed triangle inequality is not guaranteed. The solver's only finite-target optimum claim assumes no beam pruning and is subject to the 11-decimal key tolerance. The small ablation showed the same objective and physical validity with/without dominance on 10/20/40 customer original-XML subsets. Sixteen additional *uncalibrated* thermal/SOH robustness checks on the same original-XML geometry also passed physical replay. No third extension was added.

```bash
# After installing external XML under data/raw/montoya/, as described below:
python -m experiments.montoya_extension_validation --suite all --output results/my_montoya_extension1
# Quickest main corrected-vs-floored demonstration (8 configs):
python -m experiments.montoya_extension_validation --suite G --output results/my_montoya_extension1
```

## Selected synthetic extension results — [ours-scaled-down]

The unpruned physical-SoC model produced physically executable finite-grid policies across the recorded Phase 3 sweeps. Mean floored-DP gap versus the continuous MILP decreased from 118.89% to 27.29% as Γ rose from 4 to 32 on deliberately stressed synthetic cases. With the corrected method, the mean gap decreased from 21.67% (γ=2) to 3.08% (γ=16). These percentages are *not* Montoya benchmark gaps; see `results/phase3/grid_comparison.csv` for individual rows.

In the four Phase 4 stories, modeled route times compared as: last-mile AC only 357.96 min vs hypothetical AC/DC 244.89 min; coach with all stations 612.20 vs one closed 634.81 min; empty truck 780.15 vs loaded 815.06 min; sparse one-station network 336.28 vs five-station network 207.67 min. All are synthetic and have no measured real-vehicle basis. See `results/phase4/comparisons.csv` and exact source inputs.

## Repository layout

```text
befrg/                    BEFRG core, charging, parsing, validators, physical and thermal extensions
befrg/baselines/          tiny brute force and no-memo recursion
experiments/              A–H, MILPs, comparisons, Phase 3/4 runners
configs/                  fixed-seed YAML configuration files
tests/                    pytest unit, property-like and regression checks
scripts/                  demos and result-provenance audit
simulators/               optional TraCI controller skeleton
data/raw/                 gitignored manual benchmark/traces/OSM inputs
notebooks/                example walkthrough and conditional real Montoya demo
results/                  CSV/JSON/PNG from executed synthetic experiments
docs/                     critical review, assumptions, design and reproducibility verdict
.github/workflows/        test and committed-output checks on push/pull request
```

## Limitations

**Optimality is always relative to a specified model.** The original BEFRG optimizes a finite residual battery grid, which can exclude physically feasible routes. The physical label DP eliminates per-node floor loss but optimizes only a finite charging-target grid and uses floating-point merges; with beam pruning its result is heuristic. The model assumes a fixed customer order and at most one charger per original arc. Thermal capacity and degradation penalties are synthetic surrogates, not calibrated electrochemistry. Original-source files, precise energy calibration and a production traffic simulation are unavailable in the bundled project. Execution time comparisons across hardware are not meaningful without environment controls. For a full list see [`docs/assumptions.md`](docs/assumptions.md). For GitHub publishing and verification steps, see [`docs/github_submission.md`](docs/github_submission.md).

## Citation, license and academic integrity

Cite both the original paper and this implementation: `CITATION.cff` contains machine-readable software attribution; the paper DOI is https://doi.org/10.1145/3762188. MIT license applies to original source code in this repository; it does **not** relicense or grant redistribution rights to third-party datasets or papers. The repository contains no copied authors' implementation; source algorithmic ideas are attributed. Before public release, check the software credit information in `CITATION.cff`, the research-data licenses, and any modified source provenance.

## Original Montoya XML reproduction pilot (October 2026)

The research group has now executed a separate **[original-XML; independent-tour]** pilot using all 120 available source XMLs as a verified corpus and two 320-customer instances for experiments **A, E, G, F**. See **[`results/montoya_pilot/REPRODUCTION_REPORT.md`](results/montoya_pilot/REPRODUCTION_REPORT.md)** for full results, physical validation failures, figures and input hashes. It includes paper numbers alongside results as contextual comparisons, **not exact matched reproductions**. The original benchmark files are excluded from Git and must be downloaded separately into `data/raw/montoya/`.

To reproduce the new pilot:

```bash
python -m experiments.benchmark_montoya --suite A
python -m experiments.benchmark_montoya --suite E
python -m experiments.benchmark_montoya --suite G
python -m experiments.benchmark_montoya --suite F
python -m experiments.benchmark_montoya --suite milp-small
```

**Limit:** The paper's Solomon-inspired tour and exact mass/θ are still not fully specified. Matched 50–150-node paper Table 2 MILP values, full 120-instance BEFRG timings, and 640–1600-node scaling were **not** replicated. Our floored-state DPC policies can also be invalid under physical charge replay; the CSVs preserve each failure.

**Canonical Extension 1 implementation:** `befrg/physical.py`. The older `befrg/extensions/exact_soc.py` is a secondary experimental prototype, and no published figure or result in this repository is derived from it. Do not confuse its separate routine with the canonical Phase 3/4 and Montoya Extension 1 implementation.
`````

## `docs/assumptions.md`

`````markdown
# Consolidated assumptions register (A01–A55)

These assumptions are explicit research-reproduction decisions, not necessarily statements about the authors’ implementation. See the corresponding phase reports for context.

- **A01** — All fixed-route nodes, including return depot, must have strictly positive discrete SoC. The paper's literal unguarded zero state can be explored with `strict_positive=False`.
- **A02** — B divided by gamma and Gamma creates the two grids; widths are not rounded and battery capacity is exactly represented.
- **A03** — Curve segments require increasing charge and time breakpoints; station curve capacity equals B.
- **A04** — The DP's model SoC is floored after each original route arc. Actual SoC must be replayed independently, and may lead to different charging times or invalid no-op charge targets.
- **A05** — Benchmark vehicle mass and theta are omitted in the paper. Default `veh_mass=1000 kg` and `theta=0.125/1000` kWh/(km·kg) match empty-vehicle rate 0.125 kWh/km, NOT the paper's unknown calibration.
- **A06** — `cheapest_insertion` is Solomon-*inspired*, NOT a reproduction of unspecified SIH logic. No time windows or service times in BEFRG objective.
- **A07** — Montoya uses Euclidean distances in kilometres, retaining double precision.
- **A08** — Station type curves are read from source XML; no station-type reallocation.
- **A09** — At most one station detour per original route arc; no station-to-station travel.
- **A10** — Zero SoC at a charging station is permitted; positive SoC required at original route nodes.
- **A11** — Ties prefer direct action, then station input order, then smaller target.
- **A12** — Figure 2(b) does not specify distances between all node-station pairs. Running example only allows six specified directed arcs. Hence its optimum is for a *sparse interpretation* and cannot establish the optimal policy for an unstated complete graph.
- **A13** — Traffic dependence and predictive online planning are not implemented in Phase 1.
- **A14** — All benchmark customer demands default to one kg (paper's assigned unit loads).
- **A15** — Timing, memory and benchmark comparisons are future Phase 2 tasks; none are claimed here.
- **A16** — Depot occurs at both beginning and end of route, and both positions count as route nodes.
- **A17** — Every Phase 2 synthetic experiment uses fixed seed 20251028 and a deliberate empty-vehicle energy stress multiplier of 2.0.
- **A18** — Synthetic customer subsets are prefixes of the deterministic initial tour.
- **A19** — Station-set sweeps use nested first-N synthetic stations, not the sampled subsets of the paper.
- **A20** — SciPy/HiGHS substitutes for IBM CPLEX; report optimizer termination/certificate status.
- **A21** — Synthetic online traffic uses hourly (60-minute) slots, Normal(70%,10%) flow and a heuristic speed-congestion function; it is not validated SUMO dynamics.
- **A22** — Runtime instrumentation uses tracemalloc/psutil and can slow execution; no hardware-matched performance claim is made.
- **A23** — Paper-versus-ours quantitative differences are undefined when the route, benchmark or energy calibration differs.
- **A24** — A discretized-optimal policy may require a physically non-increasing charge target; independent continuous validation is mandatory.
- **A25** — Constant ambient temperature and constant SOH throughout a route.
- **A26** — Temperature capacity derating is bounded, asymmetric and synthetic; no cell calibration.
- **A27** — HVAC power is piecewise-linear in ambient temperature, not cabin control dynamics.
- **A28** — HVAC consumes battery energy during driving, with no separate charging HVAC drain.
- **A29** — Speed remains the paper's fixed speed, and temperature modifies auxiliary load, not traction efficiency or regeneration.
- **A30** — Charger follows equal normalized-SoC elapsed-time curve at reduced capacity; no cold-charge restriction or throttling.
- **A31** — Degradation term is a *per-charge throughput surrogate*, not an experimentally fitted electrochemical aging law.
- **A32** — Degradation weight is a time-equivalent objective coefficient, not electrical energy or physical duration.
- **A33** — Exact-SoC label search is globally optimal **only** over its discrete-target action space with no beam limit.
- **A34** — Equal SoC labels are merged with numerical tolerance; this is not a mathematically exact real-number implementation.
- **A35** — All Phase 3 coefficient values and all experimental geographic geometries are labeled synthetic; no exact Montoya reproduction is claimed.
- **A36** — Every scenario has synthetic Euclidean coordinates in km, never real OSM roads or station positions.
- **A37** — Fixed customer/service order and repeated depot; no optimization of customer assignment or depot placement.
- **A38** — Charging hardware is compatible with the vehicle by assumption. Especially the three-wheeler's DC charger is hypothetical and must not be treated as OEM-compatible.
- **A39** — Charging power is piecewise constant by segment with 80%, 95%, 100% breakpoints; charging losses and charger occupancy/queuing are absent.
- **A40** — Temperature is constant throughout a run; capacity derating and HVAC curves are synthetic and uncalibrated.
- **A41** — Battery health is fixed for each route; the degradation penalty is a mathematical surrogate in time-equivalent units, not cumulative SOH prediction.
- **A42** — Coach passenger loads, idle energy, driver rest, depot service, road gradients, regenerative braking, weather-dependent traction and time windows are not modeled.
- **A43** — Freight payload fits the truck by assumption. The paper's mass-linear energy model is used without calibrated resistance terms.
- **A44** — Adding stations is modeled as expanding the existing set with all other inputs fixed; outages remove one station deterministically.
- **A45** — In the exact-SoC solver, the finite charge-target optimum is certified only when no beam pruning occurs. Positivity is tested at original route nodes; zero arrival SoC at a station is allowed.
- **A46** — Very low but positive depot SoC is allowed; no safety reserve or probabilistic robustness is guaranteed.
- **A47** — The study has one deterministic geometry per scenario. These results do not support population statistics, confidence intervals or transport-system generalization.

## New validated original-XML assumptions (A48–A55)

- **A48:** Original Montoya XML inputs are genuine, but initial routes are deterministic independently generated cheapest-insertion prefixes, not the paper's unrecovered route plans.
- **A49:** Vehicle mass is assumed 1,000 kg and θ matches the XML nominal empty-vehicle kWh/km; unit customer loads are assumed, with no claim of author parameter parity.
- **A50:** The optional Euclidean dominance rule requires complete metric distances obeying triangle inequality; it is deliberately rejected for arbitrary directed/sparse graphs.
- **A51:** SoC dominates another SoC label only when its accumulated objective is no higher; each station target must remain strictly above actual arrival SoC.
- **A52:** The new 17-config physical-SoC validation compares the same independent route and charging grid; the old DP's invalid modeled route time is not a physically executable trip time.
- **A53:** Thermal parameters on original XML geometry are hypothetical, and capacity, charge power and degradation are not fitted to a specific vehicle cell chemistry.
- **A54:** All reported finite-target optimum certificates rely on no beam pruning and the existing numeric 11-decimal SoC key; on nonmetric input no dominance certificate is claimed.
- **A55:** User laptop cross-machine validation covers 36 earlier floored model objectives, not the new physical-SoC extension until rerun locally.
`````

## `docs/phase3_math_review.md`

`````markdown
# Phase 3 — New mathematical extensions and corrections

All equations below are project extensions; they are **not** equations from Mandal et al. (2025). Energy/route units: kWh, minutes, kilometres, kilograms; temperature in °C. Experimental coefficients are **assumptions**. References at end.

## Idea #1 — physically executable SoC decisions

Original BEFRG stores a rounded-down state `b * rc` and computes station charging from that rounded value. When physical arrival SoC is higher than target, the chosen action is non-executable. Residual energy lost at each grid projection can also cause needless detours.

We replace the rounded route-node state with an exact physical SoC label `s` and keep **only** the station target charge level discrete: `y'_c = ell * B/gamma`. All arcs remain fixed-route and permit at most one station detour. Transitions from each `(k,s)` are:

- Direct: `s' = s - e(v_k,v_{k+1}) > 0`, `increment = d(v_k,v_{k+1})/S`.
- Detour: `a = s - e(v_k,c) >= 0`, choose `ell` with `a < ell*B/gamma <= B`; `s' = ell*B/gamma - e(c,v_{k+1}) > 0`; `increment = (d(v_k,c)+d(c,v_{k+1}))/S + CT(a, ell*B/gamma)`.

The shortest-path label recurrence is

`D_{k+1}(s') = min_{(s, action)->s'} [D_k(s)+increment(s,action)]`.

Only *equal* physical SoC states are merged (numerical key rounded to 11 decimal places, tolerances at most ~1e-9 kWh). The baseline physical label solver makes no nontrivial SoC dominance claim by default. The **optional October 2026 Montoya-validation update** adds dominance pruning **only** for complete Euclidean metrics with nonnegative, monotone charging cost: if a label has more SoC and no greater objective at the same route node, it dominates a lower-SoC label. The triangle inequality guarantees a direct leg never costs more energy/time than a detour when the higher-SoC label would already exceed the lower label’s target charge. This optimization is rejected on sparse/directed distance overrides. On this restricted class, it preserves finite-grid optimality without heuristic beam pruning (up to the existing 11-decimal numeric key). Without optional beam pruning, this is optimal **for the finite set of charge targets and physically executable actions**, but may be slower and use more labels than BEFRG. With `max_labels_per_stage` set, it becomes an explicitly **heuristic** beam search, and `certified_grid_optimal=False`.

The continuous MILP benchmark permits any continuous charge target, so it is a lower bound on this discrete-target solution. A feasible result from our solver may be strictly worse. The per-instance gap is `(T_physical_grid - T_MILP)/T_MILP`, only when the MILP is certified optimal.

## Idea #2 — temperature-aware capacity, HVAC and degradation cost

**User-proposed expression:** `B(T)=B0*(1-alpha*(T_ref-T)^2)`. Dimensionally meaningful with `alpha` measured in degC^-2 but insufficiently realistic: it is symmetric and can be negative; it conflates usable capacity with irreversible aging.

**Project model (constant ambient T for one route):**

`B_use(T,h) = B0 * h * max(f_min, 1 - alpha_c * max(T_ref-T,0)^2 - alpha_h * max(T-T_ref,0)^2)`.

`h` is exogenous state-of-health (0,1], not an evolving state. `f_min` prevents negative capacity. Distinct cold/hot coefficients are an illustrative curve, **not empirical calibration**. Cold performance and HVAC demand are known to impact range; a manufacturer temperature-capacity lookup would be preferable to the quadratic.

**Cabin HVAC (piecewise, kW):**

`P_HVAC(T) = min(P_max, k_heat*max(T_heat-T,0) + k_cool*max(T-T_cool,0))`.

**Per-leg energy (kWh), with S in km/min:**

`e_T(u,w;k) = theta*(L(v_{k+1})+veh_mass)*d(u,w) + P_HVAC(T)*d(u,w)/(60*S)`.

The two legs of a station detour use the **same destination load** as the paper. HVAC energy is counted while traveling only; charger supplies any ancillary power during charging (assumption). The variable `B_use` is a **usable energy capacity**, and the charging target grid is `ell*B_use/gamma`.

**Charge-time curve:** Scale each curve breakpoint from nominal charge `z` to `z*B_use/B0` at unchanged elapsed time `x`. This assumes equal C-rate at equal normalized SoC; it omits temperature-triggered charge-power derating and would need battery-specific calibration.

**Degradation proxy:** The user-proposed `C_deg(ΔDoD)=omega*(ΔDoD)^beta` needs an explicit `ΔDoD` definition. Charging **increment fraction** `q=(y'-y)/B_use` is not the same as a cycle depth from a full SoC cycle. We implement

`C_deg(y,y',T) = omega_min * q^beta` where `q >= 0` and `omega_min >= 0`.

`omega_min` has units equivalent minutes; `beta >= 1`. The objective is

`min T_travel + T_charge + sum C_deg`.

The sum belongs in the **action cost** of the exact-SoC label DP, and we report route minutes and penalty separately. Neither electrochemical kinetics, calendar aging, true capacity fade along the tour, SOC-induced calendar degradation, charge C-rate, rainflow DoD cycle depth nor actual battery-life cost is modeled. `beta>1` can perversely favor splitting the same charging energy across multiple events; this objective must be described as a **throughput-related surrogate** pending chemistry-specific fitting, not physical lifetime prediction.

### DP state sufficiency

With fixed temperature `T`, exogenous SOH `h`, deterministic station curves, time-independent traffic and **additive per-charge surrogate costs**, `(route index k, physical SoC s)` remains sufficient: no cycle-history state is needed for this specific proxy. A legitimate electrochemical rainflow cycling cost generally depends on past SoC extrema and would require an expanded state or offline trajectory cost; one cannot silently substitute it into the current Bellman recurrence.

### Added assumptions A25–A35

- **A25:** Constant ambient temperature and constant SOH throughout a route.
- **A26:** Temperature capacity derating is bounded, asymmetric and synthetic; no cell calibration.
- **A27:** HVAC power is piecewise-linear in ambient temperature, not cabin control dynamics.
- **A28:** HVAC consumes battery energy during driving, with no separate charging HVAC drain.
- **A29:** Speed remains the paper's fixed speed, and temperature modifies auxiliary load, not traction efficiency or regeneration.
- **A30:** Charger follows equal normalized-SoC elapsed-time curve at reduced capacity; no cold-charge restriction or throttling.
- **A31:** Degradation term is a *per-charge throughput surrogate*, not an experimentally fitted electrochemical aging law.
- **A32:** Degradation weight is a time-equivalent objective coefficient, not electrical energy or physical duration.
- **A33:** Exact-SoC label search is globally optimal **only** over its discrete-target action space with no beam limit.
- **A34:** Equal SoC labels are merged with numerical tolerance; this is not a mathematically exact real-number implementation.
- **A35:** All Phase 3 coefficient values and all experimental geographic geometries are labeled synthetic; no exact Montoya reproduction is claimed.

### Scientific background (not calibration of our coefficients)

- Mandal et al., *ACM TECS* (2025), https://doi.org/10.1145/3762188 — baseline BEFRG problem, not temperature model.
- U.S. DOE/Argonne National Laboratory, *Impact of Cold Ambient Temperatures and Extreme Conditions on Electric Vehicles*, 2024, https://www.energy.gov/sites/default/files/2024-10/Impact_of_Cold_Ambient_Temperature_on_BEV_Performance_v15_TechEditFinal_12Sep2024__0.pdf .
- NREL System Advisor Model battery temperature/capacity inputs, https://samrepo.nlr.gov/help/battery_storage_fom.html .
- Loew et al., *Economic model predictive control of Li-ion battery cyclic aging via online rainflow-analysis* (2021), https://onlinelibrary.wiley.com/doi/10.1002/est2.228 .
- *A Comprehensive Review on the Characteristics and Modelling of Lithium-ion Battery Ageing*, https://pure.tudelft.nl/ws/portalfiles/portal/115259835/A_Comprehensive_Review_on_the_Characteristics_and_Modelling_of_Lithium_ion_Battery_Ageing.pdf .
`````

