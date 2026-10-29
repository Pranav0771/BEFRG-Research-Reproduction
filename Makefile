PYTHON ?= python
PIP ?= $(PYTHON) -m pip
RESULTS ?= results
.PHONY: setup test smoke verify example notebooks exp-a exp-b exp-c exp-d exp-e exp-f exp-g exp-h phase2 phase2-quick phase3 phase3-quick phase4 phase4-quick all help
help:
	@echo 'make setup test example verify | make exp-a ... exp-h | make phase3 phase4'
	@echo 'All default phase2 experiments use synthetic surrogate data. Full Montoya requires manual data.'
setup:
	$(PIP) install -e '.[test]'
test:
	$(PYTHON) -m pytest -q
verify:
	$(PYTHON) -m scripts.verify_results
example:
	$(PYTHON) -m scripts.run_example
smoke: test example verify
exp-a exp-b exp-c exp-d exp-e exp-f exp-g exp-h:
	$(PYTHON) -m experiments.exp_$(@:exp-%=%) --config configs/phase2.yaml --output $(RESULTS)
phase2:
	$(PYTHON) -m experiments.run_all --config configs/phase2.yaml --output $(RESULTS)
phase2-quick:
	$(PYTHON) -m experiments.run_all --quick --config configs/phase2.yaml --output results/recomputed_quick
phase3:
	$(PYTHON) -m experiments.phase3 --config configs/phase3.yaml --output results/phase3
phase3-quick:
	$(PYTHON) -m experiments.phase3 --quick --config configs/phase3.yaml --output results/phase3_quick
phase4:
	$(PYTHON) -m experiments.phase4 --config configs/phase4.yaml --output results/phase4
phase4-quick:
	$(PYTHON) -m experiments.phase4 --quick --config configs/phase4.yaml --output results/phase4_quick
all: test phase2 phase3 phase4 verify
