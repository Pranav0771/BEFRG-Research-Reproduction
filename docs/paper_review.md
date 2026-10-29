# Critical paper review — Phase 0

**Source:** Dipankar Mandal, Arnab Sarkar and Arijit Mondal, *A Discrete Partial Charging Enabled Dynamic Programming Strategy for Optimal Fixed-Route Electric Vehicle Charging*, ACM Transactions on Embedded Computing Systems 24(5s), Article 154 (September 2025). DOI: https://doi.org/10.1145/3762188.

## Plain-language summary

A delivery EV follows an already fixed sequence of customers. Because the battery may be insufficient, a planner may insert one charging station between adjacent customers and decide how much battery energy to replenish. Charging is slower as charge levels rise, so insisting on a full battery at every visit can waste time. The paper proposes BEFRG, a dynamic programming procedure that evaluates direct travel and detours with discrete charging targets, minimizing route travel and charging time with delivery-load-dependent energy usage. It also presents EFRGen, an online traffic simulator using SUMO and OpenStreetMap. The algorithm is efficient for the **discretized** model; that is not the same as proving an optimum for continuous battery dynamics.

## Scope and motivation

Vehicle routing solves customer assignment and ordering; fixed-route vehicle charging solves the subsequent energy-feasibility problem, taking that customer order as given. This hierarchy can significantly reduce search complexity for mixed electric and conventional fleets. Yet it also means an excellent charging policy cannot repair a poor customer tour. The model intentionally chooses charging opportunities, not which deliveries should share a vehicle, and does not include customer time windows, waiting for chargers, or route reshuffling.

## Formulation audit (Equations 1–21)

- Equations 1–3: station charging rate equals energy difference divided by time difference; integrate inverse slope over the intersection of departure/arrival SoC with each segment. Correct when breakpoints are monotone and the target is at least the arrival SoC; zero-width segments must be rejected.
- Equations 4–6: remaining delivery load is the sum of unmet customer demands; energy consumption on a leg is `theta * (remaining_mass + vehicle_mass) * distance`. Correct for the assumed constant mass-linear surrogate, but it omits gradients, speed dependence, acceleration and environmental load.
- Equation 7: travel time equals distance divided by positive fixed speed; correct with consistent time and distance units.
- Equations 8–9: minimize travel plus charging time with at most one detour per original route arc. The binary-choice objective is conceptually sound but the charge-time term and implicit SoC need further linearization for an executable MILP.
- Equations 10–12: full battery initially, strictly positive SoC at demand points and depot, station arrival non-negative and station charging strictly increasing. Algorithm 1's literal recurrence can create a zero arrival state at a demand point, so the implementation must decide whether to enforce Equation 11 or reproduce the unguarded pseudocode.
- Equations 13–15: continuous SoC accounting, station arrival energy, and total load-capacity bound. The continuous SoC relation is **not identical** to the DP's repeatedly floored battery state. The station arrival equation applies conditionally to the chosen detour. Capacity feasibility must be checked when the initial tour is generated.
- Equations 16–20: two-way Bellman recursion, direct option and minimum over stations and discrete charge targets. Valid given static prices/speeds and the state sufficiency assumption, but needs a strict positivity guard and a policy reconstruction check.
- Equation 21: current edge travel time from instantaneous speed. This supports snapshot replanning, not a prediction of how fast a future edge will be when traversed later.

## Algorithm 1: state correctness

The state `(route_position, residual_chunk)` is sufficient because all earlier actions influence future options only through their available energy when the route sequence is fixed and environment static. Memoization prevents recomputing overlapping suffix problems. Each state considers the direct option followed by each reachable charging station and each charge target. The value function can therefore be optimal for the **finite-state surrogate**. However, flooring a continuous battery value loses charge at each modeled node; the DP may exclude physically feasible routes. The returned policy can also prescribe a target below the actual arrival SoC, making a discrete-optimal policy physically non-executable. The independent validator must evaluate true SoC without flooring.

The terminal condition should reject zero battery if the model requires positive residual SoC at the depot. An optional literal-pseudocode mode may allow zero, but must never be conflated with the intended physical constraint. The one-station-per-arc constraint also rules out otherwise possible station-to-station sequences. No global optimality guarantee applies outside the allowed detour/charge target action set.

## Algorithm 2: online behavior

