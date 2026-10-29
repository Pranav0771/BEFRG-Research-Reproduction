# Demo notebooks

`01_running_example.ipynb`: executable, sparse Figure 2 paper instance and continuous MILP comparison. `02_montoya_xml_walkthrough.ipynb`: checks `data/raw/montoya/` for an original XML and runs only if present; **[not run]** otherwise. Both notebooks are committed without stored execution outputs to prevent stale or fabricated observations.

```bash
python -m pip install -e '.[notebook]'
jupyter lab
```

Launch from the repository root. Kernel is Python 3. `pip install -e '.[notebook]'` also installs the package itself.
