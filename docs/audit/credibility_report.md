# Credibility report: District Evolution 4.0.0

Date: 2026-10-01. Scope: what the project's own evidence (nine boundary maps, the events
compilation, the pipeline's checks) supports, what 4.0.0 fixed, and the work that would make the
results more credible. Every number comes from `outputs/audit/CREDIBILITY_AUDIT.md` (stage `a02`,
rebuilt on every run), the gate report, or `tests/baselines/v4.0.0.yaml`. Statements from outside
the repository are marked *to verify*.

## Bottom line

The computation is sound and now also stable. The partition, area arithmetic, lineage graph and
harmonization close exactly; two builds are byte-identical; the event linkage no longer swings when
its inputs change slightly. What still limits credibility is the inputs: the 2025 reference map lags
recent reorganisations, the 2011 re-digitisation moves boundaries that did not move on the ground,
some land is missing from some maps, and the events compilation cites no documents. More code cannot
fix those. They need the flagged cases reviewed and a few official documents.

## 1. What holds

| Check | Result |
|---|---|
| Validation gate (s12) | 61 checks, 0 ERROR violations; one warning class (V17, overlap repairs above 0.1% of a polygon) |
| Area, two independent methods (pyproj geodesic vs DuckDB `ST_Area_Spheroid`) | max difference 0.0067% |
| Partition per map, area ledger per district and window | closes exactly (V1, V3, V16) |
| Lineage graph | acyclic; every edge enters an identity established in that window (V9, V10) |
| Harmonization | 9 of 9 conservation and self-checks pass; crosswalk coverage adds up exactly (V26) |
| Reproducibility | two forced rebuilds byte-identical except the DuckDB file (allowed: build timestamp) |
| Event linkage stability | results move < 0.5% when the alias list changes (9% before 4.0.0); V27 warns if a probability class nears the threshold |
| Events measured exactly | 402 of 609 (the only event touching its districts between two maps) |
| Lineage edges an event corroborates | 436 of 602 |

## 2. Fixed in 4.0.0

| Issue | What was wrong | Now |
|---|---|---|
| Placeholders | Nine "Disputed (…)" strips on the SOI 2025 map (50.3 km²) had keys and counted as districts | Excluded in s01; 733 active districts (was 742); V25 guards it |
| Districts that grow | A district that stayed whole, kept its name and gained more land than it had got a new identity (Una 1991, Chennai 2021, …, 10 cases) | Keeps its identity (OD-02); 785 identities (was 804) |
| Event linkage on a knife-edge | "Exact name, compatible state" scored 0.506 against a 0.50 threshold; adding correct aliases flipped 99 unrelated links | The event's state is also compared with the district's present-day state; threshold in the gap between classes (0.52); V27 |
| Wrong links | Raigarh 1998 linked to Raygad (Maharashtra); Manipur East and West swapped | Corrected by the above; 1,103 links (was 1,094), 124 unresolved (was 132) |
| Unrecorded names | 152 name changes neither matched nor recorded | 55 added with two kinds of evidence each; 81 remain for a person |
| Map lag not recorded | Andhra Pradesh 2022 and Rajasthan 2023 are on no map | Recorded in `known_geometry_gaps.csv` as EVENTS_ONLY |
| Unallocatable land invisible | Crosswalk shares below 1 were not surfaced | `crosswalk_coverage` product, released |
| No measured error rate | — | Fixed review sample (30 lineage edges, 30 crosswalk rows) scored from `review_outcomes.csv` |
| Stale build script | `run_all.sh` ran 12 of 25 stages and would fail on a clean checkout | CLI derives the order from dvc.yaml |
| Latent crashes | V19 and the harmonization engine crashed on empty inputs; `zip()` could silently drop rows | Fixed; every `zip()` strict |
| False explanation | Alirajpur's area gap "explained" by a 4.4 km² disputed strip | An open question again |
| Wikidata in the release | Crowd-sourced claims shown as evidence | Internal gate check only |

## 3. What still limits credibility

Ranked by how much each affects results people will use.

### 3.1 The 2025 reference map lags the ground

"2025 districts" means the SOI 2025 map's districts. The events compilation records reorganisations
the map does not show: Andhra Pradesh's 2022 reorganisation (24 successors on no map; 13 districts on
the 2011, 2021 and 2025 maps), Rajasthan's 2023 districts (16 successors on no map), and Mizoram's 2019
districts (11 on the 2021 map, 8 on the 2025 map). The 2025 map has fewer districts (733) than the
2021 map (735). Statistics restated "onto 2025 districts" in these states land on pre-reorganisation
units.