The published online pseudocode refers to `b_(k+1)` before setting it, uses `best_cost` without a properly initialized direct baseline, and initializes some choice variables outside the per-node loop. It also needs a clear failure/termination action on infeasibility and an explicit physical SoC update. This makes Algorithm 2 an incomplete executable specification. Its use of the instantaneous speed snapshot to score future legs yields a myopic planner; true time-dependent optimal planning would need time as a state variable, an exogenous forecasting model, or another equivalent representation. Our project does not implement that additional predictive extension.

## The paper's running example

The continuous direct-route consumption is `3.36 + 2.45 + 0.84 + 0.35 = 7.0 kWh`, leaving `1.0 kWh` from a full 8 kWh battery; therefore the unmodified direct route is physically feasible in 7 min. Floored grid transitions instead follow `[8,4,1,0]`, which breaches the discrete positive-state rule. The text contains the erroneous expression `4 - 3.35 = 3.65` (intended `4 - 0.35`); the rounded segment rates yield 6.59 min charging where the exact charging duration from 2.04 to 6.00 kWh is 6.552 min. The illustrated charge to 6 kWh is not necessarily the optimum: in the six-arc sparse interpretation, the 4 kWh charging target gives 9.352 min versus 13.552 min for the illustrated action sequence. Distances from the lone station to other route nodes are missing; no optimum on an invented complete graph should be claimed.

## Complexity

The original stated time complexity is `O(|R| * |J_C| * Gamma * gamma)` with `O(|R| * Gamma)` memo storage. If each charging-time computation scans `omega` breakpoints, explicitly include an additional factor `omega` unless precomputed or regarded as constant. Real process memory also includes Python object overhead, recursion stacks, cache metadata and solver allocations; the storage bound refers to abstract tables, not resident memory measured by psutil.

## Experiment strengths

The use of the Montoya nonlinear-charging benchmark, heterogeneous charging rates, a MILP comparator, and sweeps in demand points, station count and discretization are valuable. Reporting both full-charge and partial-charge policies allows a useful performance comparison. EFRGen broadens the discussion to online traffic, and varying the number of city vehicles makes the simulation less artificial than a single static travel-speed case.

## Experiment limitations and threats to validity

The benchmark assigns synthetic unit loads because the source lacks the payload values needed by the proposed mass-dependent model. Critical values—vehicle empty mass, theta, exact Solomon-inspired tour construction and several simulator settings—are not sufficiently specified to reproduce identical route energies and decisions. The main MILP comparison relies on one named instance and varying tour prefixes rather than a distribution of optimum gaps across the entire benchmark. A 3-hour solver cutoff is not synonymous with proof of an optimum unless the solver reports a certificate. Despite discussion of frvcpy and the RemovalHeuristic, the paper lacks matched comparisons with them. Most performance claims lack uncertainty estimates and detailed per-seed data.

The tables also contain unit and arithmetic inconsistencies. Table 4a labels runtime as seconds while prose interprets the numerical values as milliseconds. Table 5b labels San Francisco route time as minutes while the prose calls it seconds, and the prose gives `617` where the table has `6017`. Published Table 2 gaps appear calculated with BEFRG route time as the denominator instead of the conventional MILP denominator, subject to rounded table entries. Text claiming that DPC generally draws more charge is inconsistent with seven of eight total-charge comparisons in Table 7a. Reported `under 2 MB` internal memoization memory is not equivalent to 100+ MB process RSS. Runtime comparisons must account for the different hardware and experiment parameters reported in different sections.

## Reproducibility verdict and significance

The static Bellman structure is independently implementable and testable against brute force and finite-state MILP, but the published full data-processing pipeline and online simulator are not specified well enough for exact numerical reconstruction. Thus this repository reports **partial algorithmic reproduction with synthetic inputs**, not a full original-benchmark replication. The paper remains useful because it provides a compact, forward-looking discrete charging algorithm and a testable hypothesis that finer grids improve solution quality, but 'optimal' must be interpreted within its deliberately restricted action set and battery-state discretization. The most defensible extension is physically executable SoC tracking with independent validation; a temperature/degradation penalty adds a meaningful but uncalibrated domain case.

**Primary reference:** Mandal et al. (2025), DOI `10.1145/3762188`. **Reproduction context and numerical artifacts:** `docs/reproducibility.md` and `results/`.
