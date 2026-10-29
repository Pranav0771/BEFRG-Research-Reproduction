# Phase 2 — Experimental reproduction report

**Paper:** D. Mandal, A. Sarkar and A. Mondal, *A Discrete Partial Charging Enabled Dynamic Programming Strategy for Optimal Fixed-Route Electric Vehicle Charging*, ACM TECS 24(5s), article 154 (September 2025). https://doi.org/10.1145/3762188

**Scope:** Experiment runners A–H, independent solver checks, measurements, plots, and paper-reference comparisons. No Phase 3 enhancements are claimed.

## Research-integrity statement

The original **120 Montoya XML instances**, the authors' exact initial tours and load/mass calibration, the **CRAWDAD SF taxi traces**, and the authors' **SUMO/TraCI simulator setup** were **not available** in this execution environment. Direct downloading of the Montoya archive failed because container networking/DNS was unavailable. Accordingly, **all A–G numerical sweeps used deterministic synthetic surrogate instances**, and H used an explicitly documented lightweight synthetic hourly-traffic **SUBSTITUTE**. Every measured CSV has `[ours-scaled-down]` provenance. The `paper_running_example_six_arcs` case uses values supplied in the article and is a sparse-arc interpretation, not the unknown complete graph. No numerical paper value is labeled reproduced.

For integrity, the `exp_*_paper_vs_ours.csv` files preserve [paper] values but leave paired absolute and relative differences empty: different instances, routes and energy calibrations make such differences mathematically calculable but scientifically **not meaningful**. Within-instance **our DP versus our MILP** differences and gaps are computed in `exp_a.csv`. Qualitative trend comparisons are reported separately; they are not exact numerical replications.

### Equipment, timing and reproducibility

The Python environment was 3.13.5, Linux x86_64, 5 logical CPUs visible, approximately 5.81 GiB of available system RAM, NumPy 2.3.5 and SciPy 1.17.0 (see `results/phase2_summary.json` for the recorded environment). `time.perf_counter()` measures end-to-end DP execution with `tracemalloc` instrumentation (not a clean microbenchmark); `psutil` measures process CPU time and current RSS, `resource.ru_maxrss` is the *historical process peak* and cannot be interpreted as an individual run's peak, and `tracemalloc` is a Python-allocation peak rather than overall process memory. All numeric comparisons should account for hardware, interpreter overhead, memory instrumentation, and different workloads.

Synthetic inputs use seed **20251028**, battery capacity 16 kWh, speed 40 km/h, 1000-kg empty mass, and unit customer demands; the **surrogate consumption rate is intentionally doubled** to 0.25 kWh/km empty versus the benchmark's 0.125 kWh/km base to create informative charging stress. This is an OUR experimental assumption and **does not correspond to recovered parameters from Mandal et al.** Station curves are the published fast/normal/slow profiles. Customer route order is deterministic cheapest-insertion (not exactly the author's unspecified Solomon variant); instances are prefix-stable within a sweep. For A, `gamma=4` and `Gamma=4,8,16,32` on small examples; other grid values are in `configs/phase2.yaml`.

## Summary of executed results (synthetic surrogate unless stated)

