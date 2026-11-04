# Changelog

Versions follow semantic versioning of `pipeline_version` (config/pipeline.yaml).
A MAJOR change can renumber canonical keys or change the meaning of a product.

## 4.0.0

Code-logic audit of v3.0.0 (no external sources). Every change below was measured on the
v3.0.0 build; the numbers are v3.0.0 → v4.0.0.

### Breaking
- **15 canonical keys retired** (804 → 789), every one mapped in
  `data/reference/ck_migration_v3_to_v4.csv`. The other 789 keep their v3 numbers: CK
  numbers are now **pinned** to each identity's first observation
  (`data/reference/ck_pinned_registry.csv`), so a rule change renumbers only identities it
  really changes. Retired numbers are never reused. After a reviewed build,
  `scripts/maintenance/pin_ck_registry.py` appends new CKs and writes the migration map.
- **Active districts at 2025: 742 → 733.** Nine SOI 2025 "DISPUTED (A & B)" interstate
  patches (0.7–14.5 km²) were registered as districts, with lineage edges and crosswalk
  targets. Now excluded via `data/reference/non_administrative_features.csv`. Their area
  shows downstream as unmapped coverage.
- **Event IDs changed for re-grouped events** (609 → 605). Events are grouped on the set of
  normalized, alias-resolved predecessors, not on the raw string, so `Cannanore`/`Kannur`,
  `Mahabubnagar`/`Mahbubnagar` (×2) and `North West`/`North-West` are one event each.
- **`MEASURED` is stricter.** It also requires that no event of the same state and window
  has an unresolved predecessor (new status `UNIDENTIFIED_UNLINKED_EVENT_IN_WINDOW`).
- **Linkage threshold `min_match_probability` 0.50 → 0.30**, placed in the widest gap of
  the fitted distribution. 0.50 sat on the mode of the commonest true pattern (exact name
  plus historically compatible state, p = 0.49–0.51), so links flipped on training noise.
- **`ck_registry` / `district_relationship` / `area_ledger` / `crosswalk_to_reference`
  gained columns** (see Added). `area_ledger` now has rows for CKs new at `year_b`
  (`area_before_km2 = 0`).

### Fixed
- **A single defective map broke identities.** New rule 4 (`SKIP_VINTAGE_CORE`): when a
  district breaks but lies almost wholly inside an unclaimed target, the same CK's
  previous observation is tested against it on a direct k → k+2 overlay (new `SKIP`
  overlays in s03). This repairs Kolkata (Stanford 2021 draws it at 98.6 km² against
  196 km²), Chennai (Stanford 2011 under-draws it, and v3 minted "Chennai, established 2021")
  and Champhai (SOI 2025 lag).
- **Spelling variants broke identities**: Reasi/Riasi, Bametara/Bemetara and Nagore/Nagaur
  added to `name_aliases.csv`. Nagore was found by the new V26 check.
- **Event parsing split single names on "and"**: "Jammu And Kashmir", "Andaman And
  Nicobar Islands", "United Khasi And Jaintia Hills", "United Mikir And North Cachar
  Hills" and "Daman And Diu" became 2 fake predecessors each (16 fragments, 13 linked).
  Names that occur whole on a map, as aliases, or as state/UT names are now protected,
  and "Parts of" is dropped.
- **Closed districts with no fate.** Districts absorbed into existing districts had no
  outgoing lineage, so "where did it go?" had no answer. New `ck_fate` table; V20 makes
  a closed CK without a fate an ERROR (now 56/56 have one).
- **Ledger recorded only outflow.** It now closes in both directions with
  `coverage_gain_km2`; for example, 2011 → 2021 gains about 123,000 km² of depicted territory
  that v3 never recorded.
- **Ambiguous event links were accepted** into accounting and corroboration. They are now
  resolved jointly (the near-tied candidate whose footprint contains a declared
  successor), otherwise queued and not used. SPLIT/NEW_DISTRICT predecessors are
  restricted to CKs that gave territory away in that window, and windows are chosen by
  geometry-confirmed links, not name counts. Result: unresolved participants 132 → 99,
  outside-footprint 42 → 30, corroborated lineage edges 68% → 76%.
- **Lineage edges from boundary nudges**: an edge now also needs ≥ 1% of its source or
  target (`lineage.material_share`); 26 sub-threshold flows are kept in
  `minor_material_flow`. Measured transfers keep only the km² floor.
- **splink training was not deterministic** (parallel float sums, random `linker_uid`).
  Now single-threaded with a fixed ID; two builds give identical manifests.
- s01 assumed Stanford layers were EPSG:4326; it now reads the CRS and fails if it is missing.
- s11 always downloaded the DuckDB spatial extension. It now loads it locally first and
  honours `DUCKDB_EXTENSION_DIRECTORY` for offline builds.
- Hard-coded thresholds (`MIN_SOURCE_SHARE`, V12 and V17 tolerances) moved to `config/pipeline.yaml`.
- `ck_flow`, `boundary_displacement`, `event_flow`, `event_summary` and
  `lineage_corroboration` were written without contracts; all tables now go through
  `lib.write_table` (33 contracts).

### Added
- Checks: V2 layer gaps (the configured `gap_warn_fraction` was never used), V20 closed CK
  without fate, V21 new CK without origin, V22 non-enclave overlap repair, V23 forward
  ledger closure, V24 area dip-and-recover (flags Kolkata 2021), V25 non-administrative
  name on a CK, V26 near-continuation (alias curation). V19 now covers `ABSORBED_INTO` at
  the reference vintage.
- `outputs/pipeline/s12_research_queue.csv`: one typed queue of every finding that needs
  a documentary check (87 rows).
- Products: `ck_reference_continuity` (share of each CK's year-Y territory inside its own
  2025 polygon; Bastar keeps its CK with 14% of its 1951 area) and
  `crosswalk_to_reference.source_mapped_share`.
- `district_relationship.source_closes` and `.n_target_sources`;
  `continuity_decision.evidence_year`; `event_accounting.n_unlinked_events_same_window`.
- `scripts/audit/identity_sensitivity.py`: reruns identity with each threshold ±0.05.
  At most 9 of 789 identities move; the movers are listed for review.

### Not changed, with reasons
- A third splink comparison (record vintage near the event year) was tested and
  rejected. It is uninformative (m ≈ u) because a matching CK has a record at every vintage.
  Jaro-Winkler on a word-sorted name key was also rejected: it paired "Kanara" with
  "Kannada Uttara" via the prefix bonus.
- s03 now also computes 7 SKIP overlays; it took about 4.5 min in the v4 development build.

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
