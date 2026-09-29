# Implementation Mapping

Where each part of the design lives in code, what it writes, and which tests cover it.
Paths are relative to `district_evolution/`. Tables are in `data/gold/district_evolution.duckdb`.

| Component | Module | Writes | Tests |
|---|---|---|---|
| Paths, config, vintages | `core/config.py` | — | `test_core.py` |
| The one area method | `core/area.py` | — | `test_core.py`, `test_geometry_rules.py` |
| Deterministic IDs | `core/ids.py` | — | `test_core.py` |
| Names, aliases, state spellings | `core/names.py` | — | `test_core.py` |
| Curated reference tables | `core/reference.py` | — | `test_core.py` |
| Validated writes | `core/io.py`, `contracts/schemas.py` | every gold and product table | `test_events_and_contracts.py` |
| Lineage DAG | `core/lineage_graph.py` | — | `test_events_and_contracts.py` |
| Extension points | `core/interfaces.py` | — | — |
| Boundary map adapters | `sources/stanford.py`, `sources/soi.py`, `sources/gpkg.py` | (in memory, `boundary_layer` contract) | `test_sources.py` |
| Bronze → silver, partition repair | `stages/s01_bronze_to_silver.py` | `data/silver/geometry/*.geoparquet` | `test_geometry_rules.py` |
| Topology gate (V1) | `stages/s02_topology_audit.py` | `outputs/pipeline/s02_topology_audit.csv` | — |
| Transition matrix | `stages/s03_transition_matrix.py` | `transition_flow`, `transition_residual` | `test_geometry_rules.py` |
| Identity | `stages/s04_identity.py` | `ck_registry`, `ck_observation`, `continuity_decision` | `test_identity_rules.py`, `test_golden_history.py` |
| Lineage | `stages/s05_lineage.py` | `district_relationship`, `ck_flow`, `measured_area_transfer`, `boundary_displacement` | `test_golden_history.py` |
| Area ledger | `stages/s06_area_ledger.py` | `district_ledger` (`data/products/district_area_ledger`) | — |
| Event grain | `stages/s07_events_aggregate.py` | `boundary_event`, `event_participant` | — |
| Event linkage (splink) | `stages/s08_event_linkage.py` | `participant_ck_candidate` | — |
| Event reconciliation | `stages/s09_event_reconciliation.py` | `event_linkage`, `event_accounting`, `event_flow`, `event_summary`, `lineage_corroboration` | `test_events_and_contracts.py` |
| Census products | `stages/s10_census_products.py` | `district_area_admin`, `crosswalk_to_reference`, `district_reference_context` | — |
| Warehouse and SQL invariants | `stages/s11_warehouse.py` | `district_evolution.duckdb`, `outputs/pipeline/s11_invariants.csv` | `test_golden_history.py`, `test_baselines.py` |
| Validation gate | `stages/s12_validate.py` | `outputs/pipeline/s12_*` | `test_baselines.py` |
| External audit (Wikidata) | `evidence/wikidata_snapshot.py`, `evidence/wikidata_audit.py` | `data/reference/external/*.json`, `outputs/audit/*` | — |
