"""Common deterministic data, timing, CSV and figure helpers for Phase 2.

Never silently substitute synthetic data for actual benchmark instance names.
Results whose source differs from the paper carry non-comparable numeric fields.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import csv
from dataclasses import asdict, dataclass, replace
from math import isfinite
from pathlib import Path
import platform
import sys
import time
import tracemalloc
from typing import Any, Callable

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import psutil
import scipy
import yaml

from befrg import BEFRGSolver, make_problem, read_montoya_xml, synthetic_instance, validate_solution
from befrg.data import Problem, RawInstance
from befrg.route_init import cheapest_insertion, nearest_neighbor

ROOT=Path(__file__).resolve().parents[1]
PAPER='https://doi.org/10.1145/3762188'


def arguments(letter: str) -> argparse.Namespace:
    """Use `--full` only with actual Montoya XML; otherwise synthetic surrogate."""
    ap=argparse.ArgumentParser(description=f'Experiment {letter} from Mandal et al. 2025')
    ap.add_argument('--config',type=Path,default=ROOT/'configs/phase2.yaml')
    ap.add_argument('--output',type=Path,default=ROOT/'results')
    ap.add_argument('--seed',type=int,default=None)
    ap.add_argument('--full',action='store_true',help='Require original benchmark XML; fail if absent')
    ap.add_argument('--quick',action='store_true',help='Reduce expensive sweeps further')
    ap.add_argument('--time-limit',type=float,default=None,help='MILP time limit in seconds')
    return ap.parse_args()


def config(args: argparse.Namespace) -> dict[str,Any]:
    with args.config.open(encoding='utf-8') as f:
        out=yaml.safe_load(f)
    if args.seed is not None:out['seed']=args.seed
    if args.time_limit is not None:out['solver']['milp_time_limit_sec']=args.time_limit
    return out


def data_for(name: str, args: argparse.Namespace, cfg: dict[str,Any], *, customers: int, stations: int) -> tuple[RawInstance,str]:
    """Raw input and exact provenance: original XML or labeled surrogate."""
    if args.full:
        paths=list((ROOT/'data/raw/montoya').rglob(f'{name}.xml'))
        if not paths:
            raise FileNotFoundError(f'Montoya {name}.xml absent. Download original archive to data/raw/montoya; no synthetic fallback in --full mode.')
        return read_montoya_xml(paths[0]),'original-benchmark'
    return synthetic_instance(seed=cfg['seed'],customers=max(customers,1),stations=stations),'synthetic-surrogate'


@lru_cache(maxsize=12)
def _cached_route(raw: RawInstance, method: str):
    """Avoid constructing the identical O(N^3) cheapest-insertion tour per sweep."""
    return (nearest_neighbor if method=='nearest_neighbor' else cheapest_insertion)(raw)


def build(raw: RawInstance, cfg:dict[str,Any], *, customers:int|None=None,
          stations:int|None=None, gamma:int|None=None,Gamma:int|None=None) -> Problem:
    """Fixed-order cheapest insertion; customer-count prefixes remain nested."""
    method=cfg['synthetic']['route_constructor']
    order=_cached_route(raw, method)
    if customers is not None:order=order[:customers]
    if stations is not None:raw=replace(raw,stations=raw.stations[:stations])
    p=make_problem(raw,order,gamma=gamma or cfg['solver']['charging_levels'],
                   Gamma=Gamma or cfg['solver']['residual_levels'],
                   veh_mass=cfg['synthetic']['veh_mass_kg'])
    if raw.name.startswith('synthetic'):
        p=replace(p,theta=p.theta*cfg['synthetic']['consumption_multiplier'])
    return p


@dataclass
class Run:
    """Raw algorithm metrics on a single fixed-route instance."""
    rt_min: float|None
    et_wall_s: float
    cpu_s: float
    allocated_peak_mb: float
    rss_after_mb: float
    rss_process_peak_mb: float
    detours: int|None
    tc_kwh: float|None
    depot_soc_kwh: float|None
    physically_feasible: bool|None
    physically_realized_min: float|None
    error: str


def benchmark(p:Problem, *, mode:str='DPC', method:str='bottom_up',repetitions:int=1) -> Run:
    """Measure runtime + memory; independent continuous route validation."""
    proc=psutil.Process()
    sample:Run|None=None
    for _ in range(repetitions):
        t0=time.perf_counter(); cpu0=proc.cpu_times();tracemalloc.start()
        try:
            solver=BEFRGSolver(p,mode=mode)
            sol=getattr(solver,method)()
            checked=validate_solution(p,sol)
            result=(sol,checked,'')
        except (ValueError,RuntimeError) as exc:
            result=(None,None,str(exc))
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        ct=proc.cpu_times()
        et=time.perf_counter()-t0
        cpu=(ct.user+ct.system)-(cpu0.user+cpu0.system)
        try:
            import resource
            rss_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        except ImportError:rss_peak=float('nan')
        sol,checked,error=result
        sample=Run(sol.total_minutes if sol else None,et,cpu,peak/(1024**2),
                   proc.memory_info().rss/(1024**2),rss_peak,
                   sol.detours if sol else None,sol.total_charge_kwh if sol else None,
                   checked.final_soc_kwh if checked else None,
                   checked.feasible if checked else None,checked.total_minutes if checked else None,error)
    assert sample is not None
    return sample


def save_csv(folder:Path,name:str,rows:list[dict[str,Any]]) -> Path:
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/f'{name}.csv'
    if not rows:return target
    cols=list(dict.fromkeys(k for row in rows for k in row.keys()))
    with target.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=cols)
        writer.writeheader();writer.writerows(rows)
    return target


def comparison(name:str, paper:list[dict[str,Any]], ours:list[dict[str,Any]],
               *, mode:str='not_same_instance') -> list[dict[str,Any]]:
    """Do NOT calculate numerical gaps across different input instances."""
    rows=[]
    for ref in paper:
        rows.append({'experiment':name,'paper_reference':ref.get('reference',''),
                     'setting':ref.get('setting',''), 'metric':ref['metric'],
                     'paper_value':ref['value'], 'paper_unit':ref.get('unit',''),
                     'paper_provenance':'[paper]','ours_value':None,'ours_provenance':'[not run]' if not ours else '[ours-scaled-down]',
                     'abs_diff':None,'relative_diff_pct':None,
                     'trend_agreement':'not evaluated',
                     'comparability':'not comparable: original inputs/route/parameter calibration unavailable' if mode=='not_same_instance' else mode})
    return rows


def figure(folder:Path,name:str, x:list[float]|tuple, series:dict[str,list[float]|tuple],
           *, xlabel:str, ylabel:str, logy:bool=False) -> Path:
    folder.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(7.4,4.2))
    for label,y in series.items():
        ax.plot(x,y,marker='o',linewidth=2,label=label)
    if logy:ax.set_yscale('log')
    ax.set_xlabel(xlabel);ax.set_ylabel(ylabel)
    ax.grid(alpha=.25)
    if len(series)>1:ax.legend()
    fig.tight_layout()
    out=folder/f'{name}.png';fig.savefig(out,dpi=175);plt.close(fig)
    return out


def runtime_environment() -> dict[str,Any]:
    return {'python':sys.version.split()[0], 'platform':platform.platform(),
            'cpu':platform.processor() or platform.machine(),
            'logical_cpus':psutil.cpu_count(), 'memory_gb':round(psutil.virtual_memory().total/1024**3,2),
            'numpy':np.__version__, 'scipy':scipy.__version__,
            'clock':'time.perf_counter wall, psutil process cpu; ET includes tracemalloc overhead',
            'rss':'current process RSS, ru_maxrss historical peak (not per-run peak)'}
