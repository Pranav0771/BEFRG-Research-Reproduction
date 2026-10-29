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
