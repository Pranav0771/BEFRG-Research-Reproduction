"""Unit checks for exact charging curves and the paper's energy example."""
import pytest

from befrg import ChargingCurve, STATION_CURVES, paper_example
from befrg.energy import arc_energy, energy_rate, residual_load


def test_paper_ct_two_point_five_to_six() -> None:
    p = paper_example()
    assert p.stations[0].curve.charging_time(2.5, 6.0) == pytest.approx(6.0)
    assert p.stations[0].curve.charging_time(2.04, 6.0) == pytest.approx(6.552)
    assert p.stations[0].curve.charging_time(2.04, 4.0) == pytest.approx(2.352)


def test_charging_piecewise_additivity() -> None:
    for curve in STATION_CURVES.values():
        assert curve.charging_time(1., 14.) + curve.charging_time(14., 16.) == pytest.approx(curve.charging_time(1., 16.))
        assert curve.charging_time(10., 10.) == 0
        with pytest.raises(ValueError):
            curve.charging_time(15., 14.)
        with pytest.raises(ValueError):
            curve.charging_time(0., 17.)


def test_reject_non_monotone_curve() -> None:
    with pytest.raises(ValueError):
        ChargingCurve((0., 5., 4.), (0., 6., 12.))


def test_paper_energy_values_and_remaining_load() -> None:
    p = paper_example()
    assert [residual_load(p, i) for i in (1, 2, 3, 4)] == [3., 2., 1., 0.]
    assert [energy_rate(p, i) for i in (1, 2, 3, 4)] == pytest.approx([.56, .49, .42, .35])
    assert [arc_energy(p, i)[0] for i in range(4)] == pytest.approx([3.36, 2.45, .84, .35])
    assert arc_energy(p, 1, 0) == pytest.approx((1.96, .49))


def test_missing_paper_arcs_are_unavailable() -> None:
    p = paper_example()
    assert p.distance(p.route[0], p.stations[0].node) == float("inf")
