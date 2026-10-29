# Phase 3 research extension report — two extensions only

**Provenance:** All results here are [ours-scaled-down], executed on deterministic synthetic 2D route data; no Montoya datasets, real battery-cell calibration, or traffic traces were used. Original paper: Mandal et al. (2025), https://doi.org/10.1145/3762188. The code is independently implemented.

## What was implemented

1. `befrg/physical.py` — a forward exact-physical-SoC label DP. The battery energy is never floored in transitions, and station targets must exceed physical arrival SoC. Among equal physical SoC states only, the cheapest label is retained. Without beam pruning, globally optimal over the specified discrete charging target set; NOT over continuous possible charging targets. `validate_physical_result` is a separate continuous replay.
2. `befrg/thermal.py` — bounded and asymmetric synthetic capacity derating, additional HVAC energy proportional to travel duration, station curves scaled to usable capacity, and charging-throughput penalty in minute-equivalents. Temperature/health are constant route parameters; the penalty does not model a physically measured electrochemical lifetime reduction. Details: `docs/phase3_math_review.md`.

## Core correctness check — paper's sparse example [ours-scaled-down]

| Calculation | Route time |
|---|---:|
| Our faithful floored-state DP | 9.352 min |
| Our physical-SoC grid DP | 7.000 min |
| Our separately formulated continuous MILP | 7.000 min, certified optimal |

The paper's figure does not specify a complete station road network; these figures apply only to its six explicitly specified directed arcs. The physical-grid solver chooses the direct route, ending with 1.0 kWh, rather than the unnecessary floor-driven detour.

## Grid sensitivity, 48 measured configurations [ours-scaled-down]

Data: `results/phase3/grid_comparison.csv`; three seeded synthetic problems, 5 customers, 3 stations, θ=0.00033 kWh/(km kg), Γ={4,8,16,32}, γ={2,4,8,16}. Each seed uses the same MILP continuous optimal reference for all discretizations.

| Γ | Mean BEFRG floored-state gap vs certified continuous MILP |
|---:|---:|
| 4 | 118.889% |
| 8 | 71.809% |
| 16 | 38.161% |
| 32 | 27.294% |

| γ | Mean physical-SoC grid gap vs certified continuous MILP |
|---:|---:|
| 2 | 21.669% |
| 4 | 18.133% |
| 8 | 5.393% |
| 16 | 3.084% |

All 48 grid search policies passed independent physical replay, and all 48 matching MILP reference entries were certified optimal (3 separate MILP solves, reused for the 48 configurations). The corrected grid gap ranged from 1.017% to 38.720% and remained nonzero because the charge target set is still finite. Note that Γ does not affect physical-label decisions; the label method has higher worst-case state cost than BEFRG's bounded Γ-table.

## Temperature response [ours-scaled-down]

Synthetic 7-customer, 4-station route with B0=16 kWh, θ=0.00018; degree coefficients and HVAC rates from `configs/phase3.yaml`, degradation weight 8 equivalent minutes, β=1.4.

| Ambient (°C) | Usable B (kWh) | HVAC (kW) | Actual route time (min) | Degradation proxy (min-equivalent) | Optimization objective (min-equivalent) | Detours |
|---:|---:|---:|---:|---:|---:|---:|
| -10 | 7.180 | 4.64 | 328.457 | 22.301 | 350.757 | 5 |
| 0 | 11.500 | 3.04 | 141.598 | 4.601 | 146.198 | 1 |
| 10 | 14.380 | 1.44 | 118.914 | 0.899 | 119.814 | 1 |
| 25 | 16.000 | 0.00 | 107.318 | 0.000 | 107.318 | 0 |
| 35 | 15.808 | 0.96 | 107.318 | 0.000 | 107.318 | 0 |
| 45 | 15.232 | 2.16 | 119.487 | 0.979 | 120.466 | 1 |

All 30 thermal/ablation runs passed independent replay. The coldest synthetic temperature produces a strong increase in charging stops, mostly due to modeled reduction in usable capacity plus HVAC energy; this is NOT a prediction for any actual EV model.

## Ablation at T=0°C (synthetic)

| Scenario | Route time (min) | Degradation penalty (min-equivalent) |
|---|---:|---:|
| full | 141.598 | 4.601 |
| hvac_only | 120.563 | 0.000 |
| capacity_only | 120.015 | 0.000 |
| degradation_only | 107.318 | 0.000 |
| no_extension | 107.318 | 0.000 |

## Degradation weight sensitivity at -10 °C (synthetic)

| Weight (min-equivalent) | Route time (min) | Penalty (min-equivalent) | Total objective (min-equivalent) |
|---:|---:|---:|---:|
| 0 | 328.457 | 0.000 | 328.457 |
| 2 | 328.457 | 5.575 | 334.032 |
| 8 | 328.457 | 22.301 | 350.757 |
| 20 | 328.774 | 55.140 | 383.914 |
| 50 | 328.774 | 137.850 | 466.624 |

Sensitivity CSV also varies Γ, γ, θ, nominal battery B, station number, and fast/normal/slow charging types; all 23 runs passed independent replay. Objective values cannot be compared across temperatures as measured degradation without empirical coefficient calibration.

## Findings and limits

- **Supported on tested cases:** physically executable finite-grid policies; independent MILP lower bounds; reduced conservative rounding artifacts; HVAC and thermal-capacity changes affect selected charging stops and route time.
- **Not established:** full continuous charging optimality, chemical aging reduction, real-world battery temperature response, depot capacity fade during multi-year operation, traffic-dependent routing, results on 120 Montoya benchmark instances.
- **Potential structural defect:** for β > 1 the surrogate may incentivize split-charge events even when electrochemical lifetime would not improve. A truly path-dependent DoD/rainflow stress model would need more state history.
- **Execution timing:** wall-clock seconds vary with machine load; CSV includes measured wall time but does not claim hardware-matched BEFRG performance.
- **Phase boundary:** no Phase 4 experiments were implemented.

## Re-run commands

```bash
python -m pip install -e '.[test]'
python -m pytest
python -m scripts.phase3_demo
python -m experiments.phase3
python -m experiments.phase3 --quick
```

Figures `gap_vs_Gamma.png`, `physical_runtime_vs_Gamma.png`, `temperature_effects.png`, `thermal_ablation.png`, and `degradation_sensitivity.png` were created from those CSVs.
