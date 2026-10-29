"""Phase 3: exact-SoC repair and thermal/degradation sweeps.

Run: python -m experiments.phase3 [--quick] [--output results/phase3]
All data are deterministic synthetic surrogates, not Montoya results.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import time
from dataclasses import replace
from math import isfinite
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import yaml

from befrg import BEFRGSolver, make_problem, synthetic_instance, validate_solution
from befrg.charging import ChargingCurve, STATION_CURVES
from befrg.data import Station
from befrg.physical import solve_physical_grid, validate_physical_result
from befrg.route_init import cheapest_insertion
from befrg.thermal import ThermalConfig
from experiments.milp import continuous_milp

ROOT=Path(__file__).resolve().parents[1]


def write_csv(path:Path, rows:list[dict]) -> None:
    """Write a row-homogeneous CSV with stable field ordering."""
    if not rows:
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    keys=list(rows[0].keys())
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def measured(fn):
    start=time.perf_counter()
    result=fn()
    return result, time.perf_counter()-start


def sample_problem(seed:int,customers:int,stations:int,gamma:int,Gamma:int,theta:float):
    raw=synthetic_instance(seed=seed,customers=customers,stations=stations)
    route=cheapest_insertion(raw)
    return make_problem(raw,route,gamma=gamma,Gamma=Gamma,theta=theta)


def grid_experiment(cfg:dict,output:Path,quick:bool) -> list[dict]:
    rows=[]
    seeds=(cfg['seed'],) if quick else (cfg['seed'],3,5)
    charge_levels=(2,4,8) if quick else tuple(cfg['charging_levels'])
    residual=(4,8,16) if quick else tuple(cfg['residual_levels'])
    for seed in seeds:
        base=sample_problem(seed,cfg['small_customers'],cfg['small_stations'],
                            4,8,cfg['grid_theta'])
        c,secs=measured(lambda:continuous_milp(base,time_limit=cfg['milp_time_limit_sec']))
        for gamma in charge_levels:
            for Gamma in residual:
                p=replace(base,gamma=gamma,Gamma=Gamma)
                try:
                    paper,dp_seconds=measured(lambda:BEFRGSolver(p).bottom_up())
                    paper_check=validate_solution(p,paper)
                    paper_rt=paper.total_minutes
                    physical_ok=paper_check.feasible
                except ValueError:
                    paper_rt=None
                    dp_seconds=None
                    physical_ok=False
                try:
                    fixed,fix_seconds=measured(lambda:solve_physical_grid(p))
                    valid,errors=validate_physical_result(p,fixed)
                    fixed_rt=fixed.solution.total_minutes
                    charged=fixed.solution.total_charge_kwh
                    peak=fixed.max_labels_at_stage
                except ValueError:
                    valid,errors=False,('Infeasible corrected policy',)
                    fixed_rt=fix_seconds=charged=peak=None
                reference = c.objective_min if c.certified_optimal else None
                gap=lambda val: (100*(val-reference)/reference if
                                 val is not None and reference and reference>0 else None)
                rows.append(dict(provenance='ours-scaled-down',seed=seed,gamma=gamma,
                    Gamma=Gamma,continuous_milp_min=reference,
                    milp_status=c.status,milp_certified=c.certified_optimal,
                    milp_wall_s=round(secs,6),original_dp_min=paper_rt,
                    original_dp_wall_s=dp_seconds,original_physically_valid=physical_ok,
                    corrected_min=fixed_rt,corrected_wall_s=fix_seconds,
                    corrected_physically_valid=valid,corrected_charge_kwh=charged,
                    corrected_peak_labels=peak,
                    original_gap_pct=gap(paper_rt),
                    corrected_gap_pct=gap(fixed_rt),errors=';'.join(errors)))
    write_csv(output/'grid_comparison.csv',rows)
    fig,ax=plt.subplots(figsize=(7,4.3))
    for gamma in sorted({r['gamma'] for r in rows}):
        r=[q for q in rows if q['seed']==seeds[0] and q['gamma']==gamma]
        ax.plot([q['Gamma'] for q in r],[q['original_gap_pct'] for q in r],
                marker='o',label=f'Original BEFRG gamma={gamma}')
    ax.set(xlabel='Residual-grid states (Gamma)',ylabel='Gap to certified continuous MILP (%)',
           title='Floor-discretization gap (synthetic instance)')
    ax.legend(fontsize=7);ax.grid(alpha=.25);fig.tight_layout()
    fig.savefig(output/'gap_vs_Gamma.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4.3))
    for gamma in sorted({r['gamma'] for r in rows}):
        rr=[q for q in rows if q['seed']==seeds[0] and q['gamma']==gamma]
        ax.plot([q['Gamma'] for q in rr],
                [q['corrected_wall_s'] for q in rr],marker='o',label=f'gamma={gamma}')
    ax.set(xlabel='Residual-grid states (Gamma)',ylabel='Physical label-solver wall time (s)',
           title='Exact physical states do not depend on Gamma')
    ax.legend(fontsize=8);ax.grid(alpha=.25);fig.tight_layout()
    fig.savefig(output/'physical_runtime_vs_Gamma.png',dpi=180);plt.close(fig)
    return rows


def thermal_problem(cfg:dict):
    return sample_problem(cfg['seed'],cfg['thermal_customers'],cfg['thermal_stations'],
                          8,16,cfg['theta'])


def thermal_config(cfg:dict,temp:float,weight:float=8.) -> ThermalConfig:
    d=cfg['thermal']
    return ThermalConfig(temperature_c=temp,alpha_cold=d['alpha_cold'],
              alpha_hot=d['alpha_hot'],heat_kw_per_c=d['heat_kw_per_c'],
              cool_kw_per_c=d['cool_kw_per_c'],degradation_beta=d['degradation_beta'],
              degradation_weight_min=weight)


def execute_thermal(p, conf:ThermalConfig, tag:str) -> dict:
    try:
        sol,sec=measured(lambda:solve_physical_grid(p,thermal=conf))
        valid,errors=validate_physical_result(p,sol,thermal=conf)
        return dict(provenance='ours-scaled-down',tag=tag,
            temperature_c=conf.temperature_c,
            soh_fraction=conf.health_fraction,
            capacity_kwh=sol.effective_capacity_kwh,
            hvac_kw=conf.hvac_kw(),
            degradation_weight_min=conf.degradation_weight_min,
            route_min=sol.solution.total_minutes,
            degradation_equivalent_min=sol.degradation_penalty_min,
            objective_equivalent_min=sol.objective_equivalent_min,
            charge_kwh=sol.solution.total_charge_kwh,
            detours=sol.solution.detours,
            elapsed_wall_s=sec,max_stage_labels=sol.max_labels_at_stage,
            certified_grid_optimal=sol.certified_grid_optimal,
            physically_valid=valid,error=';'.join(errors))
    except ValueError as exc:
        return dict(provenance='ours-scaled-down',tag=tag,
            temperature_c=conf.temperature_c,
            soh_fraction=conf.health_fraction,
            capacity_kwh=conf.usable_capacity(p.battery),
            hvac_kw=conf.hvac_kw(),degradation_weight_min=conf.degradation_weight_min,
            route_min=None,degradation_equivalent_min=None,
            objective_equivalent_min=None,charge_kwh=None,
            detours=None,elapsed_wall_s=None,max_stage_labels=None,
            certified_grid_optimal=False,physically_valid=False,error=str(exc))


def thermal_experiment(cfg:dict,output:Path,quick:bool) -> list[dict]:
    p=thermal_problem(cfg)
    temps=(0,25,45) if quick else tuple(cfg['thermal']['temperatures_c'])
    scenarios=['full','hvac_only','capacity_only','degradation_only','no_extension']
    rows=[]
    for temp in temps:
        base=thermal_config(cfg,temp,8.)
        for mode in scenarios:
            changes={}
            if mode in ('capacity_only','no_extension'):
                changes.update(heat_kw_per_c=0.,cool_kw_per_c=0.)
            if mode in ('hvac_only','no_extension'):
                changes.update(alpha_cold=0.,alpha_hot=0.)
            if mode!='full' and mode!='degradation_only':
                changes['degradation_weight_min']=0.
            if mode=='degradation_only':
                changes.update(alpha_cold=0.,alpha_hot=0.,heat_kw_per_c=0.,cool_kw_per_c=0.)
            conf=replace(base,**changes)
            rows.append(execute_thermal(p,conf,mode))
    write_csv(output/'thermal_ablations.csv',rows)
    full=[r for r in rows if r['tag']=='full']
    fig,axes=plt.subplots(2,1,figsize=(7.2,6.5),sharex=True)
    axes[0].plot([r['temperature_c'] for r in full],
                 [r['capacity_kwh'] for r in full],marker='o')
    axes[0].set_ylabel('Usable capacity (kWh)');axes[0].grid(alpha=.25)
    axes[1].plot([r['temperature_c'] for r in full],
                 [r['route_min'] for r in full],marker='o',label='Route time')
    axes[1].plot([r['temperature_c'] for r in full],
                 [r['objective_equivalent_min'] for r in full],marker='s',
                 label='Time + degradation penalty')
    axes[1].set(xlabel='Ambient temperature (°C)',ylabel='Minutes equivalent')
    axes[1].legend();axes[1].grid(alpha=.25)
    fig.suptitle('Temperature-aware battery routing (synthetic assumptions)')
    fig.tight_layout();fig.savefig(output/'temperature_effects.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4.3))
    for tag in scenarios:
        rr=[r for r in rows if r['tag']==tag]
        ax.plot([r['temperature_c'] for r in rr],
                [r['route_min'] for r in rr],marker='o',label=tag)
    ax.set(xlabel='Temperature (°C)',ylabel='Physical route time (min)',
           title='Thermal ablation (synthetic assumptions)')
    ax.legend(fontsize=8);ax.grid(alpha=.25);fig.tight_layout()
    fig.savefig(output/'thermal_ablation.png',dpi=180);plt.close(fig)
    return rows


def sensitivity_experiment(cfg:dict,output:Path,quick:bool) -> list[dict]:
    p=thermal_problem(cfg)
    rows=[]
    def add(axis:str,value,problem,thermal):
        record=execute_thermal(problem,thermal,axis)
        rows.append({'axis':axis,'value':value,'gamma':problem.gamma,
                     'Gamma':problem.Gamma,'theta':problem.theta,
                     'station_count':len(problem.stations),
                     'battery_kwh':problem.battery,**record})

    for w in ((0.,8.,20.) if quick else cfg['thermal']['degradation_weights_min']):
        add('degradation_weight_min',w,p,thermal_config(cfg,-10.,w))
    for gamma in (4,8,16):
        add('gamma',gamma,replace(p,gamma=gamma),thermal_config(cfg,0.,8.))
    for Gamma in (8,16,32):
        add('Gamma',Gamma,replace(p,Gamma=Gamma),thermal_config(cfg,0.,8.))
    for theta in (0.00012,0.00018,0.00022):
        add('theta',theta,replace(p,theta=theta),thermal_config(cfg,0.,8.))
    for count in (2,3,4):
        add('station_count',count,replace(p,stations=p.stations[:count]),thermal_config(cfg,0.,8.))
    for battery in (12.,16.,20.):
        factor=battery/p.battery
        stations=tuple(Station(s.node,ChargingCurve(tuple(z*factor for z in s.curve.z),s.curve.x),
                               s.station_type) for s in p.stations)
        add('battery_kwh',battery,replace(p,battery=battery,stations=stations),
            thermal_config(cfg,0.,8.))
    for kind in ('fast','normal','slow'):
        stations=tuple(Station(s.node,STATION_CURVES[kind],kind) for s in p.stations)
        add('station_type',kind,replace(p,stations=stations),thermal_config(cfg,0.,8.))
    write_csv(output/'sensitivity.csv',rows)
    fig,ax=plt.subplots(figsize=(7,4.3))
    rr=[r for r in rows if r['axis']=='degradation_weight_min']
    ax.plot([r['value'] for r in rr],
            [r['route_min'] for r in rr],marker='o',label='Route time')
    ax.plot([r['value'] for r in rr],
            [r['objective_equivalent_min'] for r in rr],marker='s',
            label='Total objective')
    ax.set(xlabel='Penalty weight (equivalent minutes)',ylabel='Minutes',
           title='Degradation surrogate sensitivity at -10 °C')
    ax.legend();ax.grid(alpha=.25);fig.tight_layout()
    fig.savefig(output/'degradation_sensitivity.png',dpi=180);plt.close(fig)
    return rows


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=ROOT/'configs/phase3.yaml')
    parser.add_argument('--output',type=Path,default=ROOT/'results/phase3')
    parser.add_argument('--quick',action='store_true')
    args=parser.parse_args()
    cfg=yaml.safe_load(args.config.read_text(encoding='utf-8'))
    args.output.mkdir(exist_ok=True,parents=True)
    grid=grid_experiment(cfg,args.output,args.quick)
    thermo=thermal_experiment(cfg,args.output,args.quick)
    sens=sensitivity_experiment(cfg,args.output,args.quick)
    meta={'origin':'ours-scaled-down','data':'deterministic synthetic, no Montoya/CRAWDAD',
          'config':str(args.config),'python':platform.python_version(),
          'platform':platform.platform(),'grid_runs':len(grid),
          'thermal_ablations':len(thermo),'sensitivity_runs':len(sens),
          'milp_certified':sum(x['milp_certified'] for x in grid),
          'physically_valid_grid':sum(bool(x['corrected_physically_valid']) for x in grid),
          'physically_valid_thermal':sum(bool(x['physically_valid']) for x in thermo),
          'physically_valid_sensitivity':sum(bool(x['physically_valid']) for x in sens)}
    (args.output/'run_summary.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,indent=2))


if __name__=='__main__':
    main()
