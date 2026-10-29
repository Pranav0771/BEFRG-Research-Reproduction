"""Run and independently validate Mandal et al. Section 4.1.3."""
from __future__ import annotations

from befrg import BEFRGSolver, paper_example, validate_solution


def main() -> None:
    """Display strict-positive DP solution, decisions and physical SoC."""
    p = paper_example()
    solver = BEFRGSolver(p)
    sol = solver.bottom_up(safety_check=True)
    actual = validate_solution(p, sol)
    print(f"[ours-scaled-down] DP minimum: {sol.total_minutes:.6f} min")
    print(f"Travel: {sol.travel_minutes:.6f}, charging: {sol.charging_minutes:.6f} min")
    print(f"Detours: {sol.detours}; charge added (DP model): {sol.total_charge_kwh:.6f} kWh")
    for k, action in enumerate(sol.actions):
        target = f", target={action.charge_level * p.ch:g} kWh" if action.charge_level else ""
        station = f" via {p.stations[action.station_index].node.id}" if action.station_index is not None else ""
        print(f"  {p.route[k].id} -> {p.route[k+1].id}: {action.kind}{station}{target}; next b={action.next_b}")
    print("Full path:", " -> ".join(sol.full_path))
    print("DP states:", sol.state_trace)
    print("DP model trace (node, SoC, elapsed min):")
    for visit in sol.model_visits:
        print(f"    {visit.node:5} {visit.soc_kwh:8.4f} {visit.elapsed_min:9.4f}  {visit.event}")
    print("Physical trace (node, SoC, elapsed min):")
    for visit in actual.visits:
        print(f"    {visit.node:5} {visit.soc_kwh:8.4f} {visit.elapsed_min:9.4f}  {visit.event}")
    print(f"Physical feasibility: {actual.feasible}; actual time: {actual.total_minutes:.6f} min")
    print("NOTE: Undocumented station arcs are excluded; this is a sparse-graph model.")


if __name__ == "__main__":
    main()
