"""Problem objects, deterministic synthetic data and Montoya VRP-REP XML reader.

Units internally: km, kWh, minutes, kg. XML battery values are Wh;
XML charging times are hours and XML speed is km/hour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, isclose
from pathlib import Path
import random
import xml.etree.ElementTree as ET

from .charging import ChargingCurve, STATION_CURVES


@dataclass(frozen=True)
class Node:
    """Depot, customer or station location; demand is delivered here (kg)."""

    id: str
    x: float
    y: float
    demand: float = 0.0
    kind: str = "customer"


@dataclass(frozen=True)
class Station:
    """Charging station and its exact nonlinear charging curve."""

    node: Node
    curve: ChargingCurve
    station_type: str = "fast"


@dataclass(frozen=True)
class RawInstance:
    """Coordinates and vehicle data before choosing the energy-unaware tour."""

    name: str
    depot: Node
    customers: tuple[Node, ...]
    stations: tuple[Station, ...]
    battery_kwh: float = 16.0
    speed_km_min: float = 40.0 / 60.0
    nominal_kwh_km: float = .125


@dataclass(frozen=True)
class Problem:
    """Fixed-route instance for the BEFRG dynamic program.

    ``distances`` optionally holds directed measured distances. If
    ``euclidean_fallback`` is False, all unspecified arcs are unavailable.
    """

    route: tuple[Node, ...]
    stations: tuple[Station, ...]
    battery: float
    speed: float
    theta: float
    veh_mass: float
    gamma: int
    Gamma: int
    distances: dict[tuple[str, str], float] = field(default_factory=dict)
    euclidean_fallback: bool = True

    def __post_init__(self) -> None:
        if len(self.route) < 2 or self.route[0].id != self.route[-1].id:
            raise ValueError("Route must begin and end at same depot")
        if self.battery <= 0 or self.speed <= 0 or self.theta <= 0 or self.veh_mass <= 0:
            raise ValueError("Positive battery, speed, theta and vehicle mass required")
        if self.gamma <= 0 or self.Gamma <= 0:
            raise ValueError("Discretization dimensions must be positive")
        if any(n.demand < 0 for n in self.route):
            raise ValueError("Negative delivery demand unsupported")
        if any(not isclose(s.curve.capacity, self.battery, abs_tol=1e-7)
               for s in self.stations):
            raise ValueError("Station curve capacity must equal battery capacity")
        if len({s.node.id for s in self.stations}) != len(self.stations):
            raise ValueError("Station IDs must be unique")

    @property
    def rc(self) -> float:
        """Residual battery state chunk size, kWh."""
        return self.battery / self.Gamma

    @property
    def ch(self) -> float:
        """Charging target chunk size, kWh."""
        return self.battery / self.gamma

    def distance(self, u: Node, w: Node) -> float:
        """Return directed distance, or infinity when edge is unavailable."""
        if (u.id, w.id) in self.distances:
            return self.distances[u.id, w.id]
        if self.euclidean_fallback:
            return hypot(u.x - w.x, u.y - w.y)
        return float("inf")


def _text(element: ET.Element, path: str, default: str | None = None) -> str:
    child = element.find(path)
    if child is None or child.text is None:
        if default is None:
            raise ValueError(f"Missing XML element: {path}")
        return default
    return child.text.strip()


def read_montoya_xml(path: str | Path) -> RawInstance:
    """Parse the Montoya VRP-REP XML instance (no author source code used).

    Node types 0/1/2 mean depot/customer/station. Fleet battery and
    breakpoints are Wh, time is hours. Service times, time windows and
    the source CVRP fleet capacity are not used by fixed-route BEFRG.
    """
    root = ET.parse(path).getroot()
    profile = root.find("./fleet/vehicle_profile")
    if profile is None:
        raise ValueError("Missing fleet vehicle profile")
    name = root.findtext("./info/name") or Path(path).stem
    battery = float(_text(profile, "./custom/battery_capacity")) / 1000
    speed = float(_text(profile, "./speed_factor")) / 60
    nominal_rate = float(_text(profile, "./custom/consumption_rate", "125")) / 1000
    curves: dict[str, ChargingCurve] = {}
    for fun in profile.findall("./custom/charging_functions/function"):
        typ = fun.attrib.get("cs_type", "fast").lower()
        bp = fun.findall("./breakpoint")
        z = tuple(float(_text(b, "./battery_level")) / 1000 for b in bp)
        x = tuple(float(_text(b, "./charging_time")) * 60 for b in bp)
        curves[typ] = ChargingCurve(z, x)
    nodes = root.findall("./network/nodes/node")
    if not nodes:
        raise ValueError("No network nodes in XML")
    depot: Node | None = None
    customers: list[Node] = []
    stations: list[Station] = []
    for n in nodes:
        typ = n.attrib.get("type")
        ident = str(n.attrib["id"])
        x, y = float(_text(n, "cx")), float(_text(n, "cy"))
        if typ == "0":
            depot = Node(ident, x, y, kind="depot")
        elif typ == "1":
            customers.append(Node(ident, x, y, demand=1.0))
        elif typ == "2":
            kind = _text(n, "./custom/cs_type").lower()
            if kind not in curves:
                raise ValueError(f"No charging curve for station type {kind}")
            stations.append(Station(Node(ident, x, y, kind="station"), curves[kind], kind))
        else:
            raise ValueError(f"Unexpected node type {typ}")
    if depot is None:
        raise ValueError("Missing depot")
    return RawInstance(name, depot, tuple(customers), tuple(stations), battery, speed, nominal_rate)


def synthetic_instance(seed: int = 42, customers: int = 8, stations: int = 3) -> RawInstance:
    """Generate a repeatable, structurally equivalent synthetic instance.

    Not a replacement for Montoya benchmark results. Unit customer loads,
    2D Euclidean kilometres and the three published station curves are used.
    """
    if customers < 1 or stations < 0:
        raise ValueError("Invalid numbers of customers/stations")
    rng = random.Random(seed)
    depot = Node("0", 12.5, 12.5, kind="depot")
    locs = [Node(str(i), rng.uniform(0, 25), rng.uniform(0, 25), demand=1.0)
            for i in range(1, customers + 1)]
    charge = [Station(Node(f"c{j}", rng.uniform(0, 25), rng.uniform(0, 25), kind="station"),
                      STATION_CURVES[("fast", "normal", "slow")[j % 3]],
                      ("fast", "normal", "slow")[j % 3])
              for j in range(stations)]
    return RawInstance(f"synthetic_s{seed}", depot, tuple(locs), tuple(charge))


def make_problem(raw: RawInstance, ordered_customers: tuple[Node, ...], *,
                 gamma: int = 16, Gamma: int = 16,
                 veh_mass: float = 1000.0, theta: float | None = None) -> Problem:
    """Build a fixed tour; default theta gives an empty-vehicle .125 kWh/km.

    Calibration is OUR assumption, not a recovered parameter from the paper.
    """
    if theta is None:
        theta = raw.nominal_kwh_km / veh_mass
    expected = {n.id for n in raw.customers}
    ids = [n.id for n in ordered_customers]
    if len(ids) != len(set(ids)) or any(i not in expected for i in ids):
        raise ValueError("Route must contain unique known customers")
    return Problem((raw.depot, *ordered_customers, raw.depot), raw.stations,
                   raw.battery_kwh, raw.speed_km_min, theta, veh_mass, gamma, Gamma)


def paper_example() -> Problem:
    """Figure 2(b) directed sparse graph; undocumented arcs are unavailable.

    Depot is v1 on departure and v5 on return, stored with same physical id.
    Only six explicitly supplied directed arc distances are usable.
    """
    depot = Node("depot", 0., 0., kind="depot")
    a, b, c = (Node(f"v{i}", float(i), 0., demand=1.) for i in (2, 3, 4))
    station = Station(Node("c", 2.5, 1., kind="station"),
                      ChargingCurve((0., 5., 7., 8.), (0., 6., 12., 18.)))
    distances = {
        ("depot", "v2"): 6., ("v2", "v3"): 5.,
        ("v3", "v4"): 2., ("v4", "depot"): 1.,
        ("v2", "c"): 4., ("c", "v3"): 1.,
    }
    return Problem((depot, a, b, c, depot), (station,), 8., 2., .07,
                   5., 4, 8, distances, euclidean_fallback=False)
