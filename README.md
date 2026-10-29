# BEFRG: Independent Reproduction and Extensions

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Tests](https://img.shields.io/badge/local%20tests-63%20passed-brightgreen) ![Status](https://img.shields.io/badge/benchmark-original%20XML%20%2B%20synthetic-orange)

**Independent implementation of** Mandal, Sarkar & Mondal (2025), *A Discrete Partial Charging Enabled Dynamic Programming Strategy for Optimal Fixed-Route Electric Vehicle Charging*, ACM TECS 24(5s), Article 154. DOI: https://doi.org/10.1145/3762188.

> **Reproduction status:** Saved evidence includes `[ours-scaled-down]` synthetic experiments and `[original-XML; independent-tour]` Montoya-input experiments, alongside separate `[paper]` references. Exact numerical reproduction of the original 120-instance published tables and original SUMO/CRAWDAD simulation was **not achieved**. Matching trends on synthetic data must not be called a full reproduction. Full explanations: [Reproducibility](docs/reproducibility.md), [Review](docs/paper_review.md), [Assumptions](docs/assumptions.md).

## Abstract

The fixed-route EV charging problem asks where to insert charging detours and what battery charge target to use while preserving an already chosen customer sequence. This repository independently implements BEFRG's finite-state dynamic programming algorithm and compares its modeled outcomes against exhaustive enumeration and discrete/continuous mixed-integer programming. It documents the limits of residual-charge flooring and implements two user-selected research extensions: (1) continuous physical SoC tracking with discrete charge targets and independent route validation, and (2) bounded temperature-dependent battery capacity, HVAC consumption, and a synthetic charging-throughput degradation penalty. Four further synthetic use cases study Indian last-mile delivery, regional coaches, heavy freight, and charger outage/density. All numbers are from executed Python experiments; original-XML experiments use independent customer tours and synthetic vehicle calibration, not calibrated vehicle field measurements.

## Results at a glance

| Claim / experiment | [paper] reference | [ours-scaled-down] executed evidence | Reproduction status |
|---|---|---|---|
| A: BEFRG vs MILP | Reported 8–15% gap at Γ=40 on selected Montoya prefixes | Synthetic 17/17 discrete MILP matches; original-XML prefix runs and certified small-instance MILP checks | Original XML used but paper tour unmatched |
| B: memoization | Exponential no-memo growth | Recursion hit defined 100,000-call cap in small synthetic cases | Partial trend |
| C: route size | Table 4b RT 137–531 min | 102.63–187.97 min on other synthetic routes | Partial trend, not comparable magnitude |
| D: station count | Table 5a RT 5761→4692 min | 303.82→265.18 min on other synthetic routes | Partial trend |
| E: charge level γ | Table 6a RT 84.17→77.75 h | 267.56→248.36 min on different model | Partial trend |
| F: scalability | 5–19 sec for 320–1600 nodes, 47 sec for 120 instances | 0.207→5.853 sec for 20–320 synthetic customers | Partial scale test |
| G: FC vs DPC | Table 7a at 320 nodes: 5132 vs 4602 min | Lower modeled DPC cost; some baseline actions failed physical replay | Partial with validation caveat |
| H: traffic | EFRGen on SF and Amsterdam | Hourly-speed substitute only, not SUMO | Could not reproduce original experiment |

The above is a **cross-dataset summary**, not a numerical gap analysis. For per-experiment CSVs and explicit N/A numeric differences, see [`results/tables/phase2_paper_ours_overview.csv`](results/tables/phase2_paper_ours_overview.csv). Configuration, run provenance and plots are committed under [`results/`](results/).

## Installation / quickstart

Python 3.10+ (CPU only) and pip are required; no IBM CPLEX is needed. HiGHS is available via SciPy. On Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
python -m pytest -q
python -m scripts.run_example
python -m scripts.phase3_demo
python -m scripts.verify_results --check-hashes
```

On Windows, activate with `.venv\Scripts\activate` and use `python` commands. To run the Jupyter notebooks: `python -m pip install -e '.[notebook]'` and `jupyter lab`.

## One-command reproduction recipes

**By default, Phase 2 uses deterministic synthetic surrogates.** `--quick` reduces workload; Phase 4 `--quick` uses a heuristic beam and cannot certify grid optimality.

| Target | Command | Outputs |
|---|---|---|
| Tests | `python -m pytest -q` | Local pass/fail |
| Paper Fig. 2 running example | `python -m scripts.run_example` | Policy and SoC trace |
| A / Fig. 4: grid–MILP | `python -m experiments.exp_a` | `results/tables/exp_a.csv`, `results/figures/exp_a_gap.png` |
| B / Table 4a: memoization | `python -m experiments.exp_b` | `results/tables/exp_b.csv`, `results/figures/exp_b_memoization.png` |
| C / Table 4b: route size | `python -m experiments.exp_c` | `results/tables/exp_c.csv`, `results/figures/exp_c_route_time.png` |
| D / Table 5a: stations | `python -m experiments.exp_d` | `results/tables/exp_d.csv`, `results/figures/exp_d_stations.png` |
| E / Table 6a: γ | `python -m experiments.exp_e` | `results/tables/exp_e.csv`, `results/figures/exp_e_charge_levels.png` |
| F / Table 6b: scale | `python -m experiments.exp_f` | `results/tables/exp_f.csv`, `results/figures/exp_f_scaling.png` |
| G / Table 7a: FC vs DPC | `python -m experiments.exp_g` | `results/tables/exp_g.csv`, `results/figures/exp_g_fc_dpc.png` |
| H / Tables 5b,7b **substitute** | `python -m experiments.exp_h` | `results/tables/exp_h_substitute.csv`, `results/figures/exp_h_traffic.png` |
| All Phase 2 synthetic | `python -m experiments.run_all` | `results/tables/`, `results/figures/` |
| Rebuild Phase 2 summary | `python -m experiments.summarize && python -m experiments.overview` | Verdicts and comparison overview |
| Extension 1 + 2 | `python -m experiments.phase3` | `results/phase3/*.csv`, `*.png` |
| New use cases | `python -m experiments.phase4` | `results/phase4/*.csv`, `*.json`, `*.png` |
| Montoya Extension 1 audit | `python -m experiments.montoya_extension_validation --suite all` | `results/montoya_extension1/` (external XML needed) |
| Fast verification smoke | `bash run_all.sh smoke` | Tests, running example and committed-result checksums |
| Regenerate quick experiment subsets | `bash run_all.sh quick` | Separate outputs under `results/recomputed_quick` etc.; may still be time-consuming |
| Rebuild all synthetic experiments | `bash run_all.sh full-synthetic` | Overwrites the corresponding checked-in results (runtime varies) |

Run any experiment with `--help` for additional flags. To avoid touching the committed outputs, supply `--output results/your_run`. `make help` lists Makefile targets, e.g. `make exp-a` and `make phase4`.

## Original dataset download (manual)

- **Montoya nonlinear EVRP benchmark:** https://www.vrp-rep.org/datasets/item/2016-0020.html — extract VRP-REP XML files into `data/raw/montoya/`. To use original XML, run `python -m experiments.exp_a --full` or `python -m experiments.exp_f --full`. `--full` requires the source files and does **not** silently substitute synthetic input. The original Solomon-like initial tour and paper's calibration remain not fully known, so even a successful `--full` run is not automatically a reproduced paper value.
- **San Francisco CRAWDAD traces:** https://doi.org/10.15783/C7J010 — save in `data/raw/crawdad/`. Historical traffic replay requires a separately configured SUMO/OSM environment; the included `simulators/traci_controller.py` is only a skeleton.
- **OpenStreetMap:** https://www.openstreetmap.org/ — place local network extracts under `data/raw/osm/` for custom simulation.

No downloaded benchmark/traces are distributed in the repository, although executed original-XML summary CSVs are included. See [`data/README.md`](data/README.md).

## Algorithm and research contribution map

| Original paper's contribution | Independent work in this repository |
|---|---|
| FRVCP-DPC formulation and BEFRG recurrence | Python top-down and bottom-up implementations with deterministic tie-breaking, policy trace and independent physical replay |
| Full-charge vs discrete partial charging | Independent FC/DPC comparison and station/target policy validation |
| Nonlinear charging curves | Exact piecewise-linear charge-time calculations with unit tests |
| Reported MILP baseline | New independent discretized-flow MILP and continuous-charge MILP in `experiments/milp.py` |
| Snapshot traffic discussion | Static vs hourly-speed substitute (`exp_h`); **not** a true time-expanded planner |
| No grid error correction | Physical-SoC label DP with charge-level grid, validator and objective/runtime sensitivity |
| No thermal degradation objective | Bounded capacity derating, driving HVAC consumption and uncalibrated per-charge throughput cost |
| Montoya/SF/Amsterdam evaluations | Four additional **synthetic**, non-georeferenced practical stories |

## Original Montoya XML: physically executable extension (new evidence)

**See [`results/montoya_extension1/EXTENSION1_ORIGINAL_MONTOYA_REPORT.md`](results/montoya_extension1/EXTENSION1_ORIGINAL_MONTOYA_REPORT.md).** Three existing original-XML experiment groups (A/E/G) were rerun on the same independent cheapest-insertion customer tours before and after Extension 1, using no beam pruning. The floored BEFRG policy passed continuous physical replay in **2/17** configurations, versus **17/17** for Extension 1. At 320 customers and γ=Γ=16, original modeled route time was 4,636.69 min (physically invalid policy) and corrected time was 3,719.68 min (physically valid). This is a *modeled objective difference*, not a realized driving-time improvement. Small 6/10 customer continuous MILP solves certified equality with the corrected finite-target optimum. The original XML input and paper numerical benchmark tour/energy calibration are **not** the same thing.

An opt-in exact Euclidean-SoC dominance filter safely reduces the label search for those metric instances. It is rejected on sparse or directed distances because the needed triangle inequality is not guaranteed. The solver's only finite-target optimum claim assumes no beam pruning and is subject to the 11-decimal key tolerance. The small ablation showed the same objective and physical validity with/without dominance on 10/20/40 customer original-XML subsets. Sixteen additional *uncalibrated* thermal/SOH robustness checks on the same original-XML geometry also passed physical replay. No third extension was added.

```bash
# After installing external XML under data/raw/montoya/, as described below:
python -m experiments.montoya_extension_validation --suite all --output results/my_montoya_extension1
# Quickest main corrected-vs-floored demonstration (8 configs):
python -m experiments.montoya_extension_validation --suite G --output results/my_montoya_extension1
```

## Selected synthetic extension results — [ours-scaled-down]

The unpruned physical-SoC model produced physically executable finite-grid policies across the recorded Phase 3 sweeps. Mean floored-DP gap versus the continuous MILP decreased from 118.89% to 27.29% as Γ rose from 4 to 32 on deliberately stressed synthetic cases. With the corrected method, the mean gap decreased from 21.67% (γ=2) to 3.08% (γ=16). These percentages are *not* Montoya benchmark gaps; see `results/phase3/grid_comparison.csv` for individual rows.

In the four Phase 4 stories, modeled route times compared as: last-mile AC only 357.96 min vs hypothetical AC/DC 244.89 min; coach with all stations 612.20 vs one closed 634.81 min; empty truck 780.15 vs loaded 815.06 min; sparse one-station network 336.28 vs five-station network 207.67 min. All are synthetic and have no measured real-vehicle basis. See `results/phase4/comparisons.csv` and exact source inputs.

## Repository layout

```text
befrg/                    BEFRG core, charging, parsing, validators, physical and thermal extensions
befrg/baselines/          tiny brute force and no-memo recursion
experiments/              A–H, MILPs, comparisons, Phase 3/4 runners
configs/                  fixed-seed YAML configuration files
tests/                    pytest unit, property-like and regression checks
scripts/                  demos and result-provenance audit
simulators/               optional TraCI controller skeleton
data/raw/                 gitignored manual benchmark/traces/OSM inputs
notebooks/                example walkthrough and conditional real Montoya demo
results/                  CSV/JSON/PNG from executed synthetic experiments
docs/                     critical review, assumptions, design and reproducibility verdict
.github/workflows/        test and committed-output checks on push/pull request
```

## Limitations

**Optimality is always relative to a specified model.** The original BEFRG optimizes a finite residual battery grid, which can exclude physically feasible routes. The physical label DP eliminates per-node floor loss but optimizes only a finite charging-target grid and uses floating-point merges; with beam pruning its result is heuristic. The model assumes a fixed customer order and at most one charger per original arc. Thermal capacity and degradation penalties are synthetic surrogates, not calibrated electrochemistry. Original-source files, precise energy calibration and a production traffic simulation are unavailable in the bundled project. Execution time comparisons across hardware are not meaningful without environment controls. For a full list see [`docs/assumptions.md`](docs/assumptions.md). For GitHub publishing and verification steps, see [`docs/github_submission.md`](docs/github_submission.md).

## Citation, license and academic integrity

Cite both the original paper and this implementation: `CITATION.cff` contains machine-readable software attribution; the paper DOI is https://doi.org/10.1145/3762188. MIT license applies to original source code in this repository; it does **not** relicense or grant redistribution rights to third-party datasets or papers. The repository contains no copied authors' implementation; source algorithmic ideas are attributed. Before public release, check the software credit information in `CITATION.cff`, the research-data licenses, and any modified source provenance.

## Original Montoya XML reproduction pilot (October 2026)

The research group has now executed a separate **[original-XML; independent-tour]** pilot using all 120 available source XMLs as a verified corpus and two 320-customer instances for experiments **A, E, G, F**. See **[`results/montoya_pilot/REPRODUCTION_REPORT.md`](results/montoya_pilot/REPRODUCTION_REPORT.md)** for full results, physical validation failures, figures and input hashes. It includes paper numbers alongside results as contextual comparisons, **not exact matched reproductions**. The original benchmark files are excluded from Git and must be downloaded separately into `data/raw/montoya/`.

To reproduce the new pilot:

```bash
python -m experiments.benchmark_montoya --suite A
python -m experiments.benchmark_montoya --suite E
python -m experiments.benchmark_montoya --suite G
python -m experiments.benchmark_montoya --suite F
python -m experiments.benchmark_montoya --suite milp-small
```

**Limit:** The paper's Solomon-inspired tour and exact mass/θ are still not fully specified. Matched 50–150-node paper Table 2 MILP values, full 120-instance BEFRG timings, and 640–1600-node scaling were **not** replicated. Our floored-state DPC policies can also be invalid under physical charge replay; the CSVs preserve each failure.

**Canonical Extension 1 implementation:** `befrg/physical.py`. The older `befrg/extensions/exact_soc.py` is a secondary experimental prototype, and no published figure or result in this repository is derived from it. Do not confuse its separate routine with the canonical Phase 3/4 and Montoya Extension 1 implementation.
