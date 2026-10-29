"""G: paired FC and DPC policy comparisons on each identical fixed route."""
from __future__ import annotations
from .common import arguments, config, data_for, build, benchmark, save_csv, figure, comparison
from .paper_values import REFERENCE
from befrg import BEFRGSolver, validate_solution


def main() -> None:
    args=arguments('G');cfg=config(args);q=cfg['experiments']['G']
    raw,src=data_for('tc2c320s38cf0',args,cfg,customers=max(q['route_customers']),stations=q['stations'])
    rows=[]
    for n in q['route_customers'][:4 if args.quick else None]:
        p=build(raw,cfg,customers=n,stations=q['stations'])
        fc=benchmark(p,mode='FC');dpc=benchmark(p,mode='DPC')
        rows.append({'customers':n,'source':src,'provenance':'[ours-scaled-down]' if not args.full else '[ours-full]',
                     'FC_RT_min':fc.rt_min,'DPC_RT_min':dpc.rt_min,
                     'FC_ET_s':fc.et_wall_s,'DPC_ET_s':dpc.et_wall_s,
                     'FC_detours':fc.detours,'DPC_detours':dpc.detours,
                     'FC_charge_kwh':fc.tc_kwh,'DPC_charge_kwh':dpc.tc_kwh,
                     'FC_feasible':fc.physically_feasible,'DPC_feasible':dpc.physically_feasible,
                     'FC_validation_errors':' | '.join(validate_solution(p,BEFRGSolver(p,mode='FC').bottom_up()).errors),
                     'DPC_validation_errors':' | '.join(validate_solution(p,BEFRGSolver(p,mode='DPC').bottom_up()).errors),
                     'RT_improvement_pct':100*(fc.rt_min-dpc.rt_min)/fc.rt_min if fc.rt_min and dpc.rt_min is not None else None})
        print('G',n,fc.rt_min,dpc.rt_min,flush=True)
    save_csv(args.output/'tables','exp_g',rows);save_csv(args.output/'tables','exp_g_paper_vs_ours',comparison('G',REFERENCE['G'],rows))
    figure(args.output/'figures','exp_g_fc_dpc',[r['customers'] for r in rows],
           {'FC':[r['FC_RT_min'] or float('nan') for r in rows],
            'DPC':[r['DPC_RT_min'] or float('nan') for r in rows]},
           xlabel='Customers (synthetic)',ylabel='Route time (min)')

if __name__=='__main__':main()
