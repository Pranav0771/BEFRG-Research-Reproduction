"""Montoya XML parsing and deterministic route constructor tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from befrg import STATION_CURVES, make_problem, read_montoya_xml, synthetic_instance
from befrg.route_init import cheapest_insertion, nearest_neighbor


MINI_XML = """<?xml version="1.0"?>
<instance>
 <info><name>toy_montoya_format</name></info>
 <network><nodes>
  <node id="0" type="0"><cx>0</cx><cy>0</cy></node>
  <node id="1" type="1"><cx>1</cx><cy>2</cy></node>
  <node id="2" type="1"><cx>3</cx><cy>4</cy></node>
  <node id="3" type="2"><cx>2</cx><cy>2</cy><custom><cs_type>fast</cs_type></custom></node>
 </nodes><euclidean/><decimals>14</decimals></network>
 <fleet><vehicle_profile type="0"><speed_factor>40</speed_factor><custom>
  <consumption_rate>125</consumption_rate><battery_capacity>16000</battery_capacity>
  <charging_functions><function cs_type="fast">
   <breakpoint><battery_level>0</battery_level><charging_time>0</charging_time></breakpoint>
   <breakpoint><battery_level>13600</battery_level><charging_time>0.31</charging_time></breakpoint>
   <breakpoint><battery_level>15200</battery_level><charging_time>0.39</charging_time></breakpoint>
   <breakpoint><battery_level>16000</battery_level><charging_time>0.51</charging_time></breakpoint>
  </function></charging_functions>
 </custom></vehicle_profile></fleet>
 <requests><request id="1" node="1"><service_time>.5</service_time></request></requests>
</instance>"""


def test_parser_units_and_station_profile(tmp_path: Path) -> None:
    xml = tmp_path / "toy.xml"
    xml.write_text(MINI_XML, encoding="utf-8")
    raw = read_montoya_xml(xml)
    assert len(raw.customers) == 2
    assert len(raw.stations) == 1
    assert raw.battery_kwh == pytest.approx(16.)
    assert raw.speed_km_min == pytest.approx(40 / 60)
    assert raw.nominal_kwh_km == pytest.approx(.125)
    assert raw.stations[0].curve.x == pytest.approx(STATION_CURVES["fast"].x)
    p = make_problem(raw, tuple(raw.customers))
    assert p.theta * p.veh_mass == pytest.approx(.125)
    assert len(p.route) == 4


def test_synthetic_deterministic_and_tours() -> None:
    a = synthetic_instance(seed=123, customers=9, stations=3)
    b = synthetic_instance(seed=123, customers=9, stations=3)
    assert a == b
    assert len(a.stations) == 3
    for constructor in (cheapest_insertion, nearest_neighbor):
        order = constructor(a)
        assert set(order) == set(a.customers)
        assert len(order) == len(a.customers)
        p = make_problem(a, order, gamma=4, Gamma=8)
        assert p.gamma == 4 and p.Gamma == 8


def test_problem_rejects_mismatched_route_and_station_capacity() -> None:
    a = synthetic_instance(seed=3, customers=3, stations=1)
    with pytest.raises(ValueError):
        make_problem(a, (a.customers[0], a.customers[0]))
