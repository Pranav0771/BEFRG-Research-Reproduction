"""Compare independent brute-force search, recursive DP and iterative DP."""
import math
import random

import pytest

from befrg import BEFRGSolver, ChargingCurve, Node, Problem, Station, paper_example, validate_solution
from befrg.baselines import exhaustive, no_memo


def test_paper_combinatorial_upper_bound() -> None:
    p = paper_example()
    assert (1 + len(p.stations) * p.gamma) ** (len(p.route) - 1) == 625


def test_paper_example_optimum_on_documented_arcs() -> None:
    p = paper_example()
    a = BEFRGSolver(p).top_down(safety_check=True)
    b = BEFRGSolver(p).bottom_up(safety_check=True)
    c = no_memo(p)
    assert a.total_minutes == pytest.approx(9.352)
    assert a.total_minutes == pytest.approx(b.total_minutes)
    assert a.total_minutes == pytest.approx(c.minutes)
    assert a.state_trace == (8, 4, 3, 2, 1)
    assert [x.kind for x in a.actions] == ["direct", "detour", "direct", "direct"]
    assert a.actions[1].charge_level == 2
    physical = validate_solution(p, a)
    assert physical.feasible
    assert physical.final_soc_kwh > 0
    assert physical.total_minutes < a.total_minutes  # no floor-lost charging energy


def test_fc_not_better_than_dpc() -> None:
    p = paper_example()
    dpc = BEFRGSolver(p, mode="DPC").bottom_up()
    fc = BEFRGSolver(p, mode="FC").bottom_up()
    assert dpc.total_minutes <= fc.total_minutes
    assert fc.actions[1].charge_level == p.gamma


def _random_small_problem(seed: int) -> Problem:
    rng = random.Random(seed)
    # B=20 covers every direct arc; some short detours are optional.
    depot = Node("d", 0., 0., kind="depot")
    pts = [Node(str(k), float(k * 3), rng.uniform(-1., 1.), 1.) for k in range(1, 4)]
    station = Station(Node("s", 5., 0., kind="station"),
                      ChargingCurve((0., 12., 20.), (0., 5., 15.)))
    return Problem((depot, *pts, depot), (station,), 20., 1., .015,
                   1., 5, 10)


@pytest.mark.parametrize("seed", [0, 1, 7, 23, 91])
def test_random_small_matches_brute_force(seed: int) -> None:
    p = _random_small_problem(seed)
    top = BEFRGSolver(p).top_down()
    bot = BEFRGSolver(p).bottom_up()
    exhaustive_result = exhaustive(p)
    memo_result = exhaustive(p, memoize=True)
    assert top.total_minutes == pytest.approx(bot.total_minutes)
    assert bot.total_minutes == pytest.approx(exhaustive_result.minutes)
    assert memo_result.minutes == pytest.approx(exhaustive_result.minutes)
    assert exhaustive_result.calls >= memo_result.calls
    assert validate_solution(p, top).feasible


def test_rounding_options_and_safety_check() -> None:
    p = paper_example()
    for mode in ("floor", "round", "ceil"):
        sol = BEFRGSolver(p, rounding=mode).bottom_up()
        assert math.isfinite(sol.total_minutes)
    assert BEFRGSolver(p, rounding="floor").bottom_up(safety_check=True)


def test_oversubscribed_bruteforce_budget_fails_explicitly() -> None:
    with pytest.raises(RuntimeError):
        no_memo(_random_small_problem(1), max_calls=1)


def test_optimistic_ceil_can_be_physically_infeasible() -> None:
    """An optimistic grid does not certify actual energy feasibility."""
    depot = Node("d", 0., 0., kind="depot")
    customers = tuple(Node(f"v{k}", 0., 0.) for k in range(1, 5))
    route = (depot, *customers, depot)
    dists = {(route[k].id, route[k + 1].id): 1.9 for k in range(len(route) - 1)}
    p = Problem(route, (), 8., 1., 1., 1., 4, 8, dists, False)
    sol = BEFRGSolver(p, rounding="ceil").bottom_up()
    assert not validate_solution(p, sol).feasible
    with pytest.raises(ValueError, match="Continuous verification failed"):
        BEFRGSolver(p, rounding="ceil").bottom_up(safety_check=True)
    with pytest.raises(ValueError, match="No feasible"):
        BEFRGSolver(p, rounding="floor").bottom_up()


def test_iterative_supports_more_than_1600_route_nodes() -> None:
    """Core iterative algorithm does not depend on recursion limit."""
    depot = Node("d", 0., 0., kind="depot")
    route = (depot, *(Node(f"v{i}", 0., 0.) for i in range(1600)), depot)
    p = Problem(route, (), 8., 1., 1., 1., 4, 4)
    sol = BEFRGSolver(p).bottom_up(safety_check=True)
    assert sol.total_minutes == 0.0
    assert len(sol.actions) == 1601
    assert sol.full_path[0] == sol.full_path[-1] == "d"


def test_terminal_zero_state_contradicts_eq11() -> None:
    depot = Node("d", 0., 0., kind="depot")
    p = Problem((depot, depot), (), 8., 1., 1., 1., 4, 8,
                {("d", "d"): 8.}, False)
    with pytest.raises(ValueError, match="No feasible"):
        BEFRGSolver(p, strict_positive=True).top_down()
    literal = BEFRGSolver(p, strict_positive=False).top_down()
    assert literal.state_trace == (8, 0)
    assert not validate_solution(p, literal).feasible
