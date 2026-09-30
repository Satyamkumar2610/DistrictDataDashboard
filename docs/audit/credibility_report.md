# Credibility report: District Evolution 4.0.0

Date: 2026-09-30. Scope: what the project's own evidence (nine boundary maps, the events
compilation, the pipeline's checks) supports, what this round fixed, and the work that would make
the results more credible. Every number comes from `outputs/audit/CREDIBILITY_AUDIT.md` (stage
`a02`, rebuilt on every run) or the gate report. Statements from outside the repository are marked
*to verify*.

## Bottom line

The computation is sound. The partition, the area arithmetic, the lineage graph and the
harmonization all close exactly, and two builds are byte-identical. What limits credibility is the
inputs: the 2025 reference map lags recent reorganisations, the 2011 re-digitisation moves
boundaries that did not move on the ground, some land is missing from some maps, and the events
compilation cites no documents. None of this can be fixed by more code. It needs review of the
flagged cases and a few official documents.

## 1. What holds

| Check | Result |
|---|---|
| Validation gate (s12) | 0 ERROR violations; one warning class (V17, overlap repairs above 0.1% of a polygon, listed for review) |
| Area, two independent methods (pyproj geodesic vs DuckDB `ST_Area_Spheroid`) | max difference 0.0067% |
| Partition per map, area ledger per district and window | closes exactly (V1, V3, V16) |
| Lineage graph | acyclic; every edge enters an identity established in that window (V9, V10) |
| Harmonization | 9 of 9 conservation and self-checks pass: restating each map's own areas reproduces the crosswalk |
| Reproducibility | two forced rebuilds byte-identical except the DuckDB file (allowed; build timestamp) |
| Events measured exactly | 401 of 609 events (the only event touching its districts between two maps) |

## 2. Fixed in this round (4.0.0)

- **Placeholders.** Nine "Disputed (…)" strips on the SOI 2025 map (0.7–14.5 km², 50.3 km² in
  all) had district keys and counted as active districts. They are now excluded like the unnamed
  J&K polygons; a new ERROR invariant (V25) stops it recurring. Active districts on the 2025 map:
  **733** (was 742). Three real districts were renumbered (Riasi, Champhai, Kolkata); every old key
  resolves through `data/reference/ck_migration_v3_to_v4.csv`.
- **A false explanation removed.** Alirajpur's area gap with Wikidata had been "explained" as a
  post-2011 reorganisation only because it lost 4.4 km² to a disputed strip. It is an open question
  again.
- **Wikidata is internal.** It still runs as a gate check but is not released, served or shown.
  Validation now rests on the project's own evidence, which this report measures.
- **API.** Mistyped `/api/...` URLs returned the web page with status 200; they are now JSON 404s.

## 3. What limits credibility

Ranked by how much they affect the results people will use.

### 3.1 The 2025 reference map lags the ground

The harmonization target is "the 2025 districts", which in practice means the SOI 2025 map. The
events compilation records reorganisations that the map does not show:

| State | Evidence in this repository |
|---|---|
| Andhra Pradesh | 24 successor districts from its 2022 reorganisation are on no map; the state has 13 districts on the 2011, 2021 and 2025 maps |
| Rajasthan | 16 successors on no map, the latest from 2023; 33 districts on the 2011, 2021 and 2025 maps |
| Mizoram | 11 districts on the 2021 map, 8 on the 2025 map (already documented, `known_geometry_gaps.csv`) |

The 2025 map has **fewer** districts (733) than the 2021 map (735). Anyone restating data "onto
2025 districts" for Andhra Pradesh or Rajasthan is restating onto the pre-reorganisation units.

### 3.2 The 2011 re-digitisation

