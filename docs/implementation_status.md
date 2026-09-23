# Implementation Status: pipeline v3.0.0

The design is in `docs/architecture/REVAMP_PLAN_V3.md`, and §7 there has the measured results.
The live check results are in `outputs/pipeline/s12_validation_report.md`.

| Stage | Script | Status |
|---|---|---|
| s01 | s01_bronze_to_silver.py | Done: exact-partition repair, placeholder exclusion |
| s02 | s02_topology_audit.py | Done: V1 gate |
| s03 | s03_transition_matrix.py | Done: parts classified as CORE/TRANSFER/DISPLACEMENT/SLIVER; reference overlays |
| s04 | s04_identity.py | Done: core-continuity identity, 804 CKs; v2 migration map |
| s05 | s05_lineage.py | Done: networkx DAG, 631 edges |
| s06 | s06_area_ledger.py | Done |
| s07 | s07_events_aggregate.py | Done: 609 events, double recording merged |
| s08 | s08_event_linkage.py | Done: splink model, parameters in outputs/events/s08_splink_model.json |
| s09 | s09_event_reconciliation.py | Done: footprint-constrained linkage, partition accounting |
| s10 | s10_census_products.py | Done: admin areas, crosswalk to 2025, reference context |
| s11 | s11_warehouse.py | Done: DuckDB + spatial, enforced DDL, 13 SQL invariants |
| s12 | s12_validate.py | Done: gate PASS; 25/25 contracts; output hash manifest |

| Principle | Enforced by |
|---|---|
| Events are evidence, not spatial truth | DAG order (s07+ after s04/s05); lineage never rewritten by events |
| Conservation by construction | Exact layer partitions (V1 = 0) and overlay closure (V3) |
| Deterministic outputs | V5: 36/36 files byte-identical across builds (CI) |
| One area method | V4: pyproj vs DuckDB ST_Area_Spheroid ≤ 0.01% |
| DAG lineage | networkx (s05) and a recursive CTE (V10) |
| Transfers between continuing districts create no lineage edge | V9 (L-3) |
| Identified vs bounded event areas | V8 (MEASURED only when there is one event per window) |

Open decisions are listed in `CLAUDE.md` under "Open items".
