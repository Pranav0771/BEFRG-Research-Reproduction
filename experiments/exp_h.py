"""H: documented SUBSTITUTE for SUMO; slot-based speed and snapshot online DP.

Traffic speeds are sampled from a fixed-seed truncated Normal congestion-flow
model. This is NOT Montoya/San Francisco/Amsterdam source data or SUMO.
The route and energy model remain fixed; only travel-time factors vary by edge
and time slot. Simulation uses departure-slot speeds, not continuous car-following.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from math import inf, isfinite
import random
from .common import arguments, config, data_for, build, save_csv, figure, comparison
from .paper_values import REFERENCE
from befrg import BEFRGSolver


@dataclass(frozen=True)
class SimResult:
    """Executed policy outcomes in the lightweight surrogate traffic model."""
    realized_min: float
    detours: int
    final_soc: float
    physically_feasible: bool


class Traffic:
    """Fixed-seed, hourly flow profiles; spatially varying congestion."""
    def __init__(self,p,vehicles:int,seed:int,slot_minutes:int=60) -> None:
        self.p=p;self.slot_minutes=slot_minutes
        r=random.Random(seed)
        nodes=list(p.route)+[s.node for s in p.stations]
        pairs={(u.id,v.id) for u in nodes for v in nodes if u.id != v.id}
        self.exposure={edge:r.uniform(0.6,1.4) for edge in sorted(pairs)}
        self.flows=[]
        for slot in range(64):
            # percentage flow sampled from Normal(70, 10), paper's example
            fraction=max(5.,min(100.,r.gauss(70.,10.)))/70.
            self.flows.append(fraction)
        self.vehicles=vehicles

    def travel(self,u,v,minutes:float) -> float:
        d=self.p.distance(u,v)
        if not isfinite(d):return inf
        slot=max(0,int(minutes//self.slot_minutes))%len(self.flows)
        congestion=(self.vehicles/1500.)*self.flows[slot]*self.exposure.get((u.id,v.id),1.)
        # surrogate speed model, not a calibrated volume-delay function
        factor=1.+0.45*congestion
        return d/self.p.speed*factor


def simulate(p,traffic:Traffic, *, snapshot:bool) -> SimResult:
    """Replan at route nodes with current traffic if snapshot=True."""
    solver=BEFRGSolver(p)
    offline=solver.bottom_up()
    b=p.Gamma;soc=p.battery;t=0.;stops=0;ok=True
    for k in range(len(p.route)-1):
        u,v=p.route[k:k+2]
        if snapshot:
            timestamp=t
            @lru_cache(maxsize=None)
            def future(ix:int,state:int) -> tuple[float,object]:
                if ix==len(p.route)-1:return 0.,None
                first=float('inf');best_action=None
                a,c=p.route[ix:ix+2]
                for baseline,act in solver._transitions(ix,state):
                    if act.kind=='direct':
                        new=traffic.travel(a,c,timestamp)
                    else:
                        st=p.stations[act.station_index].node
                        base=(p.distance(a,st)+p.distance(st,c))/p.speed
                        new=baseline-base+traffic.travel(a,st,timestamp)+traffic.travel(st,c,timestamp)
                    rest,_=future(ix+1,act.next_b)
                    if new+rest<first-1e-9:first=new+rest;best_action=act
                return first,best_action
            _,action=future(k,b)
            if action is None:
                return SimResult(inf,stops,soc,False)
        else:
            action=offline.actions[k]
        if action.kind=='direct':
            t+=traffic.travel(u,v,t)
            soc-=solver._direct[k]
        else:
            st=p.stations[action.station_index]
            e1,e2=solver._detours[k][action.station_index]
            t+=traffic.travel(u,st.node,t)
            soc-=e1
            target=action.charge_level*p.ch
            if soc < -1e-8 or target<=soc+1e-9:ok=False
            else:
                t+=st.curve.charging_time(max(0.,soc),target)
                soc=target
            t+=traffic.travel(st.node,v,t)
            soc-=e2
            stops+=1
        if soc<=1e-9:ok=False
        b=action.next_b
    return SimResult(t,stops,soc,ok)


def main() -> None:
    args=arguments('H');cfg=config(args);q=cfg['experiments']['H']
    if args.full:
        raise RuntimeError('Real SUMO + CRAWDAD cannot be claimed in this generic script. Use simulators/traci_controller.py with local SUMO and actual OSM files.')
    raw,src=data_for('H_synthetic',args,cfg,customers=q['route_customers'],stations=q['stations'])
    p=build(raw,cfg,customers=q['route_customers'],stations=q['stations'])
    rows=[]
    for vehicles in q['vehicle_counts'][:3 if args.quick else None]:
        traffic=Traffic(p,vehicles,cfg['seed'],slot_minutes=q['travel_horizon_min'])
        base=simulate(p,traffic,snapshot=False)
        online=simulate(p,traffic,snapshot=True)
        rows.append({'vehicles':vehicles,'scenario':'stochastic_hourly_SUBSTITUTE','source':src,
                     'provenance':'[ours-scaled-down]','mean_flow_percent':70,'flow_sd_percent':10,
                     'static_realized_min':base.realized_min,'snapshot_realized_min':online.realized_min,
                     'static_detours':base.detours,'snapshot_detours':online.detours,
                     'static_feasible':base.physically_feasible,'snapshot_feasible':online.physically_feasible,
                     'static_final_soc':base.final_soc,'snapshot_final_soc':online.final_soc})
        print('H',vehicles,base.realized_min,online.realized_min,online.physically_feasible,flush=True)
    save_csv(args.output/'tables','exp_h_substitute',rows)
    save_csv(args.output/'tables','exp_h_paper_vs_ours',comparison('H',REFERENCE['H'],rows))
    figure(args.output/'figures','exp_h_traffic',[r['vehicles'] for r in rows],
           {'static plan':[r['static_realized_min'] for r in rows],
            'snapshot replanning':[r['snapshot_realized_min'] for r in rows]},
           xlabel='Synthetic background vehicles',ylabel='Realized route time (min)')

if __name__=='__main__':main()
