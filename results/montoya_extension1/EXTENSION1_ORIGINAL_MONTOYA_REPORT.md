# BEFRG Extension 1 — original Montoya XML verification

> **Result type:** `[original-XML; independent-tour; our-model]`. This is a genuine Montoya benchmark input study, **not** a reproduction of Mandal et al.'s exact customer routes or calibrated vehicle parameters. No original Montoya XML is redistributed in this archive. The data here use the same independent cheapest-insertion tours and assumed 1,000 kg vehicle / nominal-rate-derived θ as the previous user's original-XML pilot.

## Executive result

The old floored-BEFRG run passes independent physical replay for **2/17** policies across the 5 Experiment A, 4 Experiment E, and 8 Experiment G configurations. Replacing floor-projected route-node battery states with physically continuous SoC labels while retaining finite charge-target actions yields **17/17 feasible policies**, all independently validated and certified finite-target-grid optimal under the stated Euclidean dominance theorem and numerical label resolution. The corrected objective is lower in all 17 comparisons, but **the original modeled times of invalid policies are not executable trip times**; therefore those percentage changes are mathematical model-objective comparisons, not field time savings.

Small independent continuous-charge MILPs agree with the corrected planner on the 6- and 10-customer configurations. An optimized dominance rule is also validated against the unpruned label algorithm for 10, 20 and 40-customer cases at γ=16 and all 38 stations. Thermal robustness runs on the original Montoya geometry use *uncalibrated illustrative* parameters and are not OEM battery validation.

## Experiment G — 40–320 original Montoya customers, γ=Γ=16

| Customers | Floored BEFRG model (min) | Corrected physical-SoC (min) | Modeled reduction | Old physically valid? | Corrected physically valid? |
|---:|---:|---:|---:|:---:|:---:|
| 40 | 579.41 | 471.83 | 18.57% | Yes | Yes |
| 80 | 1,159.60 | 950.15 | 18.06% | No | Yes |
| 120 | 1,703.27 | 1,389.33 | 18.43% | No | Yes |
| 160 | 2,367.12 | 1,938.73 | 18.10% | No | Yes |
| 200 | 2,797.07 | 2,312.75 | 17.32% | No | Yes |
| 240 | 3,390.12 | 2,817.66 | 16.89% | No | Yes |
| 280 | 3,988.54 | 3,248.84 | 18.55% | No | Yes |
| 320 | 4,636.69 | 3,719.68 | 19.78% | No | Yes |

At 320 customers, the corrected finite-target grid's route time is approximately **3,719.68 minutes**, against the floored model's **4,636.69 minutes**. The 19.78% difference is **relative to the old model's route-time output**, and cannot be interpreted as a physically realized fleet time saving when the old policy is infeasible. The new solver's run took roughly 2.48 seconds in this execution; do not generalize this runtime to all instances or all hardware.

## Experiment A — 50–150 customers, γ=Γ=40

| Customers | Floored DP (min) | Corrected (min) | Old valid? | Corrected valid? |
|---:|---:|---:|:---:|:---:|
| 50 | 529.90 | 497.21 | True | True |
| 70 | 701.47 | 638.31 | False | True |
| 90 | 1,043.92 | 961.24 | False | True |
| 100 | 1,134.56 | 1,046.63 | False | True |
| 150 | 1,711.84 | 1,549.93 | False | True |

## Experiment E — 320 customers, Γ=40 and varying γ

| Charging levels γ | Floored DP (min) | Corrected (min) | Old valid? | Corrected valid? |
|---:|---:|---:|:---:|:---:|
| 2 | 3,915.02 | 3,464.23 | False | True |
| 4 | 3,776.03 | 3,382.45 | False | True |
| 8 | 3,673.34 | 3,313.45 | False | True |
| 16 | 3,636.66 | 3,302.37 | False | True |

## Independent continuous MILP checks — original XML subcases

| Customers | Corrected finite-target (min) | Continuous-charge MILP (min) | MILP optimality certified? | Physical replay passed? |
|---:|---:|---:|:---:|:---:|
| 6 | 90.99 | 90.99 | True | True |
| 10 | 145.55 | 145.55 | True | True |

The 6/10 customer checks use **six selected stations** on the **tc2c320s38cf0** data, not the `tc1c320s38ct2` six-station cross-check used by the previous pilot. Thus their numerical values are **new**, and should not be confused with the original pilot's small 84.44/167.80 min checks.

## Euclidean SoC dominance: exactness and performance

At a given fixed-route node, a state A with more SoC and no higher accumulated objective than state B dominates B when (i) all direct edges exist and satisfy the triangle inequality, (ii) remaining energy demand is nonnegative and independent of battery history, (iii) charging costs are nonnegative, nondecreasing in charged energy, and time-independent, and (iv) the objective is additive. To reproduce any feasible low-SoC future action from the higher-SoC state: charge to the same target using no more charging time, or, when higher arrival SoC is already above that target, skip the station and use the no-longer-than-detour direct Euclidean arc. Therefore eliminating B cannot lose a better finite-target solution. The implementation *rejects* this option for arbitrary/sparse/directed distance overrides; it is **not** a universal dominance property of real directed road graphs. SoC keys are numerically rounded to 11 decimal places, consistent with the original Phase 3 solver's precision limits.

