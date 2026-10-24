# Validation report — pipeline v4.1.0

**Gate: PASS** — 0 ERROR check(s) failing, 0 WARNING check(s) with findings.

## Checks

| check_id       | severity   |   n_violations | description                                                                                    | detail                                                                                        |
|:---------------|:-----------|---------------:|:-----------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------|
| V1             | ERROR      |              0 | layer self-overlap beyond error threshold                                                      |                                                                                               |
| V3             | ERROR      |              0 | overlay closure broken (excess > closure.error_pct of polygon)                                 |                                                                                               |
| V3             | WARNING    |              0 | overlay closure beyond tolerance (local layer self-overlap, bounded by V1)                     |                                                                                               |
| V4             | ERROR      |              0 | pyproj vs ST_Area_Spheroid differ > 0.01%                                                      |                                                                                               |
| V7             | ERROR      |              0 | CK observed in non-consecutive vintages                                                        |                                                                                               |
| V8             | ERROR      |              0 | MEASURED status inconsistent with events per predecessor-window                                |                                                                                               |
| V9             | ERROR      |              0 | lineage edge into a CK not established in that window (L-3)                                    |                                                                                               |
| V10            | ERROR      |              0 | lineage graph contains a cycle                                                                 |                                                                                               |
| V12            | ERROR      |              0 | event declared transfer exceeds predecessor area                                               |                                                                                               |
| V13            | ERROR      |              0 | active CK count differs from reference-vintage features                                        |                                                                                               |
| V15            | ERROR      |              0 | crosswalk exceeds source or target area                                                        |                                                                                               |
| V16            | WARNING    |              0 | area ledger closure beyond tolerance                                                           |                                                                                               |
| V17            | WARNING    |              0 | overlap repair changed a polygon's area by more than 0.1% (review; reviewed_exceptions.csv)    |                                                                                               |
| V21            | ERROR      |              0 | evidence claim linked to a CK that does not exist                                              |                                                                                               |
| V26            | ERROR      |              0 | crosswalk coverage does not add up (on_reference + unallocated != area, or != crosswalk sum)   |                                                                                               |
| V27            | WARNING    |              0 | a linkage probability class lies near the match threshold (links may flip; see config linkage) |                                                                                               |
| V25            | ERROR      |              0 | a placeholder (unnamed or disputed strip) holds a district identity                            |                                                                                               |
| INFO_LINK      | INFO       |             93 | event participants not linked to a district                                                    |                                                                                               |
| INFO_FOOTPRINT | INFO       |             27 | successor name matched only outside the predecessor's footprint (research queue)               |                                                                                               |
| V4_MAX         | INFO       |              0 | max relative area difference pyproj vs DuckDB (%)                                              | 6.68e-03                                                                                      |
| V18            | WARNING    |              0 | state-map depicting later boundaries than its label, unconfirmed                               |                                                                                               |
| V19            | WARNING    |              0 | MERGED_INTO edge into an undocumented geometry gap (see known_geometry_gaps.csv)               |                                                                                               |
| V20            | ERROR      |              0 | file in a generated-output directory that no stage declares and git does not track             |                                                                                               |
| V22            | INFO       |            334 | open research questions (outputs/evidence/e04_research_queue.csv)                              | CLAIM_CONFLICT: 208; EVENT_NAME_OUTSIDE_FOOTPRINT: 27; EVENT_NAME_UNRESOLVED: 93; MAP_DATE: 6 |
| V23            | WARNING    |              0 | curated finding refers to a research question that no longer exists                            |                                                                                               |
| V24            | ERROR      |              0 | harmonized totals not conserved (outputs/harmonize/h05_report.md)                              |                                                                                               |

V11 data contracts (pandera): 37 / 37 tables pass.

V5 determinism: `outputs/pipeline/s12_output_manifest.csv` holds the sha256 of each of the
49 data outputs declared in `dvc.yaml` (silver, gold, products). Two runs on the same inputs
must produce identical manifests (checked in CI).

## Key figures

