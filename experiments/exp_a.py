"""A: DP vs discrete/continuous MILP, charge-state resolution sweep."""
from __future__ import annotations
from befrg import paper_example
from .common import arguments, config, data_for, build, benchmark, save_csv, figure, comparison
from .milp import discretized_milp, continuous_milp
from .paper_values import REFERENCE


def main() -> None:
    args=arguments('A'); cfg=config(args); q=cfg['experiments']['A']
    raw,source=data_for('tc1c320s38ct2',args,cfg,customers=max(q['route_customers']),stations=q['stations'])
    problems=[('paper_running_example_six_arcs',paper_example())]
    problems.extend((f'synthetic_prefix_{n}' if not args.full else f'benchmark_prefix_{n}',
                    build(raw,cfg,customers=n,stations=q['stations'],gamma=q['charge_levels'],Gamma=q['residual_levels'][0]))
                    for n in q['route_customers'][:2 if args.quick else None])
    rows=[]
    for name,base in problems:
        from dataclasses import replace
        for Gamma in ([base.Gamma] if name.startswith('paper_') else q['residual_levels'][:2 if args.quick else None]):
            p=replace(base,Gamma=Gamma)
            dp=benchmark(p)
            discrete=discretized_milp(p,time_limit=cfg['solver']['milp_time_limit_sec'])
            continuous=continuous_milp(p,time_limit=cfg['solver']['milp_time_limit_sec'])
            rt=dp.rt_min
            gap=(100*(rt-continuous.objective_min)/continuous.objective_min
                 if rt is not None and continuous.objective_min and continuous.certified_optimal else None)
            rows.append({'case':name,'source': 'paper-example-input' if name.startswith('paper_') else source,
                         'provenance':'[ours-scaled-down]' if not args.full else '[ours-full]',
                         'gamma':p.gamma,'Gamma':Gamma,'route_nodes':len(p.route), 'stations':len(p.stations),
                         'BEFRG_min':rt,'discrete_MILP_min':discrete.objective_min,
                         'discrete_certified':discrete.certified_optimal,'continuous_MILP_min':continuous.objective_min,
                         'continuous_certified':continuous.certified_optimal,'gap_pct_vs_continuous':gap,
                         'DP_MILP_same_value': (abs(rt-discrete.objective_min)<1e-6 if rt is not None and discrete.objective_min is not None else None),
                         'wall_s':dp.et_wall_s,'memory_rss_mb':dp.rss_after_mb,
                         'continuous_milp_variables':continuous.variable_count,'continuous_milp_constraints':continuous.constraint_count,
                         'discrete_milp_variables':discrete.variable_count,'discrete_milp_constraints':discrete.constraint_count,
                         'continuous_solver_message':continuous.message,'error':dp.error})
            print('A',name,Gamma,'DP',rt,'discrete',discrete.objective_min,'continuous',continuous.objective_min,'gap%',gap,flush=True)
    save_csv(args.output/'tables','exp_a',rows)
    save_csv(args.output/'tables','exp_a_paper_vs_ours',comparison('A',REFERENCE['A'],rows))
    chosen=[r for r in rows if r['case'] == problems[-1][0] and r['gap_pct_vs_continuous'] is not None]
    if chosen:figure(args.output/'figures','exp_a_gap',[r['Gamma'] for r in chosen],{'Our DP vs continuous MILP': [r['gap_pct_vs_continuous'] for r in chosen]},xlabel='Residual grid Gamma',ylabel='Optimality gap (%)')

if __name__=='__main__':main()
