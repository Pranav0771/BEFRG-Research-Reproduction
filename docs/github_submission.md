# Before submission: independent reproduction checklist

## One-time local preparation

From the extracted repository folder, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
python -m scripts.run_example
python -m scripts.verify_results --check-hashes
# Or run the same tests, example and integrity checks together:
bash run_all.sh smoke
```

On Windows, activate with `.venv\Scripts\activate` instead.

**Expected archived-source result:** 53/53 tests pass on the tested Linux/Python 3.13 environment; CI additionally tests Python 3.10 and 3.12 after you push. A different machine can have different solver availability or library versions. The manifest check verifies saved file integrity; it does **not** rerun the original experiments.

## Exact git commands (you do the remote push)

First create an **empty** repository named `befrg-reproduction` in your own GitHub account, **without** initializing it with a README, license, or `.gitignore`. Next, run:

```bash
cd /path/to/frvcp-reproduction
git init -b main
git add .
git status --short
git commit -m "Independent BEFRG reproduction, two extensions, and synthetic experiments"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/befrg-reproduction.git
git push -u origin main
```

Replace `YOUR_GITHUB_USERNAME` with your actual account or organization. GitHub may require authentication through SSH, a credential manager, or a personal access token. If you already initialized a local Git repo, omit `git init`; if `origin` exists, inspect it with `git remote -v` before changing it.

## Verify before publishing

- [ ] All tests pass. Record Python, NumPy, SciPy, OS, CPU, and relevant dependency versions.
- [ ] `python -m scripts.verify_results --check-hashes` passes on the **unmodified** bundled outputs.
- [ ] Notebook `01_running_example.ipynb` runs; `02_montoya_xml_walkthrough.ipynb` appropriately reports `[not run]` if the dataset is absent.
- [ ] Clearly distinguish `[paper]`, `[ours-scaled-down]` and `[not run]` values in the README, reports and slides.
- [ ] No claims of full Montoya reproduction or verified SUMO simulation; the inputs were unavailable.
- [ ] Every algorithmic optimum specifies the model (floor-grid vs physical-SoC finite charge targets vs continuous MILP); route validator failures are preserved.
- [ ] No real private vehicle traces, externally licensed benchmark files, secret keys, credentials, or binary third-party distributions are staged.
- [ ] Confirm license rights for all reused figures and data; the original paper is **cited**, not redistributed.
- [ ] Verify author credit in `CITATION.cff`, date, repository URL, and final paper DOI before public release.
- [ ] Source changes are independently implemented, with all borrowed ideas and data attributed.
- [ ] Record result provenance and re-run selected experiments from their exact fixed-seed configurations.
- [ ] `git status --short` is clean after committing; inspect the GitHub Actions run after pushing.

If you regenerate results, the SHA256 manifest intentionally no longer matches; this is a useful provenance guard. Decide which outputs to replace, then explicitly rebuild the manifest only after validating and documenting the regenerated results.