|                                                         | value         |
|:--------------------------------------------------------|:--------------|
| canonical keys                                          | 785           |
| active at reference year                                | 733           |
| closed identities                                       | 52            |
| lineage edges                                           | 602           |
| FORMED_FROM / SPLIT_FROM / MERGED_INTO                  | 475 / 125 / 0 |
| lineage edges corroborated by an event                  | 457           |
| measured transfers between existing districts           | 1371          |
| boundary displacement (km2, excluded from transfers)    | 90080         |
| administrative events                                   | 609           |
| of which recorded twice in the CSV (NEW_DISTRICT+SPLIT) | 326           |
| participants linked (incl. same-identity)               | 1633          |
| participants total                                      | 1772          |
| events MEASURED (only event in its window)              | 402           |
| events UNIDENTIFIED (shared window, bound only)         | 192           |

## Event classification from geometry

| spatial_class             |   n |
|:--------------------------|----:|
| CARVE_OUT                 | 355 |
| SAME_IDENTITY             | 112 |
| TRANSFER_BETWEEN_EXISTING |  58 |
| CLEAN_SPLIT               |  39 |
| UNLINKED                  |  25 |
| NO_TRANSFER_OBSERVED      |  14 |
| IDENTITY_CHANGED          |   6 |

## Research queue: successor matched only outside the predecessor's footprint

The events CSV names a successor whose territory did not come from the named
parent, according to the maps. Each case needs a documentary check.

|   year | parent             | successor          | matched_elsewhere   | state             |
|-------:|:-------------------|:-------------------|:--------------------|:------------------|
|   1956 | Nimar              | East Nimar         | East Nimar          | Madhya Pradesh    |
|   1957 | Tuensang           | Mokokchung         | Mokokchung          | Nagaland          |
|   1964 | Mehsana            | Gandhinagar        | Gandhinagar         | Gujarat           |
|   1966 | Ambala             | Chandigarh         | Chandigarh          | Chandigarh        |
|   1966 | Ambala             | Ropar              | Rupnagar            | Punjab            |
|   1972 | Simla              | Simla              | Shimla              | Himachal Pradesh  |
|   1979 | Srinagar           | Pulwama            | Pulwama             | Jammu And Kashmir |
|   1982 | Alappuzha          | Pathanamthitta     | Pattanamthitta      | Kerala            |
|   1982 | Idukki             | Pathanamthitta     | Pattanamthitta      | Kerala            |
|   1989 | Agra               | Firozabad          | Firozabad           | Uttar Pradesh     |
|   1989 | Dibrugarh          | Tinsukia           | Tinsukia            | Assam             |
|   1989 | Goalpara           | Bongaigaon         | Bongaigaon          | Assam             |
|   1989 | West Siang         | East Siang         | East Siang          | Arunachal Pradesh |
|   1992 | Hoshiarpur         | Fatehgarh Sahib    | Fatehgarh Sahib     | Punjab            |
|   1993 | Baleshwar          | Sonapur            | Subarnapur          | Odisha            |
|   1995 | Lalitpur           | Mahoba             | Mahoba              | Uttar Pradesh     |
|   1997 | Nagapattinam       | Tiruvarur          | Thiruvarur          | Tamil Nadu        |
|   2005 | Faridabad          | Mewat              | Mewat               | Haryana           |
|   2006 | Pulwama            | Kulgam             | Kulgam              | Jammu And Kashmir |
|   2007 | Perambalur         | Ariyalur           | Ariyalur            | Tamil Nadu        |
|   2007 | Tiruchchirappalli  | Ariyalur           | Ariyalur            | Tamil Nadu        |
|   2008 | Gurgaon            | Palwal             | Palwal              | Haryana           |
|   2012 | East Jaintia Hills | West Jaintia Hills | West Jaintia Hills  | Meghalaya         |
|   2013 | Jamnagar           | Morbi              | Morbi               | Gujarat           |
|   2016 | Karimnagar         | Medak              | Medak               | Telangana         |
