"""Two independent HiGHS-backed MILP baselines using scipy.optimize.milp.

(1) Discrete: 0/1 unit-flow shortest path through the BEFRG state-action DAG;
    it has the exact same FEASIBLE action space as floor/strict-positive BEFRG.
(2) Continuous: 0/1 per-leg direct-vs-station decision, continuous node SoC,
    exact piecewise-linear cumulative charging time represented by binary
    segment selection and fractional segment occupancy. Station visits have
    positive energy gain. Unlike the paper's DP, charge targets are continuous.

Both solve only the fixed tour, with at most one charging station per route arc.
No solver incumbents are called optimal without a zero-status certificate.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, inf, isfinite
from typing import Mapping

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from befrg.data import Problem
from befrg.energy import energy_rate


@dataclass(frozen=True)
class MilpResult:
    """Optimal/feasible objective and HiGHS termination information."""
    objective_min: float | None
    status: str
    certified_optimal: bool
    mip_gap: float | None
    message: str
    variable_count: int
    constraint_count: int


class Model:
    """Lightweight sparse mixed-integer linear constraint assembler."""
    def __init__(self) -> None:
        self.cost: list[float] = []
        self.lb: list[float] = []
        self.ub: list[float] = []
        self.integer: list[int] = []
        self.rows: list[dict[int, float]] = []
        self.row_lb: list[float] = []
        self.row_ub: list[float] = []

    def var(self, *, cost: float = 0., lo: float = 0., hi: float = inf, binary: bool = False) -> int:
        idx = len(self.cost)
        self.cost.append(float(cost)); self.lb.append(float(lo)); self.ub.append(float(1 if binary else hi)); self.integer.append(int(binary))
        return idx

    def eq(self, coeff: Mapping[int, float], target: float) -> None:
        self.bound(coeff, target, target)

    def bound(self, coeff: Mapping[int, float], lower: float = -inf, upper: float = inf) -> None:
        self.rows.append({j: float(v) for j, v in coeff.items() if abs(v) > 1e-13})
        self.row_lb.append(float(lower)); self.row_ub.append(float(upper))

    def active_eq(self, coeff: dict[int, float], rhs: float, selector: int, M: float) -> None:
        """When selector=1 enforce sum(coeff*x)=rhs, otherwise relax by +/-M."""
        plus = dict(coeff); plus[selector] = plus.get(selector, 0.) + M
        minus = dict(coeff); minus[selector] = minus.get(selector, 0.) - M
        self.bound(plus, upper=rhs + M)
        self.bound(minus, lower=rhs - M)

    def solve(self, *, time_limit: float = 10.) -> MilpResult:
        rr: list[int] = []; cc: list[int] = []; vv: list[float] = []
        for i, row in enumerate(self.rows):
            for j, value in row.items():
                rr.append(i); cc.append(j); vv.append(value)
        mat = coo_matrix((vv, (rr, cc)), shape=(len(self.rows), len(self.cost))).tocsr()
        try:
            res = milp(c=np.array(self.cost), integrality=np.array(self.integer),
                       bounds=Bounds(self.lb, self.ub),
                       constraints=LinearConstraint(mat, self.row_lb, self.row_ub),
                       options={"time_limit": float(time_limit), "mip_rel_gap": 1e-9})
            obj = float(res.fun) if getattr(res, "fun", None) is not None and isfinite(res.fun) else None
            return MilpResult(obj, str(res.status), res.status == 0, 
                              float(res.mip_gap) if getattr(res, 'mip_gap', None) is not None else None,
                              str(res.message), len(self.cost), len(self.rows))
        except Exception as exc:
            return MilpResult(None, 'error', False, None, str(exc), len(self.cost), len(self.rows))


def discretized_milp(p: Problem, *, time_limit: float = 10.) -> MilpResult:
    """Independent binary state-transition flow MILP, floor rounding, b>=1.

    Does not call the BEFRGSolver or its transitions. Reconstructs the
    recurrence directly from Problem, energy_rate and charging curves.
    """
    m = Model()
    n = len(p.route)
    edges: list[tuple[tuple[int,int] | str, tuple[int,int] | str, int]] = []
    for k in range(n-1):
        u,v = p.route[k:k+2]; rate = energy_rate(p,k+1)
        for b in range(1,p.Gamma+1):
            available = b*p.rc
            d=p.distance(u,v); energy=d*rate
            if isfinite(d) and available+1e-10>=energy:
                nb=floor((available-energy)/p.rc+1e-11)
                if nb>=1:
                    idx=m.var(cost=d/p.speed,binary=True)
                    edges.append(((k,b),(k+1,nb),idx))
            for station in p.stations:
                d1=p.distance(u, station.node); d2=p.distance(station.node,v)
                if not (isfinite(d1) and isfinite(d2)) or available+1e-10<d1*rate:
                    continue
                arrival=max(0.,available-d1*rate)
                for level in range(max(1,floor(arrival/p.ch+1e-11)+1),p.gamma+1):
                    target=level*p.ch
                    if target<=arrival+1e-10 or target+1e-10<d2*rate:
                        continue
                    nb=floor((target-d2*rate)/p.rc+1e-11)
                    if nb<1:continue
                    cost=(d1+d2)/p.speed+station.curve.charging_time(arrival,target)
                    idx=m.var(cost=cost,binary=True)
                    edges.append(((k,b),(k+1,nb),idx))
    for b in range(1,p.Gamma+1):
        idx=m.var(binary=True)
        edges.append(((n-1,b),'sink',idx))
    rows: dict[tuple[int,int] | str,dict[int,float]] = {}
    for source,dest,idx in edges:
        rows.setdefault(source,{})[idx]=rows.setdefault(source,{}).get(idx,0.)+1.
        rows.setdefault(dest,{})[idx]=rows.setdefault(dest,{}).get(idx,0.)-1.
    for key,coeff in rows.items():
        m.eq(coeff,1. if key==(0,p.Gamma) else (-1. if key=='sink' else 0.))
    return m.solve(time_limit=time_limit)


def continuous_milp(p: Problem, *, time_limit: float = 10., eps: float = 1e-5) -> MilpResult:
    """Exact continuous SoC charging MILP with disjunctive nonlinear segments.

    The cumulative charge-time function P(y) is piecewise-linear. We model
    segment membership explicitly for both incoming and outgoing SoC so the
    charging objective P(yout)-P(yin) is EXACT (no epigraph relaxation).
    """
    m=Model(); B=p.battery; n=len(p.route)
    y=[m.var(lo=B,hi=B)]+[m.var(lo=eps,hi=B) for _ in range(n-1)]

    def piecewise_value(z:int, value:int, curve, *, cost_sign:float) -> None:
        """Use exactly one segment if z=1; all variables zero if z=0."""
        segs=len(curve.z)-1
        a=[m.var(binary=True) for _ in range(segs)]
        q=[m.var(lo=0.,hi=1.) for _ in range(segs)]
        m.eq({**{v:1. for v in a}, z:-1.},0.)
        for ai,qi in zip(a,q):m.bound({qi:1.,ai:-1.},upper=0.)
        eq={value:1.}
        for i in range(segs):
            eq[a[i]]=eq.get(a[i],0.)-curve.z[i]
            eq[q[i]]=eq.get(q[i],0.)-(curve.z[i+1]-curve.z[i])
        m.eq(eq,0.)
        # Add actual cumulative charging-time contribution to objective directly.
        for i in range(segs):
            m.cost[a[i]]+=cost_sign*curve.x[i]
            m.cost[q[i]]+=cost_sign*(curve.x[i+1]-curve.x[i])

    for k in range(n-1):
        u,v=p.route[k:k+2]; rate=energy_rate(p,k+1)
        choices=[]
        d=p.distance(u,v)
        if isfinite(d) and d*rate <= B-eps:
            z=m.var(cost=d/p.speed,binary=True)
            choices.append(z)
            m.active_eq({y[k+1]:1.,y[k]:-1.},-d*rate,z,3*B+2*d*rate)
        for station in p.stations:
            d1=p.distance(u,station.node); d2=p.distance(station.node,v)
            if not isfinite(d1) or not isfinite(d2) or d1*rate>B or d2*rate>=B-eps:
                continue
            z=m.var(cost=(d1+d2)/p.speed,binary=True)
            choices.append(z)
            incoming=m.var(lo=0.,hi=B)
            outgoing=m.var(lo=0.,hi=B)
            for value in (incoming,outgoing):m.bound({value:1.,z:-B},upper=0.)
            # incoming = node SoC - first leg; next SoC = outgoing - second leg
            m.active_eq({incoming:1.,y[k]:-1.},-d1*rate,z,3*B+2*d1*rate)
            m.active_eq({y[k+1]:1.,outgoing:-1.},-d2*rate,z,3*B+2*d2*rate)
            m.bound({outgoing:1.,incoming:-1.,z:-eps},lower=0.)
            piecewise_value(z,incoming,station.curve,cost_sign=-1.)
            piecewise_value(z,outgoing,station.curve,cost_sign=+1.)
        if not choices:
            return MilpResult(None,'infeasible',False,None,f'No arcs at position {k}',len(m.cost),len(m.rows))
        m.eq({z:1. for z in choices},1.)
    return m.solve(time_limit=time_limit)
