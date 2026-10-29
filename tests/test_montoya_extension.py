"""Tests for correctness of dominance pruning and genuine-XML optional regression."""
from dataclasses import replace
from pathlib import Path

import pytest

from befrg import make_problem, read_montoya_xml, synthetic_instance
from befrg.physical import solve_physical_grid, validate_physical_result
from befrg.route_init import cheapest_insertion
from befrg.thermal import ThermalConfig


def test_euclidean_dominance_pruning_preserves_finite_grid_optimum():
    raw = synthetic_instance(seed=42,customers=8,stations=3)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16)
    unpruned=solve_physical_grid(p)
    dominated=solve_physical_grid(p,dominance_pruning=True)
    assert unpruned.certified_grid_optimal and dominated.certified_grid_optimal
    assert dominated.solution.total_minutes == pytest.approx(unpruned.solution.total_minutes)
    assert validate_physical_result(p,dominated)[0]


def test_dominance_with_temperature_and_degradation():
    raw=synthetic_instance(seed=44,customers=7,stations=3)
    p=make_problem(raw,cheapest_insertion(raw),gamma=6,Gamma=12)
    therm=ThermalConfig(temperature_c=10,heat_kw_per_c=.04,degradation_weight_min=7.)
    a=solve_physical_grid(p,thermal=therm)
    b=solve_physical_grid(p,thermal=therm,dominance_pruning=True)
    assert a.objective_equivalent_min==pytest.approx(b.objective_equivalent_min)
    assert validate_physical_result(p,b,thermal=therm)[0]


def test_dominance_refuses_sparse_or_directed_distance_overrides():
    raw=synthetic_instance(seed=42,customers=5,stations=2)
    p=make_problem(raw,cheapest_insertion(raw),gamma=6,Gamma=12)
    with pytest.raises(ValueError,match='Euclidean'):
        solve_physical_grid(replace(p,euclidean_fallback=False),dominance_pruning=True)
    with pytest.raises(ValueError,match='Euclidean'):
        solve_physical_grid(replace(p,distances={(p.route[0].id,p.route[1].id):10.}),dominance_pruning=True)


def test_dominance_full_charge_same_result_as_unpruned():
    raw=synthetic_instance(seed=47,customers=8,stations=3)
    p=make_problem(raw,cheapest_insertion(raw),gamma=8,Gamma=16)
    original=solve_physical_grid(p,mode='FC')
    pruned=solve_physical_grid(p,mode='FC',dominance_pruning=True)
    assert original.solution.total_minutes==pytest.approx(pruned.solution.total_minutes)
    assert validate_physical_result(p,pruned)[0]


def test_actual_montoya_regression_if_xml_available():
    path=Path(__file__).resolve().parents[1]/'data/raw/montoya/tc2c320s38cf0.xml'
    if not path.exists(): pytest.skip('Original Montoya XML is not shipped in code release')
    raw=read_montoya_xml(path)
    tour=cheapest_insertion(raw)
    p=make_problem(raw,tour[:40],gamma=16,Gamma=16)
    result=solve_physical_grid(p,dominance_pruning=True)
    assert result.certified_grid_optimal
    assert validate_physical_result(p,result)[0]
    assert result.solution.total_minutes==pytest.approx(471.826053970,rel=1e-7)
