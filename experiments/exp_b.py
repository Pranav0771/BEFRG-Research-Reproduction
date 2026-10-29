"""B: memoized versus un-memoized search with deterministic call budget."""
from __future__ import annotations
import time
from befrg.baselines.exhaustive import exhaustive
from .common import arguments, config, data_for, build, benchmark, save_csv, figure, comparison
from .paper_values import REFERENCE


def main() -> None:
    args=arguments('B'); cfg=config(args); q=cfg['experiments']['B']
    raw,src=data_for('tc0c20s3cf2',args,cfg,customers=max(q['route_customers']),stations=q['stations'])
    rows=[]
    for n in q['route_customers'][:3 if args.quick else None]:
        p=build(raw,cfg,customers=n,stations=q['stations'],gamma=q['charge_levels'],Gamma=q['residual_levels'])
        a=benchmark(p,method='top_down')
        start=time.perf_counter()
        try:
            b=exhaustive(p,memoize=False,max_calls=q['max_calls'])
            bcost=b.minutes;calls=b.calls;limit_hit=False
        except (RuntimeError,RecursionError):
            bcost=None;calls=q['max_calls'];limit_hit=True
        et=time.perf_counter()-start
        rows.append({'route_nodes':len(p.route),'customers':n,'source':src,'provenance':'[ours-scaled-down]' if not args.full else '[ours-full]',
                     'memo_rt_min':a.rt_min,'memo_wall_s':a.et_wall_s,'memo_cpu_s':a.cpu_s,
                     'no_memo_rt_min':bcost,'no_memo_wall_s':et,'no_memo_calls_or_limit':calls,
                     'no_memo_budget_hit':limit_hit,'values_match': abs(a.rt_min-bcost)<1e-7 if a.rt_min is not None and bcost is not None else None})
        print('B',n,a.et_wall_s,et,calls,limit_hit,flush=True)
    save_csv(args.output/'tables','exp_b',rows)
    save_csv(args.output/'tables','exp_b_paper_vs_ours',comparison('B',REFERENCE['B'],rows))
    figure(args.output/'figures','exp_b_memoization',[r['customers'] for r in rows],
           {'memo':[r['memo_wall_s'] for r in rows], 'no memo':[r['no_memo_wall_s'] for r in rows]},
           xlabel='Customers (synthetic)',ylabel='Wall time (sec)',logy=True)

if __name__=='__main__':main()
