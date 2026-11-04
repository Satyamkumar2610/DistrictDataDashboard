# Implementation Status: pipeline v4.1.0

Design: `docs/architecture/REVAMP_PLAN_V3.md`; changes since v3 and their measured effect: `CHANGELOG.md`.
Live check results: `outputs/pipeline/s12_validation_report.md`. Column definitions: `docs/CODEBOOK.md`.
Dataset-level description, limitations and recommended uses: `docs/DATASHEET.md`.

| Stage | Script | Status |
|---|---|---|
| s01 | s01_bronze_to_silver.py | Exact-partition repair; placeholder and curated non-administrative exclusion; enclave-aware repair log |
| s02 | s02_topology_audit.py | V1 self-overlap gate; V2 interior gaps |
| s03 | s03_transition_matrix.py | ADJACENT, SKIP and REFERENCE overlays; parts classified; map-edition window types; width distribution |
| s04 | s04_identity.py | Core-continuity identity with skip-vintage rule; pinned CK numbers; sensitivity grid; `ck_identity_confidence` |
| s05 | s05_lineage.py | Lineage edges (km² + share floors), measured transfers, `ck_fate`, DAG check |
| s06 | s06_area_ledger.py | Two-sided ledger (OUT and IN close) |
| s07 | s07_events_aggregate.py | Event grain on the normalized predecessor set; protected multi-word names |
| s08 | s08_event_linkage.py | splink model, deterministic training |
| s09 | s09_event_reconciliation.py | Footprint-constrained linkage, joint disambiguation, predecessor- and successor-level identification |
| s10 | s10_census_products.py | Admin areas, crosswalks (reference + adjacent, with envelopes), context, continuity, district codes, gazetteer |
| s10h | s10h_harmonization.py | Census attributes, measured area uncertainty, comparable units, restated population, harmonization back-test |
| s11 | s11_warehouse.py | DuckDB + spatial, enforced DDL, SQL invariants V3–V29, views |
| s12 | s12_validate.py | Contracts, gate, manifest, source agreement and capture–recapture, research queue, report |

| Principle | Enforced by |
|---|---|
| Events are evidence, not spatial truth | DAG order (s07+ after s04/s05); lineage never rewritten by events |
| Conservation by construction | Exact layer partitions (V1), overlay closure (V3), two-sided ledger (V16, V23) |
| Deterministic outputs | V5: byte-identical output manifests across builds (CI) |
| One area method | V4: pyproj vs DuckDB ST_Area_Spheroid ≤ 0.01% |
| Every closed district has a fate | V20 |
| Comparable units partition their period | V27 |
| Uncertainty is reported, never hidden | crosswalk envelopes, `district_area_uncertainty`, `ck_identity_confidence`, `harmonization_backtest` |

Tools outside the build: `scripts/audit/` (Wikidata external audit, identity sensitivity at other deltas,
stratified manual review sample/score, boundary Monte Carlo), `scripts/maintenance/` (CK pinning, release
diff), `scripts/docs/build_codebook.py`. Open decisions: `CLAUDE.md`, "Open items".
