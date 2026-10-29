"""Phase 4: four entirely synthetic, documented EV charging use cases.

Run ``python -m experiments.phase4 [--quick] [--output results/phase4]``.
This does NOT use Montoya instances or OSM networks. Every result is labeled
ours-scaled-down; the exact-SoC solver is certified only when unpruned.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import platform
import time
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import yaml

from befrg.charging import ChargingCurve
from befrg.data import Node, Problem, Station
from befrg.physical import PhysicalResult, solve_physical_grid, validate_physical_result
from befrg.thermal import ThermalConfig
from befrg.energy import energy_rate

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = 'ours-scaled-down'


@dataclass(frozen=True)
class Case:
    """One route shared across deterministic environment/policy variations."""
    key: str
    name: str
    story: str
    problem: Problem
    curves_description: str
    seed: int


def power_curve(battery_kwh: float, powers_kw: tuple[float, float, float]) -> ChargingCurve:
    """3-segment illustrative CC/CV curve; NOT a measured cell charging trace.

    Rates are mean input-to-battery powers; per-segment charging time is
    delta_energy / rate. Segments span 0–80%, 80–95%, 95–100% SoC.
    """
    if battery_kwh <= 0 or any(p <= 0 for p in powers_kw):
        raise ValueError('Capacity and charging powers must be positive')
    z = (0., battery_kwh * .80, battery_kwh * .95, battery_kwh)
    x = [0.]
    for before, after, kw in zip(z, z[1:], powers_kw):
        x.append(x[-1] + 60. * (after-before) / kw)
    return ChargingCurve(z, tuple(x))


def make_case(key: str, name: str, story: str,
              coords: tuple[tuple[float, float], ...],
              demands_kg: tuple[float, ...],
              station_specs: tuple[tuple[str, float, float, tuple[float, float, float]], ...],
              *, battery_kwh: float, speed_km_min: float, veh_mass_kg: float,
              empty_kwh_km: float, gamma: int, Gamma: int,
              seed: int = 20261028) -> Case:
    """Build a closed planar synthetic route, direct distances in km.

    All station positions, customer coordinates, consumption rates, charger
    powers and masses are intentionally synthetic and must not be presented as
    GIS/OSM-measured or calibrated vehicle measurements.
    """
    if len(coords) != len(demands_kg):
        raise ValueError('Demand length mismatch')
    depot = Node(f'{key}_depot', 0., 0., kind='depot')
    customers = tuple(Node(f'{key}_v{i+1}', x, y, demand=load)
                      for i, ((x, y), load) in enumerate(zip(coords, demands_kg)))
    stations = tuple(
        Station(Node(f'{key}_{label}', x, y, kind='station'),
                power_curve(battery_kwh, powers), label)
        for label, x, y, powers in station_specs
    )
    problem = Problem(
        (depot, *customers, depot), stations, battery_kwh, speed_km_min,
        empty_kwh_km / veh_mass_kg, veh_mass_kg, gamma, Gamma,
    )
    return Case(key, name, story, problem,
                'Synthetic 3-segment charger curves (80%, 95%, 100% SoC)', seed)


def build_cases(cfg: dict[str, Any]) -> dict[str, Case]:
    """Four practical stories, all with deterministic artificial coordinates."""
    seed = int(cfg['seed'])
    return {
        'last_mile': make_case(
            'last_mile', 'Indian urban electric cargo three-wheeler',
            'Long multi-drop city loop; compare AC-only and hypothetical DC-capable operation.',
            ((18., 1.), (35., 6.), (38., 21.), (25., 32.), (8., 28.), (-1., 12.)),
            (30., 30., 35., 35., 30., 25.),
            (('ac_3kw', 17., 2., (3.3, 2.4, 1.5)),
             ('dc_25kw', 36., 19., (25., 15., 7.5)),
             ('ac_3kw_b', 8., 27., (3.3, 2.4, 1.5))),
            battery_kwh=10.24, speed_km_min=0.5, veh_mass_kg=520.,
            empty_kwh_km=.11, gamma=5, Gamma=20, seed=seed),
        'coach': make_case(
            'coach', 'Regional battery-electric coach',
            'Closed intercity loop with a few high-power roadside chargers; the stop sequence is fixed.',
            ((70., 5.), (104., 70.), (40., 115.), (-40., 95.), (-80., 25.), (-50., -45.)),
            (0.,)*6,
            (('dc_150a', 102., 68., (150., 100., 50.)),
             ('dc_90', 39., 110., (90., 70., 35.)),
             ('dc_150b', -78., 25., (150., 100., 50.))),
            battery_kwh=220., speed_km_min=1.1, veh_mass_kg=12000.,
            empty_kwh_km=.92, gamma=5, Gamma=20, seed=seed),
        'truck': make_case(
            'truck', 'Heavy-duty electric freight truck',
            'A large outbound payload is delivered progressively; charging choices are made en route.',
            ((90., 0.), (165., 60.), (125., 145.), (35., 165.), (-55., 100.), (-85., 10.)),
            (1200., 1400., 900., 700., 1100., 800.),
            (('dc_250a', 160., 60., (250., 160., 85.)),
             ('dc_180', 37., 163., (180., 120., 65.)),
             ('dc_250b', -54., 102., (250., 160., 85.)),
             ('dc_120', -84., 11., (120., 75., 40.))),
            battery_kwh=420., speed_km_min=0.95, veh_mass_kg=16000.,
            empty_kwh_km=1.04, gamma=5, Gamma=20, seed=seed),
        'outage': make_case(
            'outage', 'Peri-urban station-density and outage network',
            'Same fixed urban-peripheral delivery loop, nested station sets, and a one-station outage.',
            ((18., 6.), (30., 18.), (22., 34.), (2., 36.), (-14., 22.), (-16., 6.)),
            (80., 80., 80., 80., 80., 80.),
            (('ac_slow', 30., 17., (12., 8., 4.)),
             ('dc_fast', -13., 23., (70., 45., 25.)),
             ('ac_near', 2., 35., (22., 12., 6.)),
             ('dc_mid', 20., 33., (60., 35., 18.)),
             ('ac_spare', 5., 7., (18., 10., 5.))),
            battery_kwh=16., speed_km_min=.65, veh_mass_kg=1100.,
            empty_kwh_km=.155, gamma=6, Gamma=24, seed=seed),
    }


def thermal_at(temperature_c: float, *, weight_min: float = 0.,
               health_fraction: float = 1., hvac_kw_per_c: float | None = None) -> ThermalConfig:
    """Fixed ambient temperature; degradation cost in time-equivalent minutes."""
    kw_cold = .16 if hvac_kw_per_c is None else hvac_kw_per_c
    kw_hot = .12 if hvac_kw_per_c is None else hvac_kw_per_c
    return ThermalConfig(temperature_c=temperature_c,
                         health_fraction=health_fraction,
                         heat_kw_per_c=kw_cold, cool_kw_per_c=kw_hot,
                         degradation_weight_min=weight_min)


def scenarios(cases: dict[str, Case], cfg: dict[str, Any]) -> list[tuple[str, str, Problem, ThermalConfig]]:
    """Build paired interventions without changing the underlying tour."""
    last = cases['last_mile'].problem
    bus = cases['coach'].problem
    truck = cases['truck'].problem
    station = cases['outage'].problem
    temperate = thermal_at(25.)
    return [
        ('last_mile', 'mixed_ac_dc', last, temperate),
        ('last_mile', 'ac_only', replace(last, stations=tuple(s for s in last.stations if 'ac_' in s.station_type)), temperate),
        ('last_mile', 'cold_mixed', last, thermal_at(0., weight_min=8., hvac_kw_per_c=.016)),
        ('coach', 'all_roadside', bus, temperate),
        ('coach', 'one_fast_closed', replace(bus, stations=bus.stations[1:]), temperate),
        ('coach', 'hot_weather', bus, thermal_at(40.,weight_min=6.)),
        ('truck', 'loaded', truck, temperate),
        ('truck', 'empty_payload_control', replace(truck, route=tuple(replace(n, demand=0.) for n in truck.route)), temperate),
        ('truck', 'cold_loaded', truck, thermal_at(0., weight_min=15., hvac_kw_per_c=.06)),
        ('outage', 'sparse_one', replace(station, stations=station.stations[:1]), temperate),
        ('outage', 'medium_two', replace(station, stations=station.stations[:2]), temperate),
        ('outage', 'dense_five', station, temperate),
        ('outage', 'dc_mid_outage', replace(station, stations=tuple(s for s in station.stations if s.station_type != 'dc_mid')), temperate),
    ]


def route_km(p: Problem) -> float:
    """Distance of original fixed route without detours."""
    return sum(p.distance(u,v) for u,v in zip(p.route,p.route[1:]))


def run_one(case: Case, variant: str, p: Problem, thermal: ThermalConfig,
            *, beam: int | None, mode: str = 'DPC') -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute one policy and independently replay physical energy."""
    start = time.perf_counter()
    trace: dict[str, Any] = {'scenario':case.key,'variant':variant,'visits':[],'actions':[]}
    common = dict(provenance=PROVENANCE,scenario=case.key,variant=variant,seed=case.seed,
                  customers=len(p.route)-2,station_count=len(p.stations),
                  battery_nominal_kwh=p.battery, temperature_c=thermal.temperature_c,
                  soh=thermal.health_fraction, battery_usable_kwh=thermal.usable_capacity(p.battery),
                  hvac_kw=thermal.hvac_kw(),initial_route_km=route_km(p),
                  gamma=p.gamma,Gamma=p.Gamma, mode=mode,
                  direct_route_energy_kwh=round(sum(
                      (energy_rate(p,k+1)+thermal.hvac_kw()/(60*p.speed))*p.distance(u,v)
                      for k,(u,v) in enumerate(zip(p.route,p.route[1:]))),6))
    try:
        answer=solve_physical_grid(p,mode=mode,thermal=thermal,max_labels_per_stage=beam)
        elapsed=time.perf_counter()-start
        valid,errors=validate_physical_result(p,answer,thermal=thermal)
        sol=answer.solution
        trace['visits']=[asdict(v) for v in sol.model_visits]
        trace['actions']=[asdict(v) for v in sol.actions]
        metrics=dict(**common,status='feasible' if valid else 'validator_failed',
                     wall_s=round(elapsed,6),route_time_min=round(sol.total_minutes,6),
                     travel_time_min=round(sol.travel_minutes,6),
                     charging_time_min=round(sol.charging_minutes,6),
                     charge_kwh=round(sol.total_charge_kwh,6),
                     detours=sol.detours,final_soc_kwh=round(sol.model_visits[-1].soc_kwh,6),
                     degradation_equivalent_min=round(answer.degradation_penalty_min,6),
                     optimized_objective_min=round(answer.objective_equivalent_min,6),
                     physically_valid=valid,
                     certified_grid_optimal=answer.certified_grid_optimal,
                     labels_created=answer.labels_created,
                     max_labels_per_stage=answer.max_labels_at_stage,
                     error='; '.join(errors))
    except ValueError as e:
        metrics=dict(**common,status='infeasible',wall_s=round(time.perf_counter()-start,6),
                     route_time_min=None,travel_time_min=None,charging_time_min=None,
                     charge_kwh=None,detours=None,final_soc_kwh=None,
                     degradation_equivalent_min=None,optimized_objective_min=None,
                     physically_valid=False,certified_grid_optimal=False,
                     labels_created=None,max_labels_per_stage=None,error=str(e))
    return metrics,trace


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0].keys()))
        writer.writeheader();writer.writerows(rows)


