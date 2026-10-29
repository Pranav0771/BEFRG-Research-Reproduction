"""Deterministic, energy-oblivious initial tour construction."""
from __future__ import annotations

from math import hypot
from .data import Node, RawInstance


def _d(a: Node, b: Node) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def nearest_neighbor(raw: RawInstance) -> tuple[Node, ...]:
    """Greedy nearest-neighbor order; stable ties use node id."""
    remaining = list(raw.customers)
    order: list[Node] = []
    prev = raw.depot
    while remaining:
        chosen = min(remaining, key=lambda n: (_d(prev, n), n.id))
        order.append(chosen)
        remaining.remove(chosen)
        prev = chosen
    return tuple(order)


def cheapest_insertion(raw: RawInstance) -> tuple[Node, ...]:
    """Cheapest tour insertion (Solomon-inspired, but NOT identical to SIH).

    No time-window, regret or seed-route terms are imposed: Montoya's
    exact initial tour construction was not specified in Mandal et al.
    """
    if not raw.customers:
        return ()
    remaining = list(raw.customers)
    route = [raw.depot, raw.depot]
    while remaining:
        choices = []
        for n in remaining:
            for i in range(1, len(route)):
                delta = _d(route[i - 1], n) + _d(n, route[i]) - _d(route[i - 1], route[i])
                choices.append((delta, n.id, i, n))
        _, _, position, chosen = min(choices, key=lambda item: item[:3])
        route.insert(position, chosen)
        remaining.remove(chosen)
    return tuple(route[1:-1])
