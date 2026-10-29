# Generated experiment outputs

All committed numeric results were generated from executed code in staged project experiments. Phase 2–4 outputs are **synthetic surrogates**; separate `montoya_pilot/` and `montoya_extension1/` outputs use original Montoya XML inputs with our independently generated routes. None is an exact numerical reproduction of the original 120-instance Montoya experiment. Execution times are *observed*, hardware-dependent wall/CPU measurements and will vary.

- `tables/exp_[a-h]*.csv` and `figures/exp_*.png`: Phase 2 surrogate experiment A–H. `exp_h_substitute.csv` is **not SUMO**.
- `tables/phase2_paper_ours_overview.csv`: paper references versus synthetic observations; cross-instance absolute differences are correctly N/A.
- `phase3/`: finite charge-target / physical-SoC label-DP comparison, temperature and degradation sensitivities.
- `phase4/`: four synthetic scenarios; `scenario_inputs.json` contains the exact generated model inputs and `policies.json` contains their policy traces.
- `phase4_quick/`: optional earlier heuristic-beam quick run; do not call its policies globally optimal.
- `MANIFEST.sha256`: checksums for shipped CSV, PNG and JSON result artifacts, generated from their actual bytes at packaging time. These hashes represent archived outputs, not a guarantee of byte-identical reproduction on another platform.

## Rebuild

```bash
python -m experiments.exp_a --config configs/phase2.yaml --output results
python -m experiments.run_all --quick --output results/recomputed_quick
python -m experiments.phase3 --quick --output results/phase3_quick
python -m experiments.phase4 --quick --output results/phase4_quick
```

Do not compare 'quick' traces with unpruned Phase 4 optimality claims. See `docs/reproducibility.md` and `docs/assumptions.md`.

For exact archive integrity (not a claim of deterministic numerical regeneration), run `python -m scripts.verify_results --check-hashes`. If you intentionally regenerate experiment outputs, the manifest must be refreshed or the hash check will fail.

- `montoya_pilot/`: actual original Montoya XML instance runs on independently constructed tours, with explicit paper comparability caveat and physical replay status. Original XML files are not redistributed.

- `montoya_extension1/`: genuine-XML physically executable solver comparison A/E/G (17 variants), 2 certified small continuous-MILP subcases, 16 uncalibrated temperature robustness cases, Euclidean state-dominance ablation, 36 baseline cross-machine comparison rows, and report `EXTENSION1_ORIGINAL_MONTOYA_REPORT.md`.
