# Reproducibility assessment

**Caution:** The original Montoya XML files were subsequently supplied for a separate pilot and extension validation, but the exact author-generated customer tours and mass/θ calibration remain unavailable. The original SUMO/CRAWDAD traffic experiments were not run. Earlier synthetic comparisons are `[ours-scaled-down]`; additional Montoya runs are `[original-XML; independent-tour]`, with published references labeled `[paper]`. Synthetic trends are not exact paper reproductions. `--full` enables parsing original Montoya XML after manual download, but authors' vehicle mass, theta and tour construction remain incompletely specified.

| Paper claim / experiment | Evidence stored | Status |
|---|---|---|
| A, MILP vs BEFRG | `results/tables/exp_a.csv`, `results/figures/exp_a_gap.png`; discrete MILP cross-checks on synthetic inputs | Partially: algorithmic correctness; original instance not run |
| B, memoization vs no memo | `exp_b.csv`, `exp_b_memoization.png` | Partially: complexity trend, different route/data |
| C, varying customer count | `exp_c.csv`, `exp_c_route_time.png` | Partially: trend only |
| D, varying candidate stations | `exp_d.csv`, `exp_d_stations.png` | Partially: trend only |
| E, charge granularity | `exp_e.csv`, `exp_e_charge_levels.png` | Partially: trend only |
| F, scalability | `exp_f.csv`, `exp_f_scaling.png` | Partially: synthetic up to 320 customers; not all 120 instances |
| G, FC vs DPC | `exp_g.csv`, `exp_g_fc_dpc.png` | Partially: model RT; several baseline policies physically invalid |
| H, EFRGen online traffic | `exp_h_substitute.csv`, `exp_h_traffic.png` | Original experiment not tested; synthetic substitute only |
| Phase 3, physical label DP | `results/phase3/grid_comparison.csv`; MILP certificate fields, validation flags | Executed on surrogate inputs |
| Phase 3, thermal and sensitivity | `results/phase3/thermal_ablations.csv`, `sensitivity.csv` | Executed with uncalibrated coefficients |
| Phase 4, novel scenarios | `results/phase4/use_cases.csv`, `scenario_inputs.json`, `policies.json` | Executed on invented planar coordinates |
| Original Montoya XML pilot A/E/G/F | `results/montoya_pilot/` | Executed on original XML with an independently generated customer tour; paper’s exact numerical experiment remains unmatched |
| Original Montoya physical-SoC extension | `results/montoya_extension1/` | Original XML, same generated tour, 17/17 corrected policies physically validated and certified finite-grid optimal; not a paper numerical reproduction |
| Cross-machine baseline verification | `results/montoya_extension1/cross_machine_objectives.csv` | Earlier baseline vs user local-run 36/36 matched; corrected solver only run in current environment |

## Comparison method
Use `results/tables/phase2_paper_ours_overview.csv` for source attribution. Absolute and percentage differences are deliberately `N/A` when the benchmark route, station subset or energy parameters differ. For matched cases compute `abs_diff = ours - paper`, `relative_diff_pct = 100*(ours-paper)/paper` only if `paper != 0`, and report both the source and the solver's optimality certificate. A trend match is not equivalent to numerical reproduction.

## Hardware and instrumentation
Experiments record machine/Python version in selected metadata. Runtime figures were produced during earlier Phases 2–4; no claims about same-machine reproducibility or identical millisecond timings. `psutil` and `tracemalloc` measure different forms of memory (process RSS versus allocated Python memory). Do not conflate them.

## Missing original materials
See `data/README.md` for manually downloaded Montoya XML, CRAWDAD taxis, OSM networks and SUMO installation requirements. Missing original route-generation logic and physical parameters remain threats to replication even when those datasets are present.

## Standards for future evaluation
1. Verify every route with continuous physical SoC and check charging target strictly exceeds arrival SoC.
2. Distinguish continuous-MILP optimum, discrete-MILP optimum, and any solver incumbent without certificate.
3. Clearly record model/objective units: degradation penalties are not battery aging measurements.
4. Run `python -m pytest -q` and `python -m scripts.verify_results` before publishing.
5. Review `docs/assumptions.md` for all assumptions A01–A47.

## Update: original XML pilot executed

The user supplied all 120 original Montoya XML files. The separately executed original-XML pilot is recorded in `results/montoya_pilot/REPRODUCTION_REPORT.md` (five CSV result sets, four chart PNGs, method manifest, and code in `experiments/benchmark_montoya.py`). It uses the **real coordinates/charging curves** and our independent cheapest-insertion customer tour. Because the paper's exact tour generation and mass/θ calibration remain unavailable, its numeric values are **not direct reproductions** of paper Tables 2/6/7. The floor-grid policies frequently failed independent continuous-SoC validation. The original benchmark files remain excluded from the distributable code archive.

For new extension results, read `results/montoya_extension1/EXTENSION1_ORIGINAL_MONTOYA_REPORT.md`. Original XML was used only as **input coordinates, chargers and capacity**; the customer tour and θ are project assumptions. The preserved original XML is not distributed in this repository.
