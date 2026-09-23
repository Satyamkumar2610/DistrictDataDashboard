# Changelog

Versions follow semantic versioning of `pipeline_version` (config/pipeline.yaml).
A MAJOR change can renumber canonical keys or change the meaning of a product.

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
