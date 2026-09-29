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
| v2 → v3 key map | `data/reference/ck_migration_v2_to_v3.csv` | Resolves every old v2 key |
| Mislabelled vintages (curated, confirmed only) | `data/reference/vintage_depiction.csv` | A map's boundaries depict a later year than its own label (e.g. Stanford "1981" Assam depicts ~1989) |
| Known geometry gaps (curated, confirmed only) | `data/reference/known_geometry_gaps.csv` | A vintage is missing districts other evidence confirms already existed (e.g. SOI 2025 still shows Mizoram's pre-2018 8 districts) |

Bronze files are committed and must never be modified.

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e . --no-deps   # once
bash scripts/run_all.sh                   # full build + validation gate (~3.5 min)
.venv/bin/python -m pytest tests          # unit tests, golden history, regression baselines (needs a built warehouse)
source .venv/bin/activate && dvc repro    # same DAG; reruns only what changed; hashes in dvc.lock
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
| s01 bronze→silver | Standardize geometry and compute geodesic area/perimeter. Exclude unnamed placeholders. Repair each layer into an exact partition (overlap goes to the enclave). |
| s02 topology | V1 gate: layer self-overlap |
| s03 transition matrix | Overlay adjacent vintages and each vintage against 2025. Classify every part as CORE / TRANSFER / BOUNDARY_DISPLACEMENT / SLIVER. |
| s04 identity | Canonical keys (CKs) by core-territory continuity. Names break ties only when the geometry is ambiguous. |
| s05 lineage | FORMED_FROM / SPLIT_FROM / MERGED_INTO into new CKs; RECONSTITUTED_FROM across a gap (OD-01). Measured transfers between existing CKs. networkx DAG check. |
| s06 ledger | Per-CK, per-window area accounting that closes exactly |
| s07 events | CSV → administrative event grain. A change recorded as both NEW_DISTRICT and SPLIT is one event. |
| s08 linkage | splink Fellegi-Sunter model linking event names to CK records (name + state-lineage evidence) |
| s09 reconciliation | Link successors only within the predecessor's territorial footprint. Partition-exact accounting. MEASURED only when there is one event per window. |
| s10 products | `district_area_admin`, `crosswalk_to_reference`, `district_reference_context` |
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
- `district_evolution/evidence/`: Wikidata snapshot and external audit.

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

- DVC remote and moving bronze out of git history (the `.git` directory is 691 MB). Needs a remote
  and a force-push coordinated with collaborators.
- Zenodo DOI: wired (`.github/workflows/release.yml`, `docs/operations/release.md`); needs the
  repository pushed and switched on at zenodo.org, then a `v3.0.0` tag.
- Independent ground truth: Wikidata (P1365/P1366 lineage, inception, area) is done —
  `outputs/audit/EXTERNAL_AUDIT_REPORT.md`, reproducible from a frozen snapshot via
  `python -m district_evolution.evidence.wikidata_snapshot` + `wikidata_audit`. Census District Handbooks, DataMeet
  boundaries, and gazettes remain open.
- OD-01 decided (3.2.0): a restored district gets a new key and a `RECONSTITUTED_FROM` edge
  (Fatehgarh Sahib, Barnala). `docs/decisions/OD-01_reclassification.md`. Six rename-plus-boundary
  breaks listed there are alias candidates for a future MAJOR version, pending documents.
- Do not keep the working copy in an iCloud-synced folder (e.g. Desktop with iCloud Drive).
  iCloud duplicates rewritten outputs as `<name> 2.<ext>` (V20 now fails on them) and marks
  `.pth` files hidden, which Python 3.13 skips, so `pip install -e .` silently has no effect.
- SOI 2025 lags Mizoram's 2019 districts (Khawzawl, Saitual; Hnahthial is also absent from the
  events compilation), producing 3 `MERGED_INTO` edges into Champhai. Documented, not silently
  fixed: `data/reference/known_geometry_gaps.csv` records the evidence, and `s12` check V19 fails
  WARNING if a future build produces an undocumented `MERGED_INTO` edge of this kind.
