# Architecture and implementation design

## Data flow

1. `befrg/data.py` reads original VRP-REP XML (when supplied) or creates a fixed-seed synthetic dataset.
2. `befrg/route_init.py` constructs an energy-oblivious route using cheapest insertion or nearest neighbor.
3. `befrg/energy.py` calculates delivery-load-aware consumption per arc; `befrg/charging.py` integrates piecewise-linear charging durations.
4. `befrg/befrg.py` evaluates finite residual-SoC state transitions with memoized top-down and iterative bottom-up DP.
5. `befrg/validate.py` independently reconstructs physical continuous SoC; discretized-optimal decisions can fail this validator.
6. `experiments/milp.py` solves independent discretized-flow and continuous-charge MILP comparisons using SciPy/HiGHS.
7. `befrg/physical.py` runs a physical-SoC label DP with finite charging target actions (no rounding at route nodes); certification applies to this *finite target* space only, without beam pruning.
8. `befrg/thermal.py` optionally applies bounded temperature capacity derating, HVAC auxiliary energy, and a charging-throughput cost expressed in **minutes-equivalent** (not physical charging time).
9. `experiments/` contains Phase 2 experiment A–H entry points, plus Phase 3 and Phase 4 scripts. `results/` contains recorded outputs from actual earlier runs.

## Units
Distance km, speed km/min, energy kWh, mass kg, physical time min, thermal degrees Celsius, degradation objective penalty min-equivalent. Benchmark XML speed and charging times are normalized to these units.

## Bellman recurrence
At state `(k,b)`, consider a direct traversal or detour via one charging station and one admissible target charge. State transitions floor SoC to `rc` chunks and take the minimum sum of immediate travel+charging and optimal downstream cost. Time bound: `O(|R| * |stations| * Gamma * gamma * segments)` (constant segments reduces to the original paper expression); memory `O(|R| * Gamma)` excluding process overhead.

## Physical label DP
A label stores SoC, elapsed route time, accumulated degradation cost, predecessor, and last action. At each leg it enumerates reachable station/target actions. Labels are merged only on approximately equal SoC; no general SoC dominance is assumed. As with any floating-point approximation, the 11-decimal merge tolerance means 'exact' refers to preserving continuous modeled SoC between nodes, not arbitrary-precision real arithmetic. Optional beam pruning is explicitly heuristic.

## MILP status
`experiments/milp.py` contains two models. The finite-grid MILP is an independent correctness oracle for the original discrete DP. The continuous-charge MILP uses piecewise-linear segments for an objective lower benchmark. Report solver termination status and only treat certified optimal solves as comparison optima. Both are intended primarily for small instances because the full integer model can be expensive.

## Deterministic behavior
Random seeds are documented in YAML. Report both wall clock and CPU timings where available; timing is hardware-dependent and not generally deterministic. Figures are produced from saved CSVs; raster files may differ across Matplotlib versions. Avoid silently modifying reference observations to improve agreement.

## Source vs authored code
This codebase was independently implemented from the cited article's formulation. It is neither the authors' released implementation nor a verified reproduction of their full research environment. The user's two selected Phase 3 extensions are discretization/physical executability and thermal/degradation surrogate modeling; no time-expanded predictive DP is present.