Between consecutive maps, land that stays put but is drawn along a different line ("boundary
displacement") is about 200–270 km² per window up to 2001. It jumps to **44,458 km²** (2001→2011)
and **40,503 km²** (2011→2021), 1.3–1.4% of the country, with 3,808 and 4,962 km² of slivers. The
2011 edition redrew lines that did not move. The pipeline classifies this as displacement, not
transfer, so it creates no lineage, but the crosswalk weights of districts along those lines carry
the error.

### 3.3 Land missing from some maps

| Map | Mapped km² | Land not on the next map, km² |
|---|---|---|
| 1951 | 3,268,503 | 80,533 (to 1961) |
| 1961–2001 | ~3,187,700 | 16–289 per window |
| 2011 | 3,156,069 | 8,852 (to 2021); 41,947 was lost from 2001 |
| 2021 / 2025 | 3,269,978 / 3,270,001 | 5,176 (2021 to 2025) |

Most of it is Jammu & Kashmir: the maps from 1961 to 2011 replace part of the state with an
unnamed polygon (80,520 km², 108,672 km² on the 2011 map), which the pipeline excludes. Statistics
reported for those areas cannot be allocated, and crosswalk shares for the districts around them
sum to less than 1. That is correct behaviour, but users need to know it.

### 3.4 Edition artefacts that may have created identities or lineage

- **81 flows** move at least 100 km² from one district to another and later move back
  (`credibility_return_flows.csv`). Examples: Udaipur and Ajmer swap the same 1,354 km² parcel in
  each of the four windows from 1951 to 1991, and 602 km² again by 2001; Ladakh and Kargil exchange 1,756 km² (2001–2011) and
  1,172 km² back; Kangra gives Una 1,169 km² (1981–1991) and gets 564 km² back (2001–2011).
- **3 districts** whose area jumps by 25% or more and later returns within 5%: Ernakulam,
  Pithoragarh, Aizawl (`credibility_area_reversals.csv`).
- Consequences in the results: Una is a new identity from 1991 (IND-000468; 945 km² in 1981,
  2,114 km² in 1991 and 2001, 1,543–1,560 km² from 2011). Solan's identity (IND-000187) starts as
  Kandaghat on the 1951 map and is labelled "Shimla" on the 1961 map. *To verify:* Una and Solan
  districts were both created in 1972, with no later change to Una's boundary with Kangra.

### 3.5 The events compilation cites no documents

All 609 events cite one or two of **3 file names** (Google Drive exports); **0** cite a gazette,
notification or census handbook. 186 events share a window with another event touching the same
district, so their km² cannot be separated, and 22 have no accounting at all. 104 successor names
match no district on any map (Andhra Pradesh and Rajasthan above, plus older cases in Arunachal
Pradesh, Sikkim and Tamil Nadu).

### 3.6 Names

152 consecutive-map name changes in 107 identities neither match by similarity nor appear in
`name_aliases.csv`. Most are spellings (Ahmadnagar/Ahmednagar); some are renames (Balipara
Frontier Tract/Kameng). Geometry decides identity, so these do not change keys. They weaken the
name tie-break and the event linkage.

### 3.7 No one else can check the results yet

The 1951–2021 maps may not be redistributed (`docs/decisions/licensing.md`), so a third party
cannot rerun the pipeline. For outside readers, credibility currently rests on the documentation
and the published checks.

## 4. Work plan

### A. Needs nothing from outside (can start now)

| # | Work | Why it matters | Size |
|---|---|---|---|
| A1 | Record Andhra Pradesh 2022 and Rajasthan 2023 in `known_geometry_gaps.csv`, with the event rows as evidence, and state in every product that "2025 districts" means the SOI 2025 map | Users stop assuming the target is current | small |
| A2 | Review the 81 material return flows and 3 area reversals; record each as a real change or an edition artefact in a curated table | Separates true lineage from digitisation; basis for A3 | medium |
| A3 | Decide how the identity rule treats confirmed artefacts (Una 1991 re-key, Solan chain). Any change renumbers keys, so it is a MAJOR version | Removes spurious identities and edges | medium |
| A4 | Add the 152 unrecorded spellings and renames to `name_aliases.csv` (same-entity only) | Stronger name tie-break and event linkage | small |
| A5 | Publish the coverage table (section 3.3) with each release, and flag crosswalk rows whose source sums below 1 | Users see where statistics cannot be allocated | small |
| A6 | Draw a fixed, seeded sample of about 30 lineage edges and 30 crosswalk rows for expert review, with outcomes recorded as findings | A measured error rate instead of none | small to set up |

### B. Needs documents you supply

| # | Work | Why it matters |
|---|---|---|
| B1 | Census District Handbooks (1951–2011): official district areas per census | The one area comparison that is not circular. Tests the maps themselves |
| B2 | Gazette notifications for events: start with the 104 unmapped successors and the 186 events in shared windows | Replaces file IDs with citations; dates events precisely enough to separate some shared windows |
| B3 | The declaration accepted when downloading SOI 2025 | Settles the reference map's terms |

### C. Needs a decision or an outside party

| # | Work | Why it matters |
|---|---|---|
| C1 | Permission from ML InfoMap for the 1951–2021 layers (at least for derived products) | Lets others reproduce and check the results |
| C2 | A newer or openly licensed reference map, if one exists, evaluated per `docs/sources/README.md` | Fixes the map lag at the source |

Suggested order: A1 and A5 first (days, and they change how people read the results), then A2 to
A4 together, then B1, the single largest gain in credibility.

## 5. Reproduce

```bash
source .venv/bin/activate && PYTHONPATH=. dvc repro     # rebuilds everything, including a02
cat outputs/audit/CREDIBILITY_AUDIT.md                  # the measured numbers behind this report
```

The full lists are in `outputs/audit/credibility_*.csv`. The thresholds are in `config/pipeline.yaml`
under `audit`.
