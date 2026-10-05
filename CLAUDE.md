# District Evolution: Project Guide

## What this project solves

India's district map changed constantly between 1951 and 2025, growing from 316 to 733 districts on the
2025 Survey of India map (which lags Andhra Pradesh's 2022 and Rajasthan's 2023 reorganisations).
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
| v2 → v3 key map | `data/reference/ck_migration_v2_to_v3.csv` | Resolves every old v2 key |
| Mislabelled vintages (curated, confirmed only) | `data/reference/vintage_depiction.csv` | A map's boundaries depict a later year than its own label (e.g. Stanford "1981" Assam depicts ~1989) |
| Research findings (curated, with evidence and citation) | `data/reference/research_findings.csv` | Settled research questions; the only way a research-queue item is closed |
| Known geometry gaps (curated, confirmed only) | `data/reference/known_geometry_gaps.csv` | A vintage is missing districts other evidence confirms already existed (e.g. SOI 2025 still shows Mizoram's pre-2018 8 districts) |

Bronze files are committed and must never be modified.

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e . --no-deps   # once
bash scripts/run_all.sh                   # = python -m district_evolution build && ... validate
.venv/bin/python -m pytest tests          # unit tests, golden history, regression baselines (needs a built warehouse)
source .venv/bin/activate && dvc repro    # same DAG; reruns only what changed; hashes in dvc.lock
(cd web && npm ci && npm run build)       # web platform; then:
.venv/bin/uvicorn district_evolution.release.api:app   # platform at http://127.0.0.1:8000, API under /api, OpenAPI at /docs
```

`s12_validate` exits non-zero if any ERROR check fails. The report is
`outputs/pipeline/s12_validation_report.md`. Regression baselines (row counts, class breakdowns,
gate results) are in `tests/baselines/v<pipeline_version>.yaml`; a PR that changes one updates
that file and explains the delta.

## Pipeline (`district_evolution/stages/`)

Each stage runs as `python -m district_evolution.stages.<stage>`.

Geometry stages come first. Events enter only after identity and lineage are fixed, so events
are evidence and never drive geometry.

| Stage | Does |
|---|---|
| s01 bronze→silver | Standardize geometry and compute geodesic area/perimeter. Exclude placeholders: unnamed polygons and "Disputed (…)" strips (config `placeholders`). Repair each layer into an exact partition (overlap goes to the enclave). |
| s02 topology | V1 gate: layer self-overlap |
| s03 transition matrix | Overlay adjacent vintages and each vintage against 2025. Classify every part as CORE / TRANSFER / BOUNDARY_DISPLACEMENT / SLIVER. |
| s04 identity | Canonical keys (CKs) by core-territory continuity. Names break ties only when the geometry is ambiguous. A whole district that keeps its name and grows continues (OD-02). |
| s05 lineage | FORMED_FROM / SPLIT_FROM / MERGED_INTO into new CKs; RECONSTITUTED_FROM across a gap (OD-01). Measured transfers between existing CKs. networkx DAG check. |
| s06 ledger | Per-CK, per-window area accounting that closes exactly |
| s07 events | CSV → administrative event grain. A change recorded as both NEW_DISTRICT and SPLIT is one event. |
| s08 linkage | splink Fellegi-Sunter model linking event names to CK records (name + state evidence: the map's state, the district's present-day state, state lineage). V27 warns if a probability class nears the threshold. |
| s09 reconciliation | Link successors only within the predecessor's territorial footprint. Partition-exact accounting. MEASURED only when there is one event per window. |
| s10 products | `district_area_admin`, `crosswalk_to_reference`, `district_reference_context` |
| e01 evidence claims | Every statement of every evidence source (now: the frozen Wikidata snapshot) as a cited claim: NAME, AREA, INCEPTION, PARENT |
| e02 claim linkage | Locate each claim's subject by its coordinate on the map of its date; the name only qualifies the link |
| e03 claim verdicts | AGREE / EXPLAINED / CONFLICT / NOT_CHECKABLE with a reason, using the rules the audit uses; PARENT by the footprint rule |
| h01–h05 harmonization | Link reported statistics (config/indicators.yaml) to identities on the map they report on; allocate totals with a stated weight method (AREA; CROPLAND when a cropland raster is declared, `docs/operations/cropland_weights.md`); report per-district method sensitivity; recompute ratios such as yield from harmonized totals, never allocate them; check conservation and a mapped-area self-check that must reproduce s10 |
| r02 data dictionary | `docs/data_dictionary.md`, generated from the contracts; every column's meaning lives in `contracts/descriptions.py` |
| r01 release | `data/release/`: tables, simplified geometry per map, `load.sql` (DuckDB views), `release_info.json`, `MANIFEST.csv`; byte-reproducible |
| e04 research queue | Every open question in one table; closed only by a curated row in `data/reference/research_findings.csv` |
| a02 credibility audit | Measures trust from the maps, the events compilation and the internal checks only: edition agreement, land not carried to the next map, map lag against the events, land that moves and comes back, area reversals, unrecorded name changes, event sourcing. `outputs/audit/CREDIBILITY_AUDIT.md` |
| s11 warehouse | `data/gold/district_evolution.duckdb`: enforced DDL, SQL invariants, independent ST_Area_Spheroid check |
| s12 validate | pandera contracts, collect all checks, output hash manifest, report, gate |

Shared code:
- `district_evolution/core/`: `config` (paths, `CFG`, vintages), `area` (the one area method),
  `ids`, `names`, `reference` (curated reference tables), `io` (`write_table`), `lineage_graph`
  (networkx). Stages import it as `from district_evolution import core`.
- `district_evolution/contracts/schemas.py`: pandera contracts for every table.
- `district_evolution/sources/`: boundary map adapters (Stanford, SOI). A new map series is one
  adapter returning the `boundary_layer` contract in EPSG:4326; s01 keeps placeholder exclusion,
  partition repair and area, so no source can bypass them.
- `district_evolution/core/interfaces.py`: the extension points (`BoundarySource`,
  `EvidenceSource`, `Indicator`, `WeightMethod`).
- `district_evolution/harmonize/`: indicators (`CsvIndicator` for a supplied file), weight methods
  (`AreaWeight`; `CroplandWeight` in `cropland.py`, zonal sums of a declared raster over each map's overlay on 2025), the engine (`link`, `allocate` refuses ratios, `ratios`). A new crop statistic is one
  entry in `config/indicators.yaml` plus a `docs/sources/<source>.md` evaluation. `restate.py` runs
  the same engine on a user's file from a release's tables (CLI `harmonize.cli`, `POST /api/harmonize`,
  the Harmonize page); nothing is stored.
- `district_evolution/evidence/`: evidence sources (`EVIDENCE_SOURCES`), shared verdict rules
  (`rules.py`), point location (`geo.py`), the Wikidata snapshot and the external audit (a01).
  Evidence stages write only to `data/gold/evidence` and `outputs/evidence`, and no s01–s10 stage
  reads them (`tests/test_evidence.py`).

## Rules for working in this repo

- **Geometry decides identity and area.** Names and events only corroborate or break ties within
  spatially valid candidates. Never resolve identity from name strings alone.
- **Every km² gets exactly one classification.** Area is conserved by the s03 partition. Never
  normalize weights to 1, never distribute residuals, never force a residual to zero.
- **Every product has one stated meaning.** If a column would mix two meanings, make two products.
- **Write tables through `core.write_table(df, path, "<schema>")`.** Add or extend the contract in
  `contracts/schemas.py` for any new table. A new invariant goes into s11 as SQL with a severity.
- **Keep builds deterministic.** Use `core.stable_id` for IDs (never `uuid4`), explicit sorts before
  any tie-break, and a seeded splink. CI rebuilds twice and diffs the output manifests.
- **Configure every threshold in `config/pipeline.yaml`** with a rationale, ideally measured on the
  data.
- **Use one area method:** `core.geodesic_area_km2` (WGS84). DuckDB `ST_Area_Spheroid` is the
  independent cross-check.
- **Aliases record the same entity under another name.** A split (Malabar → Kozhikode) is lineage,
  not an alias.
- **Disagreements between the events CSV and the maps are findings.** Report them (the research
  queue in the s12 report). Never "recover" them automatically.
- **Changing identity rules renumbers CKs.** That is a MAJOR version: bump `pipeline_version`,
  update `CHANGELOG.md`, and extend the CK migration map.

## Open items

- **Licensing blocks any public data release** (`docs/decisions/licensing.md`). The 1951–2021 maps
  are ML InfoMap data licensed to Stanford affiliates only, "not to be reproduced or used for any
  purpose without permission"; the GitHub repository contains them in its history. It was made
  private on 2026-09-30, which stops publication but not the history. Do not tag a release, publish
  `data/`, or make the repository public again until the owner decides. No LICENSE file until then.
- DVC remote and moving bronze out of git history (the `.git` directory is 691 MB). Needs a remote
  and a force-push coordinated with collaborators.
- Zenodo DOI: wired (`.github/workflows/release.yml`, `docs/operations/release.md`); needs the
  repository pushed and switched on at zenodo.org, then a `v3.0.0` tag.
- The Wikidata comparison (e01–e03, a01) is an **internal check**: it runs on every build and its
  contracts and counts are in the gate report, but it is not released, served or shown (owner decision
  2026-09-30; `release.INTERNAL_RESEARCH_TOPICS`). Validation rests on the maps, the events compilation
  and the internal checks; `a02` measures how far that goes. The work that would raise credibility
  is in `docs/audit/credibility_report.md`.
- OD-01 decided (3.2.0): a restored district gets a new key and a `RECONSTITUTED_FROM` edge
  (Fatehgarh Sahib, Barnala). `docs/decisions/OD-01_reclassification.md`. Six rename-plus-boundary
  breaks listed there are alias candidates for a future MAJOR version, pending documents.
- Do not keep the working copy in an iCloud-synced folder (e.g. Desktop with iCloud Drive).
  iCloud duplicates rewritten outputs as `<name> 2.<ext>` (V20 now fails on them) and marks
  `.pth` files hidden, which Python 3.13 skips, so `pip install -e .` silently has no effect.
- SOI 2025 lags Mizoram's 2019 districts (Khawzawl, Saitual; Hnahthial is also absent from the events
  compilation), Andhra Pradesh's 2022 reorganisation and Rajasthan's 2023 districts. Recorded in
  `data/reference/known_geometry_gaps.csv` (Mizoram CONFIRMED; the other two EVENTS_ONLY until a second
  source confirms them). Since OD-02 Champhai continues and absorbs Khawzawl's and Saitual's land as
  measured transfers; V19 still fails WARNING if a future build produces an undocumented `MERGED_INTO` edge.
- Credibility work plan: `docs/audit/credibility_report.md`.