| Exp. | [paper] reference | [ours-scaled-down] executed result | Evidence and verdict |
|---|---|---|---|
| A | Table 2 / Fig. 4: MILP comparison at 50–150 route nodes and smaller gap for finer Gamma | **17 of 17** DP values exactly matched independent binary state-flow MILP (within 1e-6). In sparse running example DP=9.352 min, discrete MILP=9.352 min, continuous MILP=7.000 min, gap 33.6% (conventional denominator). On synthetic prefixes, gap decreases with Gamma. | **Partially reproduced**: correctness of surrogate finite-state DP, direction of resolution effect. Published MILP experiment **could not test**. |
| B | Table 4a: nonmemoized computation grows exponentially; memoir ET units are internally contradictory | No-memo call counts 1,917 at 3 customers and 15,170 at 4; for 5–7 customers, bounded at 100,000 recursive calls. Memoized solves all. Completed nonmemo values equal DP. | **Partially reproduced** (trend, not paper runtimes). Timeout-budget rows are **censored**, not successful times. |
| C | Table 4b: 15–50 route nodes, RT 137–531 min | 8–16 customers: model RT **102.6296 → 187.9667 min**, 1–2 detours; routes passed physical validation. | **Partially reproduced** (upward trend on surrogate). |
| D | Table 5a: with 15–35 stations, RT 5761 → 4692 min | Nested station subsets of 2–8: RT **303.8202 → 265.1782 min**; adding candidate stations does not worsen optimum. | **Partially reproduced** (trend; paper's uniformly sampled sets differ). |
| E | Table 6a: gamma 2,4,8,16 at Gamma 40, RT 84.17 → 77.75 hr | At Gamma 24, gamma 2,4,8,16: **267.5642 → 248.3563 min**; decreasing objective, nondecreasing candidate set. | **Partially reproduced** (trend, not paper values). |
| F | Table 6b: route nodes 320–1600 in 5–19 sec; 120 originals in 47 sec | Synthetic **20–320 customers**, wall time **0.2074 → 5.8530 sec** (DP only, includes instrumentation); 320-run objective 2141.7498 min and 34 detours. Original 120 and 1600 extended-node runs **not run**. | **Partially reproduced** (scaling on a different workload). |
| G | Table 7a: DPC route time better than FC, more DP work | 6–28 customers: DPC model RT <= FC for all. At 28: FC **322.9601** vs DPC **302.1521 min**, but this DPC charging policy is **NOT physically executable as prescribed**. | **Partially reproduced** for discrete model comparison; physical validity fails in 3/6 DPC runs. |
| H | Tables 5b / 7b: SF traces and Amsterdam SUMO, nonlinear congestion effects | Normal-flow hourly speed **SUBSTITUTE**, vehicles 500–3000: at 3000, realized static **303.2213** versus snapshot-replanned **289.6952 min**; actual SUMO/TraCI was **not run**. | **Could not test** paper H; substitute illustrates replanning only. |

### Important discrepant physical feasibility finding

Three synthetic DPC plans in G (18, 22, 28 customers) return valid *discretized* costs but the independently replayed continuous vehicle reaches station `c4` **above** the target 4.000 kWh. The verifier reports physical SoC at station as 4.355942, 5.120660 and 5.055801 kWh respectively. A literal instruction to charge to 4.000 kWh would decrease energy, violating the paper's strictly-increasing charging rule. We have **not** retroactively repaired those policies; the CSV rows are explicitly flagged false, with error text. This highlights an execution mismatch caused by using floored arrival SoC to select a target level. In Phase 3 we can test a corrected conservative policy or adaptive refinement.

DPC <= FC is guaranteed for the static **discretized objective** when charging-level choices for DPC contain the FC choice. This does not certify that all DPC policies execute physically or that their actual realized times are smaller.

### MILP models and exactness conditions

- **Discrete binary-flow MILP:** One unit of flow chooses one transition between `(k,b)` states in the acyclic route×SoC graph. Actions, floor rounding, positive discrete states, station arrival and nonlinear CT follow independent code in `experiments/milp.py` (not imports from solver transitions). It should equal top-down and bottom-up BEFRG on the same input. Tested on the paper example, 16 synthetic combinations, plus randomized unit tests.
- **Continuous-SoC MILP:** Each original arc chooses direct travel or one station. Continuous battery conservation is enforced via indicator-style big-M conditional equalities. The cumulative piecewise charging-time curve is represented **exactly** by a one-hot breakpoint segment plus a fractional occupancy variable for **both arrival and departure SoC**; objective includes their cumulative-time difference. This avoids invalid epigraph-only treatment of the negative arrival charging-time term. This model still imposes one station per arc, no queues, zero delivery service durations and small positive residual SoC tolerance. HiGHS/SciPy's termination status and MIP gap are retained by the `MilpResult` object; results are called certified only on status 0. This is **our independent** continuous MILP interpretation, not a claim to have recreated the unpublished CPLEX formulation exactly.
- Running example has B=8 kWh, and the direct 14-km total route energy is 7 kWh. The continuous MILP finds the no-detour 7-minute solution; the discretized DP gives 9.352 minutes with a 4-kWh station target, not the paper's illustrative charge-to-6 route. The 33.6% within-instance OG uses `(RT_DP-RT_MILP)/RT_MILP`.

### Baseline comparisons and statistical limitations

The no-memo enumerator explicitly stops at 100,000 calls. Results at the limit cannot be interpreted as measured time to optimality. Repetitions are set to 1 for scaled runs; the paper's 100-run averages and inter-run variance were not reproduced. No CPLEX, frvcpy, RemovalHeuristic, full Montoya reference tours or real stochastic SUMO traces were available. Hardware is not matched to the paper's dual-Xeon server or laptop. No original source instance has been tested in this phase. One case of actual physical feasibility failure is captured in the regression suite rather than omitted.

### Verdict: strict versus trend-level

The `results/tables/phase2_verdicts.csv` table uses **Partially reproduced** strictly for trends and internally verified methods on new synthetic data. **None** of A–H qualifies as an *exact numerical reproduction of the paper*. Published table values, specific hardware runtimes and trace-derived metrics remain **Could not test**. The phrase **Reproduced** should be reserved for experiments with source XML, identical routes and energy parameters, certified optimization status and matching metrics within explicitly justified tolerances.

## Remaining manual inputs for a proper reproduction

1. Download the 120-instance VRP-REP Montoya archive: https://www.vrp-rep.org/datasets/item/2016-0020.html . Extract XML into `data/raw/montoya/`.
2. Obtain the CRAWDAD EPFL/mobility San Francisco taxi GPS data: https://doi.org/10.15783/C7J010 . Place archive into `data/raw/crawdad/`.
3. For SUMO, install it and TraCI locally; extract appropriate OSM networks and configure `.sumocfg` plus charging-station edges. The provided controller is a **skeleton only** and does not actuate charging decisions yet.
4. Obtain source route order, `theta`, `veh_mass`, generator seed/sampling details and CPLEX formulation from authors, where possible. Without these, same-instance benchmarking is not guaranteed to replicate the article.

## Generated evidence

- `results/tables/exp_{a,b,c,d,e,f,g}.csv` — raw measurements, mode and provenance.
- `results/tables/exp_h_substitute.csv` — simulated traffic surrogate.
- `results/tables/exp_*_paper_vs_ours.csv` — paper reference rows, no invalid cross-instance numeric differences.
- `results/tables/phase2_verdicts.csv` — qualitative verdict table.
- `results/phase2_summary.json` — machine/environment, checks, important numerical summaries and limitations.
- `results/figures/*.png` — Matplotlib charts generated from our executed result tables, **never paper figures**.
- `tests/test_phase2.py` — independent solver checks, deterministic traffic and continuous feasibility counterexample.

**All experiments in this report are static and traffic Phase 2 tasks. Extensions for Phase 3 have not been implemented.**
