"""Phase 3 regression tests: physical SoC grid DP and thermal model."""
from __future__ import annotations

from dataclasses import replace
from math import inf

import pytest

from befrg import BEFRGSolver, make_problem, paper_example, synthetic_instance
from befrg.physical import solve_physical_grid, validate_physical_result
from befrg.route_init import cheapest_insertion
from befrg.thermal import ThermalConfig, derated_curve, temperature_arc_energy
from experiments.milp import continuous_milp


def test_exact_soc_grid_recovers_unrounded_direct_route() -> None:
    p = paper_example()
    original = BEFRGSolver(p).bottom_up()
    improved = solve_physical_grid(p)
    assert original.total_minutes == pytest.approx(9.352)
    assert improved.solution.total_minutes == pytest.approx(7.)
    assert improved.certified_grid_optimal
    assert improved.solution.detours == 0
    assert validate_physical_result(p, improved) == (True, ())
    assert continuous_milp(p).objective_min == pytest.approx(improved.solution.total_minutes)


def test_actual_station_charge_regression() -> None:
    raw=synthetic_instance(seed=20251028,customers=28,stations=8)
    p=make_problem(raw,cheapest_insertion(raw)[:18],gamma=8,Gamma=16,theta=.00025)
    original=BEFRGSolver(p).bottom_up()
    from befrg.validate import validate_solution
    assert not validate_solution(p,original).feasible
    repaired=solve_physical_grid(p)
    good, errors=validate_physical_result(p,repaired)
    assert good,errors
    assert repaired.certified_grid_optimal


@pytest.mark.parametrize('seed', [5,11,19])
def test_grid_soc_matches_continuous_lower_bound(seed: int) -> None:
    raw=synthetic_instance(seed=seed,customers=4,stations=2)
    p=make_problem(raw,cheapest_insertion(raw),gamma=4,Gamma=8,theta=.00025)
    result=solve_physical_grid(p)
    valid,errors=validate_physical_result(p,result)
    assert valid,errors
    milp=continuous_milp(p,time_limit=8)
    assert milp.certified_optimal
    assert milp.objective_min <= result.solution.total_minutes + 1e-5


def test_temperature_capacity_and_hvac_units() -> None:
    p=paper_example()
    base=ThermalConfig()
    cold=ThermalConfig(temperature_c=0)
    hot=ThermalConfig(temperature_c=40)
    assert base.usable_capacity(8.) == pytest.approx(8.)
    assert cold.usable_capacity(8.) < hot.usable_capacity(8.) < 8
    assert base.hvac_kw() == 0.
    assert cold.hvac_kw() == pytest.approx(19*.16)
    thermal=ThermalConfig(temperature_c=0,alpha_cold=0.,heat_kw_per_c=.1)
    e_original=3.36
    e_with_hvac=temperature_arc_energy(p,0,thermal)[0]
    assert e_with_hvac == pytest.approx(e_original + 1.9 * (6/2)/60)
    with pytest.raises(ValueError):
        ThermalConfig(health_fraction=1.2)
    with pytest.raises(ValueError):
        ThermalConfig(alpha_cold=-.1)


def test_derated_curve_and_penalty() -> None:
    p=paper_example()
    station=p.stations[0]
    smaller=derated_curve(station.curve,6.)
    assert smaller.capacity == pytest.approx(6.)
    assert smaller.charging_time(0,6) == pytest.approx(station.curve.charging_time(0,8))
    cfg=ThermalConfig(degradation_weight_min=10.,degradation_beta=2.)
    assert cfg.charge_penalty_min(2.,6.,8.) == pytest.approx(2.5)
    assert cfg.charge_penalty_min(6.,6.,8.) == 0


def test_temperature_degradation_action_dp_replays() -> None:
    raw=synthetic_instance(seed=20251028,customers=7,stations=4)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16,theta=.00018)
    for temp in (-10.,0.,25.,45.):
        cfg=ThermalConfig(temperature_c=temp,degradation_weight_min=12.)
        result=solve_physical_grid(p,thermal=cfg)
        valid,errors=validate_physical_result(p,result,thermal=cfg)
        assert valid,errors
        assert result.objective_equivalent_min == pytest.approx(
            result.solution.total_minutes+result.degradation_penalty_min)
        assert result.solution.charging_minutes >= 0
        assert result.degradation_penalty_min >= 0
        assert result.effective_capacity_kwh <= p.battery
        assert result.certified_grid_optimal


def test_penalty_increases_optimal_objective_for_fixed_environment() -> None:
    raw=synthetic_instance(seed=20251028,customers=7,stations=4)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16,theta=.00018)
    objs=[]
    for w in (0.,5.,20.):
        cfg=ThermalConfig(temperature_c=-10.,degradation_weight_min=w)
        s=solve_physical_grid(p,thermal=cfg)
        assert validate_physical_result(p,s,thermal=cfg)[0]
        objs.append(s.objective_equivalent_min)
    assert all(x <= y+1e-9 for x,y in zip(objs,objs[1:]))


def test_uncertified_beam_marked_and_can_be_worse() -> None:
    raw=synthetic_instance(seed=6,customers=4,stations=2)
    p=make_problem(raw,cheapest_insertion(raw),gamma=4,Gamma=8,theta=.00025)
    exact=solve_physical_grid(p)
    assert exact.certified_grid_optimal
    try:
        limited=solve_physical_grid(p,max_labels_per_stage=3)
        assert not limited.certified_grid_optimal
        assert limited.objective_equivalent_min >= exact.objective_equivalent_min - 1e-8
        assert validate_physical_result(p,limited)[0]
    except ValueError:
        # A heavily pruned beam can be infeasible even when the complete
        # label search is feasible; this behavior is explicitly documented.
        pass


def test_physical_grid_matches_independent_tiny_bruteforce() -> None:
    """Enumerate actual-SoC paths without label merging or dynamic programming."""
    raw=synthetic_instance(seed=44,customers=2,stations=1)
    p=make_problem(raw,cheapest_insertion(raw),gamma=3,Gamma=6,theta=.00015)

    def brute(k: int,soc:float) -> float:
        if k == len(p.route)-1:
            return 0.
        u,v=p.route[k:k+2]
        e_rate=p.theta*(p.veh_mass+sum(n.demand for n in p.route[k+1:]))
        d=p.distance(u,v)
        opts=[]
        if soc-e_rate*d>1e-9:
            opts.append(d/p.speed+brute(k+1,soc-e_rate*d))
        for station in p.stations:
            d1,d2=p.distance(u,station.node),p.distance(station.node,v)
            incoming=soc-e_rate*d1
            if incoming < 0: continue
            for l in range(1,p.gamma+1):
                target=l*p.ch
                if target<=incoming+1e-9 or target-e_rate*d2<=1e-9:
                    continue
                val=(d1+d2)/p.speed+station.curve.charging_time(incoming,target)
                opts.append(val+brute(k+1,target-e_rate*d2))
        return min(opts,default=inf)

    solved=solve_physical_grid(p)
    assert solved.objective_equivalent_min == pytest.approx(brute(0,p.battery))