### 3.2 The 2011 re-digitisation

Land that stays put but is drawn along a different line is about 200–270 km² per window up to 2001.
It is **44,458 km²** (2001→2011) and **40,503 km²** (2011→2021), 1.3–1.4% of the country. The
pipeline classifies it as displacement, not transfer, so it creates no lineage, but crosswalk weights
along those lines carry the error.

### 3.3 Land the 2025 districts do not cover

`crosswalk_coverage` measures it per district. Summed per map, earlier districts' land that lies in no
2025 district is 13,800–15,300 km² for every map from 1951 to 2011 and 8,582 km² for 2021; between 22
and 48 districts per map have less than 99% of their area covered. Separately, Jammu & Kashmir is
partly replaced by an unnamed polygon on the 1961–2011 maps (80,520 km²; 108,672 km² on the 2011
map), which the pipeline excludes. Statistics for the uncovered land cannot be restated.

### 3.4 Edition artefacts

- **79 flows** move at least 100 km² between two districts and later move back
  (`credibility_return_flows.csv`). Udaipur and Ajmer swap the same 1,354 km² parcel in each of the
  four windows from 1951 to 1991; Ladakh and Kargil exchange 1,756 km² (2001–2011) and 1,172 km² back;
  Kangra gives Una 1,169 km² (1981–1991) and gets 564 km² back (2001–2011). Una is now one identity
  throughout (OD-02), but these flows still enter lineage and crosswalks.
- **5 districts** whose area jumps by 25% or more and later returns within 5%: Calcutta (194 → 99 →
  185 km², 2011–2025), Ernakulam, Pithoragarh, and Aizawl and Champhai (both the Mizoram map lag).
- Solan's identity (IND-000187) starts as Kandaghat on the 1951 map and is labelled "Shimla" on the
  1961 map. *To verify:* Solan district was created in 1972.

### 3.5 The events compilation cites no documents

All 609 events cite one or two of **3 file names**; **0** cite a gazette, notification or census
handbook. 189 events share a window with another event touching the same district, so their km²
cannot be separated, and 21 have no accounting at all.

### 3.6 Names

81 consecutive-map name changes in 61 identities are still unrecorded (`credibility_name_changes.csv`):
renames the events compilation does not record (Balipara Frontier Tract → Kameng), and spellings the
conservative rule does not catch (Sibsagar/Sivasagar, Bhir/Beed). They need a person with sources.

### 3.7 No one else can check the results yet

The 1951–2021 maps may not be redistributed (`docs/decisions/licensing.md`), so a third party cannot
rerun the pipeline.

## 4. Work plan

### A. Needs nothing from outside

| # | Work | Status |
|---|---|---|
| A1 | Record the Andhra Pradesh and Rajasthan map lag; say what "2025 districts" means | **Done** (EVENTS_ONLY rows; this report, the changelog) |
| A2 | Classify the 79 material return flows and 5 reversals as real change or edition artefact | **Open**: needs a person with the maps; the audit lists them in order |
| A3 | Decide how identity treats artefacts | **Done** for growth (OD-02). Solan remains to verify |
| A4 | Record unrecorded names | **Partly done**: 55 aliases added by rule; unrecorded changes 152 → 81, which need a person |
| A5 | Publish coverage | **Done** (`crosswalk_coverage`) |
| A6 | Expert review sample | **Ready**: 60 items in `outputs/audit/review_sample.csv`; record verdicts in `data/reference/review_outcomes.csv` |

### B. Needs documents you supply

| # | Work | Why it matters |
|---|---|---|
| B1 | Census District Handbooks (1951–2011): official district areas | The one area comparison that does not rely on the maps being tested |
| B2 | Gazette notifications, starting with the 124 event names no map matches and the 189 events in shared windows | Citations for events; exact dates that can separate shared windows; turns EVENTS_ONLY gaps into CONFIRMED |
| B3 | The declaration accepted when downloading SOI 2025 | Settles the reference map's terms |

### C. Needs a decision or an outside party

| # | Work | Why it matters |
|---|---|---|
| C1 | Permission from ML InfoMap for the 1951–2021 layers (at least for derived products) | Lets others reproduce and check the results |
| C2 | A newer or openly licensed reference map, if one exists, evaluated per `docs/sources/README.md` | Fixes the map lag at the source |

Suggested order: A6 (an afternoon: gives the first measured error rate), then B1, the single largest
gain in credibility, then A2 with the maps and B2 together.

## 5. Reproduce

```bash
source .venv/bin/activate
python -m district_evolution build && python -m district_evolution validate
cat outputs/audit/CREDIBILITY_AUDIT.md
```
