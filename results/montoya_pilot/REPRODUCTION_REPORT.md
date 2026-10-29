# Original Montoya XML: independent BEFRG reproduction pilot
**Status:** 120/120 source XML instances successfully parsed and ZIP CRC verified; **two original 320-customer/38-station instances** used for executed experiments A, E, G, F. This is **not a numerical reproduction of Mandal et al. (2025) at an identical customer tour or energy calibration**. All results are labelled **[original-XML; independent-tour]**.
The complete uploaded archive has SHA256 `bbe7e924ad79670f12657cd0bed096ce396d157405363029cd422e8894ec64c8`. The `dataset_xml_manifest.csv` stores SHA256 and per-instance metadata for **all 120 XMLs**; only two specified instances were used in the actual algorithmic experiment sweeps.

## Reproduction-versus-comparability status
| Component | Paper-aligned | Outstanding difference |
|---|---|---|
| Dataset XML | **Yes** | Original Montoya 2017 VRP-REP files (320 customers / 38 stations) |
| Battery / speed / charge profile | **Yes** | B = 16 kWh, S = 40 km/h; station charging curves from XML |
| Customer load | **Yes (unit loads)** | Set to 1 kg for each customer following paper description |
| Tour construction | **No** | Our cheapest-insertion route differs from paper’s incompletely specified Solomon-inspired tour. We first build all 320 customers then use prefixes. |
| Mass/energy model | **Partially** | Assumed empty mass = 1,000 kg and θ=0.125/1000 kWh/(km·kg). Published values for those two parameters are not recoverable from paper. |
| MILP | **Only small original-input subcases** | Original Table 2 50–150-customer CPLEX model not rerun. Both independent SciPy HiGHS models certified on 6/10-customer subcases. |
| Execution environment | **No** | Python / SciPy / CPU differ; wall time excludes route construction, solver compilation and memory profiling. |
| Physical validity | **Explicitly checked** | Some floored-state DP-optimal charge policies fail continuous SoC replay; don’t present as physically executable. |

## Experiment A — BEFRG modeled route time (Table 2)
Same **input XML instance** `tc1c320s38ct2.xml`, 38 original stations, γ=40, Γ=40; 50/70/90/100/150 prefixes of our independent tour. The paper’s `|R|` interpretation may also differ by depot counting.
| Customers | Paper BEFRG (h) | Ours (h) | Physical replay |
|---:|---:|---:|---|
| 50 | 6.64 | 8.83 | PASS |
| 70 | 9.87 | 11.69 | FAIL |
| 90 | 13.89 | 17.40 | FAIL |
| 100 | 15.74 | 18.91 | FAIL |
| 150 | 23.49 | 28.53 | FAIL |

We do **not** compute a numerical reproduction gap between these columns: tour and mass-dependent energy are not matched. The paper’s Table 2 continuous MILP optimality gaps require a large MILP solve and matched route. The original user request for exact Table 2 values is **not yet complete**.

### Independent DP/MILP cross-check (original XML subset; NOT Table 2)
| Customers | Stations | γ / Γ | BEFRG DP (min) | Discrete MILP (min) | Continuous MILP (min) | Certified | Physical replay |
|---:|---:|---|---:|---:|---:|---|---|
| 6 | 6 | 8/12 | 84.443 | 84.443 | 84.443 | both yes | True |
| 10 | 6 | 8/12 | 167.797 | 167.797 | 155.329 | both yes | True |

With 10 customers, the finite-state DP equals the independent **discrete MILP** to solver tolerance, while the **continuous MILP** is 8.03% lower using the conventional continuous-MILP denominator. This is evidence of the model’s battery-state discretization cost, **not** the paper’s Table 2 gap. Both small DP policies passed physical replay.

## Experiment E — charging resolution (Table 6a)
Same original XML, full 320-customer independent tour, 38 stations, Γ=40, γ varied.
| γ | Paper (h) | Ours (h) | Our detours | Physical replay |
|---:|---:|---:|---:|---|
| 2 | 84.17 | 65.25 | 36 | FAIL |
| 4 | 80.62 | 62.93 | 36 | FAIL |
| 8 | 78.48 | 61.22 | 33 | FAIL |
| 16 | 77.75 | 60.61 | 33 | FAIL |

Increasing γ lowers the discrete-model route time in both series. Every one of our four policies fails independent physical validation (non-increasing charge targets at actual arrival SoC), so the route times cannot be advertised as executable schedules.

