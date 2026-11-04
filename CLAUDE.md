# District Evolution: Project Guide

## What this project solves

India's district map changed constantly between 1951 and 2025, growing from 316 to 742 districts.
For any district at any census year, this pipeline answers four questions, each with an evidence
chain:

- **Identity:** is this the same administrative entity as one that existed earlier?
- **Origin:** which earlier districts did its territory come from?
- **Fate:** where did its territory go?
- **Quantity:** how many km² moved, and when?

The downstream purpose is **harmonization**: restating statistics reported on one census's
districts onto the 2025 districts.

The design and the measured justification for every rule are in
`docs/architecture/REVAMP_PLAN_V3.md`. Read it before changing identity, linkage, or product
semantics.

## Evidence

| Source | Location | Proves |
|---|---|---|
| 9 boundary vintages: Stanford 1951–2021, Survey of India 2025 | `data/bronze/{stanford,soi}` | Net territorial change between consecutive maps |
| Events compilation (1,550 rows, one per parent-child pair) | `data/bronze/events/district_evolution_master.csv` | That a change happened, roughly when, and what it was called. It records most carve-outs twice. |
| State reorganisations (curated) | `data/reference/state_lineage.csv` | Which states a district can appear under at other dates |
| Renames and spellings (curated, same entity only) | `data/reference/name_aliases.csv` | Name equivalence. Splits are never aliases. |
| v2 → v3 and v3 → v4 key maps | `data/reference/ck_migration_v2_to_v3.csv`, `ck_migration_v3_to_v4.csv` | Resolve every retired key |
| Pinned CK numbers | `data/reference/ck_pinned_registry.csv` | Which CK number each identity (by first observation) carries; append-only, written by `scripts/maintenance/pin_ck_registry.py` |
| Non-administrative features (curated, confirmed only) | `data/reference/non_administrative_features.csv` | Named polygons that are not districts (SOI 2025 "DISPUTED (A & B)" patches) |
| Mislabelled vintages (curated, confirmed only) | `data/reference/vintage_depiction.csv` | A map's boundaries depict a later year than its own label (e.g. Stanford "1981" Assam depicts ~1989) |
| Known geometry gaps (curated, confirmed only) | `data/reference/known_geometry_gaps.csv` | A vintage is missing districts other evidence confirms already existed (e.g. SOI 2025 still shows Mizoram's pre-2018 8 districts) |

Bronze files are committed and must never be modified.

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
bash scripts/pipeline/run_all.sh          # full build + validation gate (s03 alone took ~4.5 min in v4 development)
.venv/bin/python -m pytest tests          # unit tests + golden history (needs a built warehouse)
source .venv/bin/activate && dvc repro    # same DAG; reruns only what changed; hashes in dvc.lock
```

`s12_validate` exits non-zero if any ERROR check fails. The report is
`outputs/pipeline/s12_validation_report.md`; every finding needing a documentary check is in
`outputs/pipeline/s12_research_queue.csv`. s11 needs the DuckDB `spatial` extension: it loads it
locally and only downloads it if missing; for offline builds set `DUCKDB_EXTENSION_DIRECTORY`.
s04 reruns identity with each threshold ±`identity.sensitivity_delta` on every build
(`ck_identity_confidence`). Docs: `docs/CODEBOOK.md` (regenerate with
`scripts/docs/build_codebook.py`), `docs/DATASHEET.md`. Audit tools outside the build:
`scripts/audit/review_sample.py` + `review_score.py` (stratified manual review),
`boundary_monte_carlo.py`, `identity_sensitivity.py --delta`. Release diff:
`scripts/maintenance/release_diff.py`.

## Pipeline (`scripts/pipeline/`)

Geometry stages come first. Events enter only after identity and lineage are fixed, so events
are evidence and never drive geometry.

| Stage | Does |
|---|---|
| s01 bronze→silver | Standardize geometry and compute geodesic area/perimeter. Exclude unnamed placeholders and curated non-administrative features. Repair each layer into an exact partition (overlap goes to the enclave; non-enclave repairs are logged). |
| s02 topology | V1 gate: layer self-overlap; V2: interior gaps |
| s03 transition matrix | Overlay adjacent vintages (ADJACENT), vintages two apart (SKIP) and each vintage against 2025 (REFERENCE). Classify every part as CORE / TRANSFER / BOUNDARY_DISPLACEMENT / SLIVER. |
| s04 identity | Canonical keys (CKs) by core-territory continuity. Names break ties only when the geometry is ambiguous. Rule 4: a break caused by one defective map is tested on the SKIP overlay. CK numbers come from the pinned registry. |
| s05 lineage | FORMED_FROM / SPLIT_FROM / MERGED_INTO into new CKs (km² and share floors). Measured transfers between existing CKs. `ck_fate` for every closed CK (incl. ABSORBED_INTO). networkx DAG check. |
| s06 ledger | Per-CK, per-window area accounting that closes exactly in both directions (out: where it went; in: where it came from, incl. coverage gain) |
| s07 events | CSV → administrative event grain. A change recorded as both NEW_DISTRICT and SPLIT is one event; grouped on the normalized predecessor set; names that are one entity ("Jammu And Kashmir") are never split. |
| s08 linkage | splink Fellegi-Sunter model linking event names to CK records (name + state-lineage evidence) |
| s09 reconciliation | Link successors only within the predecessor's territorial footprint; predecessors of splits only among CKs that gave territory away; ambiguous links resolved by footprint or not used. Partition-exact accounting. MEASURED only when there is one event per window and no unlinked event beside it. |
| s10 products | `district_area_admin`, `crosswalk_to_reference` and `crosswalk_adjacent` (with low/high envelope), `district_reference_context`, `ck_reference_continuity`, `ck_district_code`, `name_gazetteer` |
| s10h harmonization | Census attributes carried by the layers; area uncertainty with σ measured against census areas; comparable units (exact aggregation); population restated onto 2025 and onto units; back-test of area weighting |
| s11 warehouse | `data/gold/district_evolution.duckdb`: enforced DDL, SQL invariants, independent ST_Area_Spheroid check |
| s12 validate | pandera contracts, collect all checks, output hash manifest, research queue, report, gate |

Shared modules: `lib.py` (paths, config, area, IDs, names, reference data, `write_table`),
`schemas.py` (pandera contracts for every table), `lineage_graph.py` (networkx),
`harmonize.py` (restate by area weights / aggregate to comparable units), `quality.py`
(capture–recapture, AUC).

## Rules for working in this repo

- **Geometry decides identity and area.** Names and events only corroborate or break ties within
  spatially valid candidates. Never resolve identity from name strings alone.
- **Every km² gets exactly one classification.** Area is conserved by the s03 partition. Never
  normalize weights to 1, never distribute residuals, never force a residual to zero.
- **Every product has one stated meaning.** If a column would mix two meanings, make two products.
- **Write tables through `lib.write_table(df, path, "<schema>")`.** Add or extend the contract in
  `schemas.py` for any new table. A new invariant goes into s11 as SQL with a severity.
- **Keep builds deterministic.** Use `lib.stable_id` for IDs (never `uuid4`), explicit sorts before
  any tie-break, and a seeded splink. CI rebuilds twice and diffs the output manifests.
- **Configure every threshold in `config/pipeline.yaml`** with a rationale, ideally measured on the
  data.
- **Use one area method:** `lib.geodesic_area_km2` (WGS84). DuckDB `ST_Area_Spheroid` is the
  independent cross-check.
- **Aliases record the same entity under another name.** A split (Malabar → Kozhikode) is lineage,
  not an alias.
- **Disagreements between the events CSV and the maps are findings.** Report them (the research
  queue in the s12 report). Never "recover" them automatically.
- **Changing identity rules can retire CKs.** That is a MAJOR version: bump `pipeline_version`,
  update `CHANGELOG.md`, review the build, then run `scripts/maintenance/pin_ck_registry.py`
  (it appends new CKs to the pinned registry and writes the migration map for retired ones).
  Never edit or reuse a pinned number by hand.
- **Report uncertainty with every number.** A new weight or area gets its envelope or measured error;
  a rate is never area-weighted directly (use `harmonize.restate(kind="rate")` with its denominator).
- **Document every product column** in `docs/codebook.yaml`; `tests/test_codebook.py` fails otherwise.
- **A named polygon that is not a district** goes into `non_administrative_features.csv` with
  evidence; V25 fails if a CK carries such a name.

## Open items

- DVC remote and moving bronze out of git history (the `.git` directory is 691 MB). Needs a remote
  and a force-push coordinated with collaborators.
- Zenodo DOI (`CITATION.cff` is ready) and pushing the CI workflow.
- Independent ground truth: Wikidata (P1365/P1366 lineage, inception, area) is done —
  `outputs/audit/EXTERNAL_AUDIT_REPORT.md`, reproducible from a frozen snapshot via
  `scripts/audit/wikidata_snapshot.py` + `external_audit.py`. Census District Handbooks, DataMeet
  boundaries, and gazettes remain open.
- OD-01 (reclassification CK rule).
- SOI 2025 lags Mizoram's 2019 districts (Khawzawl, Saitual; Hnahthial is also absent from the
  events compilation). Since v4 Champhai/Aizawl/Lunglei keep their identities, so the gap shows
  as 3 `ABSORBED_INTO` fates (`ck_fate`). Documented, not silently fixed:
  `data/reference/known_geometry_gaps.csv` records the evidence, and `s12` check V19 fails
  WARNING if a future build produces an undocumented closure of this kind at the reference vintage.
- Research queue (`s12_research_queue.csv`): 30 outside-footprint successors, 26 historical
  absorptions, 19 shown-before-creation, 10 ambiguous links, Kolkata 2021 area anomaly, one
  non-enclave overlap repair (2011). Each needs a documentary check.
- Manual review: `scripts/audit/review_sample.py` draws the stratified sample; the per-class
  precision with intervals exists only once someone fills `outputs/audit/review_form.csv`.
- Same-edition displacement width: `s03_width_distribution.csv` holds the evidence for setting
  `displacement_width_km_by_window_type.SAME_EDITION` separately; still 1.0 km.
- Area weighting misallocates population in urban cores and mountain districts (back-test: median
  15% error where splitting is needed). Dasymetric weights need sub-district data the project
  does not have; `harmonize.restate` accepts any crosswalk, so such weights can be added as one.
- `state_lineage.csv` lacks some partial transfers (e.g. Bombay → Mysore/Karnataka 1956 for
  North Kanara), which is why exact-name links to historical states score only ~0.5.
