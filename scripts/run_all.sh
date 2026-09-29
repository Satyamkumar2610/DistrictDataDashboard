#!/usr/bin/env bash
# Runs the District Evolution pipeline v3 end to end.
# Setup once: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e . --no-deps
# Design: docs/architecture/REVAMP_PLAN_V3.md. Equivalent DAG run: dvc repro
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"

for stage in \
  s01_bronze_to_silver \
  s02_topology_audit \
  s03_transition_matrix \
  s04_identity \
  s05_lineage \
  s06_area_ledger \
  s07_events_aggregate \
  s08_event_linkage \
  s09_event_reconciliation \
  s10_census_products \
  s11_warehouse \
  s12_validate
do
  echo "================ ${stage} ================"
  "$PY" -m "district_evolution.stages.${stage}"
done

echo "Pipeline complete. Report: outputs/pipeline/s12_validation_report.md"
