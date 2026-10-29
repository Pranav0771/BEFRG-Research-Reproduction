"""Independent Phase 2 cross-solver checks (SciPy/HiGHS)."""
from __future__ import annotations
from math import isclose

import pytest
from befrg import BEFRGSolver, make_problem, paper_example, synthetic_instance, validate_solution
from befrg.route_init import cheapest_insertion
from experiments.exp_h import Traffic, simulate
from experiments.milp import continuous_milp, discretized_milp


def test_paper_example_exact_milp_and_continuous_gap() -> None:
    p=paper_example()
    dp=BEFRGSolver(p).bottom_up()
    d=discretized_milp(p)
    c=continuous_milp(p)
    assert d.certified_optimal and c.certified_optimal
    assert d.objective_min == pytest.approx(dp.total_minutes,abs=1e-7)
    assert c.objective_min == pytest.approx(7.0,abs=1e-6)
    assert dp.total_minutes > c.objective_min


@pytest.mark.parametrize('seed', [5,11,19,27])
def test_milp_matches_dp_and_continuous_bound(seed: int) -> None:
    raw=synthetic_instance(seed=seed,customers=5,stations=2)
    p=make_problem(raw,cheapest_insertion(raw),gamma=4,Gamma=8,theta=0.00025)
    dp=BEFRGSolver(p).bottom_up()
    d=discretized_milp(p,time_limit=8)
    c=continuous_milp(p,time_limit=8)
    assert d.certified_optimal and c.certified_optimal
    assert d.objective_min == pytest.approx(dp.total_minutes,abs=1e-6)
    assert c.objective_min <= dp.total_minutes + 1e-5
    assert validate_solution(p,dp).feasible


def test_more_stations_cannot_worsen_discrete_optimum() -> None:
    raw=synthetic_instance(seed=42,customers=15,stations=4)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16,theta=0.00025)
    from dataclasses import replace
    vals=[BEFRGSolver(replace(p,stations=p.stations[:j])).bottom_up().total_minutes
          for j in (1,2,3,4)]
    assert all(a+1e-8>=b for a,b in zip(vals,vals[1:]))


def test_seeded_snapshot_traffic_reproducible() -> None:
    raw=synthetic_instance(seed=52,customers=9,stations=3)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16,theta=0.00025)
    r1=simulate(p,Traffic(p,1000,seed=99),snapshot=True)
    r2=simulate(p,Traffic(p,1000,seed=99),snapshot=True)
    assert r1 == r2
    assert r1.physically_feasible


def test_validator_detects_non_executable_dp_charge_target() -> None:
    """Regression for synthetic grid-flooring charge-target mismatch, not a pass."""
    raw=synthetic_instance(seed=20251028,customers=28,stations=8)
    from dataclasses import replace
    p=make_problem(raw,cheapest_insertion(raw)[:18],gamma=8,Gamma=16,theta=0.00025)
    sol=BEFRGSolver(p).bottom_up()
    validation=validate_solution(p,sol)
    assert not validation.feasible
    assert any('Non-increasing physical charge' in e for e in validation.errors)