| Customers | Unpruned (sec) | Dominance (sec) | Same objective? | Corrected physically valid? |
|---:|---:|---:|:---:|:---:|
| 10 | 2.96 | 0.04 | Yes | True |
| 20 | 11.69 | 0.17 | Yes | True |
| 40 | 28.83 | 0.51 | Yes | True |

These are local wall times from one run, not stable hardware-independent speedup estimates. The dominance method is **an internal acceleration of Extension 1**, not a new third research extension. Any optional beam search is disabled; all reported corrected policies are grid-optimal within the model assumptions.

## Extension 2 — robustness on *original benchmark geometry*, NOT calibrated cells

At the same 40-customer original-XML tour, route time changes from 471.83 min at 25°C to 587.12 min at 0°C under the chosen quadratic usable-capacity derating and a hypothetical HVAC rate 0.04 kW/°C. At 80 customers it changes from 950.15 to 1,154.07 min. Doubling the *assumed* cold coefficient increases the 40-customer result to 878.31 min, underscoring that the response depends strongly on uncalibrated parameters. A charging-throughput equivalent-minute penalty was included in a separate cold scenario; it is **not measured electrochemical aging**, and it must not be added to driving time as if it were physical charging duration.

The U.S. DOE/Argonne 2024 impact report supports the qualitative relevance of ambient temperature, cell performance and HVAC load; it does **not** calibrate this model for the Montoya vehicle, determine `alpha_cold`, or validate its battery chemistry: https://www.energy.gov/cmei/vehicles/articles/program-record-impact-cold-ambient-temperature-and-extreme-conditions . For measured deployment, obtain vehicle-specific temperature-vs-usable-capacity tests, charger-power-vs-SoC-vs-temperature maps, HVAC duty cycles, charging availability and original-route road grades.

## Cross-machine numerical reproducibility (original floored baseline)

The user's local Ubuntu run matches the earlier environment on **36/36** stored objective metrics within 1e-6 minute, across Experiments A, E, F, G and small MILP checks. This is separate from the new Extension 1 validation, which was executed in the current environment only. Repeating the new runner on the user's laptop is recommended before claiming cross-machine validation of the corrected implementation. `cross_machine_objectives.csv` and `old_baseline_regression_checks.csv` contain the complete reconciliation.

## Configuration, limitations and reproducibility

- **Inputs:** Actual Montoya VRP-REP XML, checksums in `methodology.json`. Source archive must be downloaded separately, not redistributed with this code.
- **Tour:** One independently constructed deterministic cheapest-insertion tour for the full 320 customers, using prefixes for smaller runs; the authors' exact tour is unknown.
- **Calibration:** Customer deliveries assumed 1 kg each; 1,000 kg empty mass; θ chosen so empty consumption equals the original XML nominal kWh/km. This was the original pilot's assumption, not a recovered paper value.
- **Charging:** Original nonlinear station profiles from XML; finite target grid γ; at most one station per original route arc; all 38 stations unless explicitly reported as 6 in the small continuous MILP checks.
- **Guarantees:** Physical-SoC solver is optimal within the finite-target, Euclidean-metric action model (up to 11-decimal SoC merge tolerance) **without beam pruning**; continuous charging optimum is only provided by separately certified MILP on 6/10 customer cases.
- **Feasibility:** Independent continuous replay validates positivity at fixed-route nodes, monotone station charging, charger limits, and objective accounting. It does not model queue waiting, traffic, hills, charging losses or a safety energy reserve.
- **Comparability:** Paper's numerical Table 2/6/7 values **cannot** be directly attributed to algorithmic differences because their routes/vehicle calibration are not matched. The new results demonstrate reproduced benchmark-input behavior, not exact numerical reproduction of Mandal et al.'s results.
- **Timing:** Local wall time depends on CPU, Python and dependency versions; route construction is excluded. Absent original SUMO data and authors' CPLEX environment, no fair paper-to-ours speed claim exists.

### Re-run

```bash
python -m pip install -e '.[test]'
# Place your externally downloaded XMLs in data/raw/montoya/
python -m pytest -q
python -m experiments.montoya_extension_validation --suite all --output results/my_extension_validation
python -m experiments.montoya_extension_validation --suite G --output results/my_extension_validation
```

The first command may take longer for γ=40 cases or small MILP solves; a single run avoids overwriting saved results by choosing its own output directory. The report is deterministic in objective values but not necessarily runtime measurements.

### Traceability

- Source code: `befrg/physical.py` (`dominance_pruning=True`), `experiments/montoya_extension_validation.py` and `tests/test_montoya_extension.py`.
- Saved evidence: `results/montoya_extension1/extension1_{a,e,g}_original_xml.csv`, `small_milp_crosschecks.csv`, `thermal_robustness_original_xml.csv`, `dominance_ablation.csv`, `cross_machine_objectives.csv`.
- Existing baseline and local-run evaluation: `results/montoya_pilot/`, `cross_machine_objectives.csv`.
- Exact model derivation: `docs/phase3_math_review.md` plus additional Euclidean dominance argument above.
