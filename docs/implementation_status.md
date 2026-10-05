# Implementation Status: pipeline v4.0.0

The design is in `docs/architecture/REVAMP_PLAN_V3.md`; the live check results are in
`outputs/pipeline/s12_validation_report.md`; regression counts are in `tests/baselines/v4.0.0.yaml`.
Stage modules live in `district_evolution/stages/`; the module map is in
`docs/architecture/implementation_mapping.md`.

## Stages

| Stage | Status |
|---|---|
| s01–s02 | Done: exact-partition repair, placeholder exclusion (unnamed and disputed strips), V1 gate |
| s03 | Done: parts classified as CORE/TRANSFER/DISPLACEMENT/SLIVER; reference overlays |
| s04 | Done: core-continuity identity with growth continuation (OD-02), 785 identities; v2→v3 and v3→v4 key maps |
| s05–s06 | Done: networkx DAG lineage (incl. RECONSTITUTED_FROM, OD-01), measured transfers, closing ledger |
| s07–s09 | Done: 609 events, splink linkage (present-day state level, threshold in a class gap, V27), footprint reconciliation |
| s10 | Done: admin areas, crosswalk to 2025, crosswalk coverage, reference context |
| e01–e04 | Done: Wikidata claims, linkage and verdicts as an internal check (not released); research queue |
| h01–h05 | Done: linking, AREA and CROPLAND weights, allocation, ratios recomputed, conservation, self-check, method sensitivity. CROPLAND waits for a raster |
| r01–r02 | Done: byte-reproducible release with content-addressed provenance; generated data dictionary |
| a01–a02 | Done: Wikidata audit (internal) and the credibility audit with a fixed expert-review sample |
| s11–s12 | Done: DuckDB warehouse with SQL invariants and the independent area check; contracts, manifest, gate |
| Platform | Done: read-only FastAPI + DuckDB (health probe, gzip, request limits, security headers), React web app, container |

## Waiting on outside input

| Item | Needs | Where it plugs in |
|---|---|---|
| District crop statistics | Files from the owner, each evaluated in `docs/sources/` | `data/bronze/agri/` + `config/indicators.yaml` |
| Cropland raster | A raster from the owner | `data/bronze/cropland/` + `weights.cropland` (`docs/operations/cropland_weights.md`) |
| Census District Handbooks, gazette notifications | Documents (credibility report B1, B2) | Curated rows in `data/reference/` |
| Expert review verdicts | A person with the maps | `data/reference/review_outcomes.csv` (60 items in `outputs/audit/review_sample.csv`) |
| Public release, DOI, data licence | Permission for the 1951–2021 maps (`docs/decisions/licensing.md`) | `docs/operations/release.md` |
| DVC remote; bronze out of git history | A remote and a coordinated force-push | `docs/operations/data_storage.md` |

## Principles and their enforcement

| Principle | Enforced by |
|---|---|
| Events are evidence, not spatial truth | DAG order (s07+ after s04/s05); lineage never rewritten by events |
| Conservation by construction | Exact layer partitions (V1 = 0) and overlay closure (V3); h05 conservation per method |
| Deterministic outputs | V5: every declared output byte-identical across two builds (CI), except the DuckDB file (build time) |
| One area method | V4: pyproj vs DuckDB ST_Area_Spheroid ≤ 0.01%; cropland cell areas use the same method |
| DAG lineage | networkx (s05) and a recursive CTE (V10) |
| Transfers between continuing districts create no lineage edge | V9 (L-3) |
| Identified vs bounded event areas | V8 (MEASURED only when there is one event per window) |
| Weights never normalised | `statistical_crosswalk` contract: a source's weights sum to at most 1 |

Open decisions are listed in `CLAUDE.md` under "Open items".
