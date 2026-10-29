"""OPTIONAL SKELETON for connecting online charging choices to real SUMO.

Not executed in Phase 2. Requires local SUMO binaries, traci and a prepared
sumo.cfg generated from an OSM extract. This is an interface/skeleton, not an
implementation of the full paper's proprietary EFRGen traffic generator.

Install SUMO via https://sumo.dlr.de/docs/Installing/index.html
Then `pip install traci sumolib` and generate OSM network / routes with
SUMO's osmWebWizard or netconvert tools. Set SUMO_HOME as appropriate.
"""
from __future__ import annotations
import argparse


def run_skeleton(config: str, vehicle_id: str, *, max_steps: int = 100000) -> None:
    """Start TraCI, read edge speeds, and leave policy-actuation for integration."""
    try:
        import traci
    except ImportError as exc:
        raise RuntimeError('Install SUMO and python package traci locally') from exc
    traci.start(['sumo', '-c', config])
    try:
        for _ in range(max_steps):
            if traci.simulation.getMinExpectedNumber() == 0:
                break
            traci.simulationStep()
            active=traci.vehicle.getIDList()
            if vehicle_id not in active:
                continue
            road=traci.vehicle.getRoadID(vehicle_id)
            speed=traci.vehicle.getSpeed(vehicle_id)
            sim_time=traci.simulation.getTime()
            # An actual integration must (1) map road edges to graph distance,
            # (2) call BEFRG with measured SoC and estimated edge speeds,
            # (3) decide whether/where to charge, (4) issue traci.vehicle.setRoute,
            # (5) represent charger dwell time and physical energy state.
            # Never claim this commented placeholder is a working online controller.
            _=(road,speed,sim_time)
    finally:
        traci.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--sumo-config',required=True)
    parser.add_argument('--vehicle-id',required=True)
    args=parser.parse_args()
    run_skeleton(args.sumo_config,args.vehicle_id)
