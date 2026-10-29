"""E: vary gamma while holding residual grid Gamma fixed."""
from __future__ import annotations
from dataclasses import asdict
from .common import arguments, config, data_for, build, benchmark, save_csv, figure, comparison
from .paper_values import REFERENCE


def main() -> None:
    args=arguments('E');cfg=config(args);q=cfg['experiments']['E']
    raw,src=data_for('tc1c320s38ct2',args,cfg,customers=q['route_customers'],stations=q['stations'])
    rows=[]
    for g in q['charging_levels'][:3 if args.quick else None]:
        p=build(raw,cfg,customers=q['route_customers'],stations=q['stations'],gamma=g,Gamma=q['residual_levels'])
        r=benchmark(p)
        rows.append({'gamma':g,'Gamma':p.Gamma,'source':src,'provenance':'[ours-scaled-down]' if not args.full else '[ours-full]',**asdict(r)})
        print('E',g,r.rt_min,r.detours,flush=True)
    save_csv(args.output/'tables','exp_e',rows);save_csv(args.output/'tables','exp_e_paper_vs_ours',comparison('E',REFERENCE['E'],rows))
    figure(args.output/'figures','exp_e_charge_levels',[r['gamma'] for r in rows],
           {'DPC':[r['rt_min'] or float('nan') for r in rows]},xlabel='Charge-level count gamma',ylabel='Route time (min)')

if __name__=='__main__':main()
