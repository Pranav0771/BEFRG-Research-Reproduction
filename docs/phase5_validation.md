# Phase 5 validation log — 2026-10-28

This log documents checks executed during final repository packaging. It is not evidence that the original benchmark numerical results were reproduced.

| Check | Observation | Provenance |
|---|---|---|
| Existing pytest suite | 53/53 tests passed on Python 3.13.5, Linux | `[ours-scaled-down]` code tests |
| `scripts.run_example` | Correct, floored DP 9.352 min, physical replay 8.584 min | `[ours-scaled-down]` |
| `notebooks/01_running_example.ipynb` | Code cells executed without error; finite-target physical planner 7.000 min, continuous MILP 7.000 min, solver optimality certified | `[ours-scaled-down]` |
| `notebooks/02_montoya_xml_walkthrough.ipynb` | Code cells executed correctly but reported source XML missing | `[not run]` original benchmark |
| `scripts.verify_results --check-hashes` | All 67 archived CSV/PNG/JSON files matched SHA256 manifest | Integrity check only |
| `make -n exp-a` | Confirmed valid runnable experiment command after Makefile fix | Command validation |
| `run_all.sh quick` | Partial execution: Phase 2 quick A–H completed; Phase 3 quick emitted a 9-grid/15-thermal/21-sensitivity summary before the aggregate run exceeded its execution window. Phase 4 quick was not reached; no complete end-to-end quick assertion is made. | `[ours-scaled-down]` / incomplete |
| `run_all.sh smoke` | Run at release packaging; unit tests, paper example and integrity only | See current command output |

The original Montoya 120-instance reproduction and SUMO/CRAWDAD simulation remain `[not run]`. Phase 3/4 source data are synthetic, as documented in `docs/reproducibility.md`. CI is configured to run Python 3.10 and Python 3.12 tests **after** the repository is pushed; those workflow runs have not occurred in this environment.
