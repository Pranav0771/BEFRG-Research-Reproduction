"""Standalone demonstration of the two Phase 3 extensions."""
from __future__ import annotations

from befrg import BEFRGSolver, make_problem, paper_example, synthetic_instance
from befrg.physical import solve_physical_grid, validate_physical_result
from befrg.route_init import cheapest_insertion
from befrg.thermal import ThermalConfig
from experiments.milp import continuous_milp


def main() -> None:
    p=paper_example()
    original=BEFRGSolver(p).bottom_up()
    corrected=solve_physical_grid(p)
    milp=continuous_milp(p,time_limit=10.)
    print('[ours-scaled-down] paper figure 2 sparse graph')
    print('BEFRG floored objective:',round(original.total_minutes,6))
    print('Physical-grid objective:',round(corrected.solution.total_minutes,6))
    print('Certified continuous MILP:',milp.objective_min,'optimal:',milp.certified_optimal)
    print('Independent continuous replay:',validate_physical_result(p,corrected))
    print('Physical SoC trace:',[(v.node,round(v.soc_kwh,3))
                                 for v in corrected.solution.model_visits])
    raw=synthetic_instance(seed=20251028,customers=7,stations=4)
    therm_problem=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16,theta=.00018)
    print('\n[ours-scaled-down] temperature-aware synthetic example')
    for t in [-10.,0.,25.,45.]:
        thermal=ThermalConfig(temperature_c=t,degradation_weight_min=8.)
        result=solve_physical_grid(therm_problem,thermal=thermal)
        good,errors=validate_physical_result(therm_problem,result,thermal=thermal)
        print(f'T={t:5.1f}C, usable={result.effective_capacity_kwh:6.3f} kWh, '
              f'route={result.solution.total_minutes:9.3f} min, '
              f'penalty={result.degradation_penalty_min:7.3f} eq-min, '
              f'objective={result.objective_equivalent_min:9.3f} eq-min, '
              f'valid={good}, errors={errors}')


if __name__=='__main__':
    main()
