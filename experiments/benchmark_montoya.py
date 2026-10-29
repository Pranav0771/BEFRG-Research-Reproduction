"""Original Montoya XML, independent cheapest-insertion tours: A/E/G/F pilot.

This is NOT an exact numerical reproduction of Mandal et al. (2025):
the original tour, vehicle mass, theta calibration, and software/hardware differ.
All results labeled [original-XML; independent-tour]. Never overwrite the
Phase 2 synthetic figures or results; separate outdir is the default.

Usage (original files installed in data/raw/montoya):
  python -m experiments.benchmark_montoya --suite all
  python -m experiments.benchmark_montoya --suite A
  python -m experiments.benchmark_montoya --suite milp-small
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
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from befrg import read_montoya_xml, make_problem, BEFRGSolver, validate_solution
from befrg.route_init import cheapest_insertion
from experiments.milp import discretized_milp, continuous_milp
from experiments.paper_values import REFERENCE
from befrg.energy import energy_rate

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = '[original-XML; independent-tour]'
RECORDS = {'A': ('tc1c320s38ct2', [50,70,90,100,150]),
           'E': ('tc1c320s38ct2', [2,4,8,16]),
           'G': ('tc2c320s38cf0',[40,80,120,160,200,240,280,320]),
           'F': ('tc2c320s38cf0',[40,80,160,240,320])}

PAPER_A = {50:6.64,70:9.87,90:13.89,100:15.74,150:23.49}
PAPER_E = {2:84.17,4:80.62,8:78.48,16:77.75}
PAPER_G = {40:(455,415),80:(968,878),120:(1442,1306),160:(2028,1875),
           200:(2623,2377),240:(3343,2982),280:(4111,3687),320:(5132,4602)}


def input_data():
    result = {}
    for name in sorted({v[0] for v in RECORDS.values()}):
        path = ROOT / 'data/raw/montoya' / (name+'.xml')
        if not path.is_file():
            raise FileNotFoundError(f'Required original Montoya file not found: {path}')
        raw = read_montoya_xml(path)
        start=time.perf_counter()
        tour=cheapest_insertion(raw)
        print(f'PARSED {name}: {len(raw.customers)} customers, {len(raw.stations)} stations; tour construction {time.perf_counter()-start:.2f} s',flush=True)
        result[name]=(raw,tour,path)
    return result


def run_solver(p, mode='DPC'):
    t0=time.perf_counter()
    cpu=time.process_time()
    sol=None; check=None; error=''
    try:
        sol=BEFRGSolver(p,mode=mode).bottom_up()
        check=validate_solution(p,sol)
    except (ValueError,RuntimeError) as exc:
        error=f'{type(exc).__name__}: {exc}'
    return dict(model_route_min=round(sol.total_minutes,9) if sol else None,
                wall_s=round(time.perf_counter()-t0,5),cpu_s=round(time.process_time()-cpu,5),
                detours=sol.detours if sol else None,
                charged_kwh=round(sol.total_charge_kwh,7) if sol else None,
                final_physical_soc_kwh=round(check.final_soc_kwh,7) if check else None,
                physically_valid=check.feasible if check else False,
                physical_error_count=len(check.errors) if check else None,
                physical_error_examples=' | '.join(check.errors[:3]) if check else error,
                model_kwh_per_km_at_first_leg=round(energy_rate(p,1),8))


def write_rows(target:Path,rows:list[dict]):
    if not rows:return
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader();w.writerows(rows)


def make_chart(out:Path,name:str,rows:list[dict],keys:tuple, labels:tuple, *, xkey:str, unit:str, title:str):
    fig,ax=plt.subplots(figsize=(8.5,4.9))
    x=[r[xkey] for r in rows]
    for key,label in zip(keys,labels):
        y=[r[key] for r in rows]
        ax.plot(x,[float(v) if v is not None else float('nan') for v in y],marker='o',label=label,linewidth=2)
    ax.set_xlabel(xkey.replace('_',' ').capitalize())
    ax.set_ylabel(unit)
    ax.set_title(title,fontsize=11)
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out/name,dpi=180)
    plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--suite',choices=['all','A','E','G','F','milp-small'],default='all')
    ap.add_argument('--output',type=Path,default=ROOT/'results/montoya_pilot')
    ap.add_argument('--milp-time-limit',type=float,default=20.)
    args=ap.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    dataset=input_data()
    meta={'source':'Original Montoya et al. 2017 VRP-REP XML',
          'dataset_sha256':{k:sha256(t[2].read_bytes()).hexdigest() for k,t in dataset.items()},
          'provenance':PROVENANCE,'route_method':'independent deterministic cheapest_insertion from befrg.route_init',
          'tour_type':'prefix of a tour built for the entire 320-customer instance, then depot return',
          'calibration':'unit demand per customer; veh_mass_kg=1000; theta=0.125/1000 kWh/(km kg); source speed/curve/energy normalization',
          'distance':'Euclidean km from original XML coordinates',
          'paper_tour_matched':False,'paper_energy_calibration_matched':False,
          'paper_runtime_hardware_matched':False,
          'uncertainty':'Do NOT compute paper-vs-ours optimality gaps; experiments are not identical controlled trials',
          'python':sys.version.split()[0],'platform':platform.platform(),
          'paper_published_reference':{'A_BERFG_h':PAPER_A,'E_BERFG_h':PAPER_E,'G_FC_DPC_min':PAPER_G},
          'masses':'customer unit mass=1kg; fixed total capacity treated as sufficient per paper upper-bound condition'}
    (out/'methodology.json').write_text(json.dumps(meta,indent=2)+'\n')

    if args.suite in ('all','A'):
        name=RECORDS['A'][0];raw,tour,_=dataset[name]
        rows=[]
        for n in RECORDS['A'][1]:
            p=make_problem(raw,tour[:n],gamma=40,Gamma=40)
            r=run_solver(p)
            row={'experiment':'A','provenance':PROVENANCE,'dataset':name,'customers':n,'route_nodes_including_depot':n+2,
                 'stations':len(p.stations),'gamma':40,'Gamma':40,
                 'paper_BERFG_h_Table2':PAPER_A[n], 'route_hash':sha256(','.join(n.id for n in p.route).encode()).hexdigest()[:16],
                 **r}
            rows.append(row)
            write_rows(out/'exp_a_original_xml.csv',rows)
            print('A',n,'hours',None if r['model_route_min'] is None else round(r['model_route_min']/60,5),'runtime',r['wall_s'],'valid',r['physically_valid'],flush=True)
        for row in rows:row['ours_model_h']=round(row['model_route_min']/60,5) if row['model_route_min'] is not None else None
        write_rows(out/'exp_a_original_xml.csv',rows)
        make_chart(out,'exp_a_original_vs_paper.png',rows,('paper_BERFG_h_Table2','ours_model_h'),('Paper Table 2 (different tour)', 'Our model (original XML, independent tour)'),xkey='customers',unit='Route time (hours)', title='Experiment A — same original instance; unmatched customer tours')

    if args.suite in ('all','E'):
        name=RECORDS['E'][0];raw,tour,_=dataset[name]
        rows=[]
        for gamma in RECORDS['E'][1]:
            p=make_problem(raw,tour,gamma=gamma,Gamma=40)
            r=run_solver(p)
            row={'experiment':'E','provenance':PROVENANCE,'dataset':name,'customers':len(tour),'stations':len(p.stations),
                 'gamma':gamma,'Gamma':40,'paper_route_h_Table6a':PAPER_E[gamma], **r}
            row['ours_model_h']=round(r['model_route_min']/60,5) if r['model_route_min'] is not None else None
            rows.append(row);write_rows(out/'exp_e_original_xml.csv',rows)
            print('E',gamma,'hours',row['ours_model_h'],'runtime',r['wall_s'],'valid',r['physically_valid'],flush=True)
        make_chart(out,'exp_e_original_vs_paper.png',rows,('paper_route_h_Table6a','ours_model_h'),('Paper Table 6a (different tour)','Our model (original XML, independent tour)'),xkey='gamma',unit='Route time (hours)',title='Experiment E — original instance, alternative customer tour')

    if args.suite in ('all','G'):
        name=RECORDS['G'][0];raw,tour,_=dataset[name]
        rows=[]
        for count in RECORDS['G'][1]:
            p=make_problem(raw,tour[:count],gamma=16,Gamma=16)
            fc=run_solver(p,mode='FC');dpc=run_solver(p,mode='DPC')
            pair=PAPER_G[count]
            row={'experiment':'G','provenance':PROVENANCE,'dataset':name,'customers':count,'gamma':16,'Gamma':16,
                 'stations':len(p.stations),'paper_FC_min_Table7a':pair[0],'paper_DPC_min_Table7a':pair[1],
                 **{'FC_'+k:v for k,v in fc.items()},**{'DPC_'+k:v for k,v in dpc.items()}}
            row['ours_DPC_improvement_pct']=round(100*(fc['model_route_min']-dpc['model_route_min'])/fc['model_route_min'],4) if fc['model_route_min'] and dpc['model_route_min'] is not None else None
            rows.append(row);write_rows(out/'exp_g_original_xml.csv',rows)
            print('G',count,'FC',fc['model_route_min'],'DPC',dpc['model_route_min'],'validFC',fc['physically_valid'],'validDPC',dpc['physically_valid'],flush=True)
        make_chart(out,'exp_g_original_vs_paper.png',rows,
                   ('paper_FC_min_Table7a','paper_DPC_min_Table7a','FC_model_route_min','DPC_model_route_min'),
                   ('Paper FC','Paper DPC','Our FC (different tour)','Our DPC (different tour)'),
                   xkey='customers',unit='Route time (minutes)',title='Experiment G — original instance; unmatched customer tours')

    if args.suite in ('all','F'):
        name=RECORDS['F'][0];raw,tour,_=dataset[name]
        rows=[]
        for count in RECORDS['F'][1]:
            p=make_problem(raw,tour[:count],gamma=16,Gamma=16)
            r=run_solver(p)
            row={'experiment':'F','provenance':PROVENANCE,'dataset':name,'customers':count,
                 'gamma':16,'Gamma':16,'stations':len(p.stations),**r}
            rows.append(row);write_rows(out/'exp_f_original_xml.csv',rows)
            print('F',count,'wall_s',r['wall_s'],'rtmin',r['model_route_min'],flush=True)
        make_chart(out,'exp_f_original_scaling.png',rows,('wall_s',),('Our wall time (Python, no tracemalloc)',),xkey='customers',unit='Wall time (seconds)',title='Experiment F — real XML, up to 320 customers (not paper 640–1600 nodes)')

    if args.suite in ('all','milp-small'):
        name='tc1c320s38ct2';raw,tour,_=dataset[name]
        rows=[]
        for n in (6,10):
            stations=tuple(sorted(raw.stations,key=lambda s:min((s.node.x-v.x)**2+(s.node.y-v.y)**2 for v in tour[:n]+(raw.depot,)))[:6])
            p=make_problem(replace(raw,stations=stations),tour[:n],gamma=8,Gamma=12)
            d=run_solver(p)
            tm=time.perf_counter(); m1=discretized_milp(p,time_limit=args.milp_time_limit);dt1=time.perf_counter()-tm
            tm=time.perf_counter(); m2=continuous_milp(p,time_limit=args.milp_time_limit);dt2=time.perf_counter()-tm
            row={'experiment':'A_small_MILP_validation','dataset':name,'provenance':PROVENANCE,
                 'customers':n,'stations':len(p.stations),'gamma':p.gamma,'Gamma':p.Gamma,'dp_objective_min':d['model_route_min'],
                 'discrete_MILP_min':m1.objective_min,'discrete_certified':m1.certified_optimal,
                 'continuous_MILP_min':m2.objective_min,'continuous_certified':m2.certified_optimal,
                 'discrete_MILP_wall_s':round(dt1,5),'continuous_MILP_wall_s':round(dt2,5),
                 'discrete_matches_DP':abs(d['model_route_min']-m1.objective_min)<1e-6 if d['model_route_min'] is not None and m1.objective_min is not None else False,
                 'physically_valid':d['physically_valid'],'errors':d['physical_error_examples'],
                 'station_ids':','.join(s.node.id for s in p.stations)}
            rows.append(row);write_rows(out/'exp_a_small_milp_crosscheck.csv',rows)
            print('A small',n,'DP',row['dp_objective_min'],'discMILP',row['discrete_MILP_min'],'contMILP',row['continuous_MILP_min'],'cert',m1.certified_optimal,m2.certified_optimal,flush=True)

    (out/'README.md').write_text('''# Original Montoya XML study — not an exact numerical paper replication

Every row labeled `[original-XML; independent-tour]` uses the **genuine Montoya et al. 2017 XML coordinates, charging curves, speed and capacity**. Tours are generated by our own deterministic cheapest-insertion heuristic; the paper reports a Solomon-inspired initial tour without enough data to reconstruct it exactly. Hence the table values are displayed side by side **for context, not for numerical-gap attribution**. We used an assumed 1000-kg empty vehicle and θ=0.125/1000 kWh/km/kg plus 1-kg load per customer. The paper's θ and mass were not released. Original source license is not claimed and XML files are not redistributed here.

## Executed suites

- `exp_a_original_xml.csv`: original 320/38 instance and published 50/70/90/100/150-customer *prefix configurations*, γ=40, Γ=40; our BEFRG vs paper Table 2 BEFRG only. Paper continuous MILP at those sizes was **not** reproduced here (3-hour CPLEX cap vs our different solver).
- `exp_a_small_milp_crosscheck.csv`: independent certified BEFRG/discrete/continuous MILP on **small 6- and 10-customer subcases** of the original XML with six selected stations, γ=8 and Γ=12; original paper did not publish these values.
- `exp_e_original_xml.csv`: all 320 original customers, 38 stations, Γ=40, γ=2/4/8/16; paper Table 6a shown but tours differ.
- `exp_g_original_xml.csv`: original 320/38 file, 40 to 320 customer prefix, γ=Γ=16, FC vs DPC; original paper Table 7a shown but tours differ.
- `exp_f_original_xml.csv`: real 320-customer file, sample prefixes up to 320 at γ=Γ=16; **not** the 640–1600-node extension reported in Table 6b.

Original BEFRG DP uses floored battery states. The independent `validate_solution` physical replay can reject some nominally optimal DP policies when their station charge target is below the continuous arrival SoC; such failures are preserved as `physically_valid=false`, with errors. `model_route_min` is the **discrete algorithm's modeled cost**, not necessarily an executable route duration. Runtime figures are local `perf_counter` wall time without `tracemalloc`; do not compare directly to the paper's CPU times or hardware.

Re-run, after manually installing Montoya XML under `data/raw/montoya/`:

```bash
python -m experiments.benchmark_montoya --suite all
```

`methodology.json` holds original-input SHA256s and modeling assumptions. This pilot does **not** verify published optimality gaps or exact empirical Table 2/6/7 values.
''',encoding='utf8')
    print('OUTPUT',out,flush=True)

if __name__=='__main__': main()