def make_plots(rows: list[dict[str, Any]],output:Path,cases: dict[str, Case]) -> None:
    """All charts derive solely from the executed CSV rows."""
    for case in ('last_mile','coach','truck','outage'):
        group=[r for r in rows if r['scenario']==case]
        labels=[r['variant'].replace('_','\n') for r in group]
        vals=[r['route_time_min'] if r['route_time_min'] is not None else 0 for r in group]
        fig,ax=plt.subplots(figsize=(max(7.,1.4*len(group)+2.),4.5))
        bars=ax.bar(range(len(group)),vals)
        ax.set_xticks(range(len(group)),labels)
        ax.set_ylabel('Physical route time (minutes)')
        ax.set_title(f'{case.replace("_"," ").title()} — synthetic scenario comparison')
        ax.grid(axis='y',alpha=.25)
        ax.set_axisbelow(True)
        for bar,row in zip(bars,group):
            if row['route_time_min'] is None:
                ax.text(bar.get_x()+bar.get_width()/2,0,'INFEASIBLE',ha='center',va='bottom',fontsize=8,rotation=90)
            else:
                ax.text(bar.get_x()+bar.get_width()/2,bar.get_height(),f'{bar.get_height():.1f}',
                        ha='center',va='bottom',fontsize=9)
        ymax=max(vals or [1.])
        ax.set_ylim(0,max(1.,ymax)*1.2)
        fig.tight_layout();fig.savefig(output/f'{case}_comparison.png',dpi=180);plt.close(fig)
    # Geometry diagrams: synthetic Euclidean locations, not GPS coordinates.
    for key,case in cases.items():
        p=case.problem
        fig,ax=plt.subplots(figsize=(7,5.5))
        xs=[n.x for n in p.route]
        ys=[n.y for n in p.route]
        ax.plot(xs,ys,marker='o',label='Fixed customer order')
        ax.scatter([p.route[0].x],[p.route[0].y],marker='s',s=105,label='Depot')
        ax.scatter([s.node.x for s in p.stations],
                   [s.node.y for s in p.stations],marker='^',s=65,label='Candidate chargers')
        for i,n in enumerate(p.route[1:-1],start=1):
            ax.annotate(str(i),(n.x,n.y),xytext=(5,5),textcoords='offset points',fontsize=9)
        for st in p.stations:
            ax.annotate(st.station_type,(st.node.x,st.node.y),xytext=(5,-12),
                        textcoords='offset points',fontsize=7)
        ax.set(xlabel='Synthetic x-coordinate (km)',ylabel='Synthetic y-coordinate (km)',
               title=f'{key.replace("_"," ").title()} — schematic route, NOT OSM')
        ax.axis('equal');ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.tight_layout();fig.savefig(output/f'{key}_geometry.png',dpi=170);plt.close(fig)
    groups=sorted({r['scenario'] for r in rows})
    fig,ax=plt.subplots(figsize=(8.8,5.))
    for case in groups:
        subset=[r for r in rows if r['scenario']==case and r['route_time_min'] is not None]
        ax.scatter([r['charge_kwh'] for r in subset], [r['route_time_min'] for r in subset],label=case,s=65)
    ax.set(xlabel='Energy added at charging stations (kWh)',ylabel='Physical route time (min)',
           title='Cross-scenario charging outcomes (not directly comparable vehicles)')
    ax.grid(alpha=.25);ax.legend();fig.tight_layout()
    fig.savefig(output/'overview.png',dpi=180);plt.close(fig)


