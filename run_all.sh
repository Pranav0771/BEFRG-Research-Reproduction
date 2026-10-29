#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python}"
case "${1:-smoke}" in
  smoke)
    "$PYTHON_BIN" -m pytest -q
    "$PYTHON_BIN" -m scripts.run_example
    "$PYTHON_BIN" -m scripts.verify_results --check-hashes
    exit 0
    ;;
  quick)
    "$PYTHON_BIN" -m pytest -q
    "$PYTHON_BIN" -m experiments.run_all --quick --output results/recomputed_quick
    "$PYTHON_BIN" -m experiments.phase3 --quick --output results/phase3_quick
    "$PYTHON_BIN" -m experiments.phase4 --quick --output results/recomputed_phase4_quick
    ;;
  full-synthetic)
    "$PYTHON_BIN" -m pytest -q
    "$PYTHON_BIN" -m experiments.run_all --output results
    "$PYTHON_BIN" -m experiments.phase3 --output results/phase3
    "$PYTHON_BIN" -m experiments.phase4 --output results/phase4
    ;;
  *) echo "Usage: ./run_all.sh [smoke|quick|full-synthetic]" >&2; exit 2;;
esac
"$PYTHON_BIN" -m scripts.verify_results
