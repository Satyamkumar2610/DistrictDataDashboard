# Changelog

Versions follow semantic versioning of `pipeline_version` (config/pipeline.yaml).
A MAJOR change can renumber canonical keys or change the meaning of a product.

## 3.4.0

Phase 3: a data service. No key, lineage, area, product or evidence changes.

### Added
- r02: `docs/data_dictionary.md` / `.json`, generated from the contracts: 170 columns in 18 tables,
  each with type, nullability, unit, allowed values, meaning and the stage that writes it.
  `tests/test_release.py` fails on any released column without a contract or a meaning.
- r01: `data/release/`, byte-reproducible: 17 tables, the polygons of all 9 maps simplified per
  polygon (0.0005°, median area change 0.005%; full-resolution areas kept), `load.sql` (DuckDB
  views), `release_info.json`, `MANIFEST.csv`. Coverage simplification was measured and rejected
  (the layers' shared borders are digitised independently; it distorted Tumakuru by 26%).
- r03: read-only FastAPI service (`uvicorn district_evolution.release.api:app`): `/districts`,
  `/districts/{ck}`, `/timeline`, `/lineage`, `/geometry`, `/evidence`, `/crosswalk`, `/events`,
  `/research`, `/meta`; every response carries `pipeline_version` and `config_sha256`. p95 32 ms.
- r04: the District Ledger explorer at `/` for all 804 identities; every caption names its table row.
- Dependencies: fastapi 0.141.1, uvicorn 0.54.0, httpx 0.28.1.

## 3.3.0

Phase 2: an evidence layer. No key, lineage, area or product changes.

### Added
- Stages e01–e04. e01 turns every statement of an evidence source into a cited claim (1,771 from
  the frozen 2026-09-23 Wikidata snapshot). e02 locates each claim's subject by coordinate on the
  map of its date (633 subjects linked by geometry and name, 161 by geometry only, 28 without a
  coordinate). e03 gives each claim a verdict: 1,213 agree, 105 explained, 214 conflict, 239 not
  checkable. e04 gathers 395 open research questions.
- `data/reference/research_findings.csv`: the curated register that closes research questions
  (3 settled findings). Checks V21 (claim linked to an unknown key, ERROR), V22 (open questions,
  INFO), V23 (finding pointing at a vanished question, WARNING). 29 contracts (was 25).
- The external audit and e03 share one set of verdict rules (`evidence/rules.py`); the audit
  output is byte-identical after the refactor. Evidence thresholds moved to `config/pipeline.yaml`.

### Not done (by decision)
- DataMeet boundaries, Census District Handbooks and gazettes: no files yet (the owner will provide
  them). Each plugs in as an `EvidenceSource` (or a `BoundarySource` for audit) without core changes.

## 3.2.0

OD-01 decided: a district that is absorbed and later restored keeps a new key and gains a
`RECONSTITUTED_FROM` lineage edge. No key, product or area changes.

### Added
- s05 writes `RECONSTITUTED_FROM` when a closed identity with no lineage successor (absorbed into
  existing districts) returns as a new identity at least one map later that is mostly its land
  (`lineage.reconstitution_share`). Two edges: Fatehgarh Sahib 1951 → 2001, Barnala 1951 → 2011.
  `district_relationship` 631 → 633; baselines in `tests/baselines/v3.2.0.yaml`.

## 3.1.0

No canonical key, product or data output changed. One gate result changed: V18 has no
findings (was Manipur 1971: 4/5), explained below; baselines in `tests/baselines/v3.1.0.yaml`.

### Changed
- Code moved into the `district_evolution` package (`core`, `contracts`, `stages`, `sources`,
  `evidence`); stages run as `python -m district_evolution.stages.<stage>`. Install with
  `pip install -e . --no-deps`. Proven byte-identical on every deterministic output.
- s01 reads maps through `BoundarySource` adapters checked against a new `boundary_layer` contract.
- The V5 output manifest is built from the outputs declared in `dvc.yaml` (36 data outputs); it
  previously globbed directories and had picked up 25 stale copies. Silver layers are declared
  one file each. The copies come from iCloud Drive syncing the working folder: it duplicates
  files rewritten mid-sync as "<name> 2.<ext>".
- The Wikidata external audit is a DVC stage (`a01_external_audit`), so its outputs are rebuilt
  and hash-tracked with everything else.
- The s08 splink model JSON and the s03 GeoPackage are now byte-reproducible (random linker id
  dropped and floats rounded to 12 decimals; fixed GeoPackage timestamp). The DuckDB warehouse is
  the one output allowed to differ between builds, with its reason in `config/pipeline.yaml`.

### Added
- Check V20 (ERROR): a file under `data/silver`, `data/gold`, `data/products` or `outputs/` that no
  stage declares and git does not track.
- Regression baselines (`tests/baselines/v<version>.yaml`), CI comparing two full builds
  (`district_evolution/compare_builds.py`), a tag-triggered release workflow for Zenodo.

### Removed
- `official_district_area_benchmark.csv` (circular: SOI 2025 recomputed in a planar projection,
  finding F14), two unused v1 files under `data/silver/`, and the dead `sliver_threshold_km2`.

### Fixed
- The map-date rule (V18, external audit) read RENAME rows and parent-continuation rows as
  creations. Manipur's 1971 layer shows exactly the five districts created in 1969; four were
  renamed in 1981. Renames now inherit the original creation year, and a creation dated after an
  identity closed is treated as a later homonym. Districts shown before creation: 20 → 7.
  Evidence: `outputs/research/V18_manipur_1971.md`.
- The committed external audit report predated the confirmed Assam 1981 depiction row.

### Documented, not implemented
- OD-01 decision memo with measured evidence: `docs/decisions/OD-01_reclassification.md`.
- DVC remote and history rewrite runbook: `docs/operations/data_storage.md`.

## 3.0.0

Design and measured rationale: `docs/architecture/REVAMP_PLAN_V3.md`.

### Breaking
- **Canonical keys renumbered** (1,376 → 804). Identity now follows core-territory
  continuity instead of the symmetric 90/90 rule, which re-keyed every district that
  lost or gained more than 10% of its territory (Kangra had 6 keys). Every v2 key maps to its
  v3 key in `data/reference/ck_migration_v2_to_v3.csv` (448 identical, 923 merged into
  their continuation, 5 retired as non-administrative placeholders).
- **Event IDs changed.** A carve-out recorded twice in the events CSV (as NEW_DISTRICT and
  as SPLIT) is now one event (935 → 609 events; `recorded_as` keeps the original types).
- **Products replaced.** `district_census_area_matrix_backfilled` (mixed two meanings of
  area in one column) is replaced by `district_area_admin`, `crosswalk_to_reference`
  and `district_reference_context`.
- **Stages renumbered** into dependency order (s01–s12); s8 and s10b retired, s10
  rewritten as s09.

### Fixed
- Five unnamed placeholder polygons (including the ~80,520 km² and ~108,672 km²
  claimed-territory polygons in J&K) had received canonical keys; now excluded.
- Name normalization ignored `_`, so 212 of 468 state names in the 1991 layer never matched.
- Layers were not exact partitions (57–124 km² self-overlap per layer; Puducherry
  enclaves double counted in 2011). Overlaps now go to the enclave and are logged.
- Boundary displacement between independently digitized editions (~90,000 km²) was
  counted as territorial transfer; now its own class.
- Event linkage re-derived identity from name strings and ignored lineage; now uses a
  footprint-constrained probabilistic model. Residual "recovery" (non-deterministic,
  candidate pool limited to the event's own participants) removed: accounting follows
  the overlay partition exactly.
- Reported event transfer area exceeded India's area (retained area counted, events
  double counted); now split by role, with identifiability status per event.
- Runs were not deterministic (set-order tie-breaking); now byte-identical (V5).

### Added
- `requirements.txt` (pinned), `config/pipeline.yaml` (every threshold with rationale).
- Reference data: `state_lineage.csv`, `name_aliases.csv` (renames only; splits are not aliases).
- splink event linkage (s08), networkx lineage DAG (s05), pandera data contracts,
  DuckDB + spatial warehouse with enforced DDL and SQL invariants (s11), validation
  gate (s12), DVC pipeline (`dvc.yaml`), CI workflow, CITATION.cff, tests with golden
  historical cases.

## 2.0.0

Transition-matrix rebuild of the spatial core (planar overlay, deterministic IDs,
continuity-based identity, event-grain aggregation). See git history.
