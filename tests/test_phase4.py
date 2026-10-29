"""Phase 4 case-study design and independent route feasibility tests."""
from __future__ import annotations

from dataclasses import replace
from math import isclose
from pathlib import Path

import pytest
import yaml

from befrg.physical import solve_physical_grid, validate_physical_result
from befrg.thermal import ThermalConfig
from experiments.phase4 import (build_cases, power_curve, route_km,
                                 run_one, scenarios, thermal_at)

CFG_PATH = Path(__file__).resolve().parents[1] / 'configs' / 'phase4.yaml'


@pytest.fixture(scope='module')
def cfg() -> dict:
    return yaml.safe_load(CFG_PATH.read_text())


@pytest.fixture(scope='module')
def cases(cfg: dict):
    return build_cases(cfg)


def test_four_unique_synthetic_cases_with_closed_routes(cases) -> None:
    assert set(cases) == {'last_mile', 'coach', 'truck', 'outage'}
    for case in cases.values():
        p=case.problem
        assert p.route[0].id==p.route[-1].id
        assert len(p.route)==8
        assert len({s.node.id for s in p.stations})==len(p.stations)
        assert all(isclose(s.curve.capacity,p.battery) for s in p.stations)
        assert route_km(p)>0


def test_curve_integrates_power_and_respects_taper() -> None:
    curve=power_curve(10.,(20.,10.,5.))
    assert curve.charging_time(0.,8.)==pytest.approx(24.)
    assert curve.charging_time(8.,9.5)==pytest.approx(9.)
    assert curve.charging_time(9.5,10.)==pytest.approx(6.)
    assert curve.charging_time(0.,10.)==pytest.approx(39.)
    with pytest.raises(ValueError):
        power_curve(10., (0.,10.,5.))


def test_documented_demand_and_station_count(cases) -> None:
    assert sum(v.demand for v in cases['last_mile'].problem.route)==185
    assert sum(v.demand for v in cases['truck'].problem.route)==6100
    assert sum(v.demand for v in cases['coach'].problem.route)==0
    assert len(cases['outage'].problem.stations)==5


@pytest.mark.parametrize('key', ['last_mile','coach','truck','outage'])
def test_every_core_use_case_physically_replays(cases,key) -> None:
    p=cases[key].problem
    r=solve_physical_grid(p,thermal=thermal_at(25.))
    ok,errors=validate_physical_result(p,r,thermal=thermal_at(25.))
    assert ok,errors
    assert r.certified_grid_optimal
    assert r.solution.total_minutes>0
    assert r.solution.detours>=1
    assert r.objective_equivalent_min==pytest.approx(r.solution.total_minutes)


def test_nested_station_sets_can_only_help(cases) -> None:
    base=cases['outage'].problem
    t=thermal_at(25.)
    sparse=solve_physical_grid(replace(base,stations=base.stations[:1]),thermal=t)
    medium=solve_physical_grid(replace(base,stations=base.stations[:2]),thermal=t)
    dense=solve_physical_grid(base,thermal=t)
    assert sparse.certified_grid_optimal and medium.certified_grid_optimal and dense.certified_grid_optimal
    assert dense.objective_equivalent_min <= medium.objective_equivalent_min <= sparse.objective_equivalent_min


def test_station_outage_cannot_improve_exact_grid_optimum(cases) -> None:
    p=cases['outage'].problem
    t=thermal_at(25.)
    actual=replace(p,stations=tuple(s for s in p.stations if s.station_type!='dc_mid'))
    full=solve_physical_grid(p,thermal=t)
    outage=solve_physical_grid(actual,thermal=t)
    assert outage.objective_equivalent_min>=full.objective_equivalent_min-1e-8
    assert validate_physical_result(actual,outage,thermal=t)[0]


def test_payload_reduction_does_not_increase_leg_energy(cases) -> None:
    p=cases['truck'].problem
    r=replace(p,route=tuple(replace(v,demand=0.) for v in p.route))
    t=thermal_at(25.)
    loaded=solve_physical_grid(p,thermal=t)
    empty=solve_physical_grid(r,thermal=t)
    assert empty.solution.total_minutes <= loaded.solution.total_minutes+1e-8
    assert validate_physical_result(r,empty,thermal=t)[0]


def test_no_policy_selects_target_below_real_arrival(cases,cfg) -> None:
    for key,variant,p,therm in scenarios(cases,cfg):
        result=solve_physical_grid(p,thermal=therm)
        okay,errors=validate_physical_result(p,result,thermal=therm)
        assert okay,(key,variant,errors)
        assert result.certified_grid_optimal
        assert result.solution.total_minutes>0
        assert result.objective_equivalent_min>=result.solution.total_minutes


def test_repeated_run_is_bitwise_identical_in_objective(cases) -> None:
    p=cases['last_mile'].problem
    t=thermal_at(0.,weight_min=8.,hvac_kw_per_c=.016)
    first=solve_physical_grid(p,thermal=t)
    second=solve_physical_grid(p,thermal=t)
    assert first.solution.actions==second.solution.actions
    assert first.objective_equivalent_min==second.objective_equivalent_min
    assert first.solution.total_minutes==second.solution.total_minutes


def test_synthetic_values_are_declared_not_real_measurements(cases) -> None:
    assert all(case.seed==20261028 for case in cases.values())
    assert 'synthetic' in cases['coach'].curves_description.lower()
