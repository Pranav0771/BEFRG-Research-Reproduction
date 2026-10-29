"""C: route-length sweep and route-feasibility metrics."""
from __future__ import annotations
from dataclasses import asdict
from .common import arguments, config, data_for, build, benchmark, save_csv, figure, comparison
from .paper_values import REFERENCE


def main() -> None:
    args=arguments('C');cfg=config(args);q=cfg['experiments']['C']
    raw,src=data_for('tc2c320s38cf0',args,cfg,customers=max(q['route_customers']),stations=q['stations'])
    rows=[]
    for n in q['route_customers'][:3 if args.quick else None]:
        p=build(raw,cfg,customers=n,stations=q['stations'])
        r=benchmark(p)
        rows.append({'customers':n,'route_nodes':len(p.route),'source':src,'provenance':'[ours-scaled-down]' if not args.full else '[ours-full]',**asdict(r)})
        print('C',n,r.rt_min,r.detours,r.et_wall_s,flush=True)
    save_csv(args.output/'tables','exp_c',rows);save_csv(args.output/'tables','exp_c_paper_vs_ours',comparison('C',REFERENCE['C'],rows))
    figure(args.output/'figures','exp_c_route_time',[r['customers'] for r in rows],
           {'DPC':[r['rt_min'] or float('nan') for r in rows]},xlabel='Customers (synthetic)',ylabel='Route time (min)')

if __name__=='__main__':main()
