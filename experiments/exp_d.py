"""D: nested candidate station sets to test station-availability monotonicity."""
from __future__ import annotations
from dataclasses import asdict
from .common import arguments, config, data_for, build, benchmark, save_csv, figure, comparison
from .paper_values import REFERENCE


def main() -> None:
    args=arguments('D');cfg=config(args);q=cfg['experiments']['D']
    raw,src=data_for('tc2c320s38cf0',args,cfg,customers=q['route_customers'],stations=max(q['station_counts']))
    rows=[]
    for s in q['station_counts'][:4 if args.quick else None]:
        p=build(raw,cfg,customers=q['route_customers'],stations=s)
        r=benchmark(p)
        rows.append({'station_count':s,'source':src,'provenance':'[ours-scaled-down]' if not args.full else '[ours-full]',**asdict(r)})
        print('D',s,r.rt_min,r.detours,flush=True)
    save_csv(args.output/'tables','exp_d',rows);save_csv(args.output/'tables','exp_d_paper_vs_ours',comparison('D',REFERENCE['D'],rows))
    figure(args.output/'figures','exp_d_stations',[r['station_count'] for r in rows],
           {'DPC':[r['rt_min'] or float('nan') for r in rows]},xlabel='Available stations (nested)',ylabel='Route time (min)')

if __name__=='__main__':main()
