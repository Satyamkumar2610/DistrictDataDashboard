#!/usr/bin/env bash
# Runs the District Evolution pipeline end to end: every stage in dvc.yaml, in dependency order.
# Setup once: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e . --no-deps
# Options pass through, e.g. --from s04_identity, --until s12_validate, --dry-run.
# Equivalent with caching of unchanged stages: dvc repro
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m district_evolution build "$@"
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m district_evolution validate