def run_all(output: Path, config: Path, quick: bool = False) -> list[dict[str, Any]]:
    """Run all four scenarios; --quick uses a documented heuristic beam limit."""
    cfg=yaml.safe_load(config.read_text(encoding='utf-8'))
    output.mkdir(parents=True,exist_ok=True)
    cases=build_cases(cfg)
    beam=cfg['quick_beam_limit'] if quick else cfg.get('full_beam_limit')
    rows=[]
    traces=[]
    for key, variant, p, thermal in scenarios(cases,cfg):
        row, trace=run_one(cases[key],variant,p,thermal,beam=beam)
        rows.append(row)
        traces.append(trace)
        print(f"{key:11s} | {variant:23s} | {str(row['route_time_min']):>12s} min | {row['status']:16s} | {row['wall_s']:.3f} s",flush=True)
    write_csv(output/'use_cases.csv',rows)
    by_name={(r['scenario'],r['variant']):r for r in rows}
    pairs=[
        ('last_mile','ac_only','mixed_ac_dc','AC only versus mixed chargers'),
        ('last_mile','mixed_ac_dc','cold_mixed','Cold-weather operation'),
        ('coach','all_roadside','one_fast_closed','Roadside charger closure'),
        ('coach','all_roadside','hot_weather','Hot-weather operation'),
        ('truck','empty_payload_control','loaded','Freight payload effect'),
        ('truck','loaded','cold_loaded','Cold-weather laden freight'),
        ('outage','sparse_one','dense_five','Station-density improvement'),
        ('outage','dense_five','dc_mid_outage','High-power charger outage'),
    ]
    comparisons=[]
    for key,baseline,counterfactual,question in pairs:
        b=by_name[(key,baseline)]['route_time_min']
        a=by_name[(key,counterfactual)]['route_time_min']
        comparisons.append(dict(provenance=PROVENANCE,scenario=key,
            comparison=question,baseline=baseline,alternative=counterfactual,
            baseline_min=b,alternative_min=a,
            change_min=round(a-b,6) if a is not None and b is not None else None,
            change_pct=round(100*(a-b)/b,4) if a is not None and b else None))
    write_csv(output/'comparisons.csv',comparisons)
    (output/'policies.json').write_text(json.dumps(traces,indent=2)+'\n',encoding='utf-8')
    metadata={'source':'synthetic coordinates, synthetic energy and charging curves; no OSM',
              'provenance':PROVENANCE,'fixed_seed':cfg['seed'],
              'quick':quick,'beam_limit':beam,
              'platform':platform.platform(),'python':platform.python_version(),
              'stories':{key:asdict(case)|{'problem':None} for key,case in cases.items()},
              'parameters':cfg}
    (output/'run_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    # Policy baseline FC vs DPC on the exact same synthetic route and environment.
    policy_rows=[]
    for key, case in cases.items():
        for mode in ('FC','DPC'):
            record, _ = run_one(case,mode.lower()+'_policy',case.problem,thermal_at(25.),
                                beam=beam,mode=mode)
            policy_rows.append(record)
    write_csv(output/'fc_vs_dpc.csv',policy_rows)

    # Input serialization for independently auditing every synthetic coordinate.
    inputs={}
    for key,case in cases.items():
        p=case.problem
        inputs[key]={
            'story':case.story,'seed':case.seed,'battery_kwh':p.battery,
            'speed_km_min':p.speed,'vehicle_mass_kg':p.veh_mass,
            'theta_kwh_per_kg_km':p.theta,'gamma':p.gamma,'Gamma':p.Gamma,
            'route':[asdict(n) for n in p.route],
            'charging_stations':[{'node':asdict(s.node),
                        'name':s.station_type,'z_kwh':list(s.curve.z),
                        'x_minutes':list(s.curve.x)} for s in p.stations]}
    (output/'scenario_inputs.json').write_text(json.dumps(inputs,indent=2)+'\n',encoding='utf-8')
    make_plots(rows,output,cases)
    return rows


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quick',action='store_true',help='Use bounded label beam, results are heuristic')
    parser.add_argument('--config',type=Path,default=ROOT/'configs'/'phase4.yaml')
    parser.add_argument('--output',type=Path,default=ROOT/'results'/'phase4')
    args=parser.parse_args()
    run_all(args.output,args.config,args.quick)


if __name__=='__main__':
    main()