## Experiment G — full charging vs discrete partial charging (Table 7a)
Same original XML `tc2c320s38cf0.xml`; 38 original stations; γ=Γ=16; fixed route shared within each FC–DPC comparison.
| Customers | Paper FC (min) | Paper DPC (min) | Our FC (min) | Our DPC (min) | Our DPC improvement | Our DPC physically valid? |
|---:|---:|---:|---:|---:|---:|---|
| 40 | 455 | 415 | 627.69 | 579.41 | 7.69% | True |
| 80 | 968 | 878 | 1,330.04 | 1,159.60 | 12.81% | False |
| 120 | 1442 | 1306 | 1,894.60 | 1,703.27 | 10.10% | False |
| 160 | 2028 | 1875 | 2,610.39 | 2,367.12 | 9.32% | False |
| 200 | 2623 | 2377 | 3,097.12 | 2,797.07 | 9.69% | False |
| 240 | 3343 | 2982 | 3,722.70 | 3,390.12 | 8.93% | False |
| 280 | 4111 | 3687 | 4,423.45 | 3,988.54 | 9.83% | False |
| 320 | 5132 | 4602 | 5,130.45 | 4,636.69 | 9.62% | False |

At 320 customers, our FC = **5,130.45 minutes** and our DPC = **4,636.69 minutes** (paper: 5,132 and 4,602 minutes). Though the magnitudes are similar, numerical closeness does not establish replication with different tours. Our FC physically validates on all eight prefixes, while DPC validates only at 40 customers; **seven DPC policies failed continuous SoC replay**. Thus the 9.62% DPC gain is a gain in the **floored discretized objective**, not in validated real-drive time.

## Experiment F — scalability pilot (not Table 6b)
| Customers | Wall time (s) | Model RT (min) | Physically valid |
|---:|---:|---:|---|
| 40 | 0.307 | 579.41 | True |
| 80 | 0.578 | 1,159.60 | False |
| 160 | 0.927 | 2,367.12 | False |
| 240 | 1.457 | 3,390.12 | False |
| 320 | 1.811 | 4,636.69 | False |

Our largest **original single-instance** run has 320 customers. The paper’s 640–1600-node experiments combine routes beyond the size of one original XML. Their route-assembly method and runtime hardware are not matched; no claims of replicated 5–19-second timings are warranted.

## Execution and how to reproduce these numbers
1. Extract the user-provided `montoya-et-al-2017.zip` into the repository’s `data/raw/montoya/` folder (the XMLs are **not** repackaged in the repository). Check there are 120 XMLs.
2. `python -m pip install -e '.[test]'` from repository root, then `python -m pytest -q`.
3. To generate a specific suite without overwriting any Phase 2–4 outputs, run the following in the repository root:

```bash
python -m experiments.benchmark_montoya --suite A
python -m experiments.benchmark_montoya --suite E
python -m experiments.benchmark_montoya --suite G
python -m experiments.benchmark_montoya --suite F
python -m experiments.benchmark_montoya --suite milp-small
```

All write to `results/montoya_pilot/` by default. For a long combined run use `--suite all`; it may take longer. The result rows include exact model times, physical replay status, customer counts, source dataset names, wall/CPU seconds and errors. `methodology.json` records SHA256 for each input XML and assumptions. Charts plot published and our quantities as **separate, non-matched series**. Never interpret their vertical difference as an approximation error or optimality gap.

### Next scientific steps if exact replication is required

- Reconstruct or obtain the paper’s exact Solomon-inspired initial tour node order for the same input file and `|R|` counting.
- Obtain/document the exact `veh_mass` and `theta` in the mass-dependent equation. Without these values, the dataset’s original 125 Wh/km baseline alone does not uniquely specify the paper’s consumption model.
- On identical fixed tours and settings, run an independently certified MILP comparator for Table 2’s 50–150 customer sizes with a sufficiently generous time/memory limit and report solver termination certificates (not just incumbents).
- If possible, obtain the original online SUMO settings for H and the route concatenation procedure for F above 320 customers.
- For any claimed practical charging policy, require positive physical SoC and `charge_target > actual_arrival_soc` at every station. The Phase 3 physical-label solver is a candidate correction; re-running it on all 320 customers requires additional scaling validation and has not been done in this pilot.

**Paper reference:** Mandal, Sarkar & Mondal, ACM TECS 2025, DOI: https://doi.org/10.1145/3762188. **Dataset:** Montoya et al. VRP-REP 2017, https://www.vrp-rep.org/datasets/item/2016-0020.html.
