# Validation report — pipeline v4.0.0

**Gate: PASS** — 0 ERROR check(s) failing, 1 WARNING check(s) with findings.

## Checks

| check_id       | severity   |   n_violations | description                                                                                    | detail                                                                                         |
|:---------------|:-----------|---------------:|:-----------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------|
| V1             | ERROR      |              0 | layer self-overlap beyond error threshold                                                      |                                                                                                |
| V3             | ERROR      |              0 | overlay closure broken (excess > closure.error_pct of polygon)                                 |                                                                                                |
| V3             | WARNING    |              0 | overlay closure beyond tolerance (local layer self-overlap, bounded by V1)                     |                                                                                                |
| V4             | ERROR      |              0 | pyproj vs ST_Area_Spheroid differ > 0.01%                                                      |                                                                                                |
| V7             | ERROR      |              0 | CK observed in non-consecutive vintages                                                        |                                                                                                |
| V8             | ERROR      |              0 | MEASURED status inconsistent with events per predecessor-window                                |                                                                                                |
| V9             | ERROR      |              0 | lineage edge into a CK not established in that window (L-3)                                    |                                                                                                |
| V10            | ERROR      |              0 | lineage graph contains a cycle                                                                 |                                                                                                |
| V12            | ERROR      |              0 | event declared transfer exceeds predecessor area                                               |                                                                                                |
| V13            | ERROR      |              0 | active CK count differs from reference-vintage features                                        |                                                                                                |
| V15            | ERROR      |              0 | crosswalk exceeds source or target area                                                        |                                                                                                |
| V16            | WARNING    |              0 | area ledger closure beyond tolerance                                                           |                                                                                                |
| V17            | WARNING    |              1 | overlap repair changed a polygon's area by more than 0.1% (review)                             |                                                                                                |
| V21            | ERROR      |              0 | evidence claim linked to a CK that does not exist                                              |                                                                                                |
| V26            | ERROR      |              0 | crosswalk coverage does not add up (on_reference + unallocated != area, or != crosswalk sum)   |                                                                                                |
| V27            | WARNING    |              0 | a linkage probability class lies near the match threshold (links may flip; see config linkage) |                                                                                                |
| V25            | ERROR      |              0 | a placeholder (unnamed or disputed strip) holds a district identity                            |                                                                                                |
| INFO_LINK      | INFO       |            124 | event participants not linked to a district                                                    |                                                                                                |
| INFO_FOOTPRINT | INFO       |             35 | successor name matched only outside the predecessor's footprint (research queue)               |                                                                                                |
| V4_MAX         | INFO       |              0 | max relative area difference pyproj vs DuckDB (%)                                              | 6.68e-03                                                                                       |
| V18            | WARNING    |              0 | state-map depicting later boundaries than its label, unconfirmed                               |                                                                                                |
| V19            | WARNING    |              0 | MERGED_INTO edge into an undocumented geometry gap (see known_geometry_gaps.csv)               |                                                                                                |
| V20            | ERROR      |              0 | file in a generated-output directory that no stage declares and git does not track             |                                                                                                |
| V22            | INFO       |            376 | open research questions (outputs/evidence/e04_research_queue.csv)                              | CLAIM_CONFLICT: 210; EVENT_NAME_OUTSIDE_FOOTPRINT: 35; EVENT_NAME_UNRESOLVED: 124; MAP_DATE: 7 |
| V23            | WARNING    |              0 | curated finding refers to a research question that no longer exists                            |                                                                                                |
| V24            | ERROR      |              0 | harmonized totals not conserved (outputs/harmonize/h05_report.md)                              |                                                                                                |

V11 data contracts (pandera): 35 / 35 tables pass.

V5 determinism: `outputs/pipeline/s12_output_manifest.csv` holds the sha256 of each of the
47 data outputs declared in `dvc.yaml` (silver, gold, products). Two runs on the same inputs
must produce identical manifests (checked in CI).

## Key figures

|                                                         | value         |
|:--------------------------------------------------------|:--------------|
| canonical keys                                          | 785           |
| active at reference year                                | 733           |
| closed identities                                       | 52            |
| lineage edges                                           | 602           |
| FORMED_FROM / SPLIT_FROM / MERGED_INTO                  | 475 / 125 / 0 |
| lineage edges corroborated by an event                  | 436           |
| measured transfers between existing districts           | 1371          |
| boundary displacement (km2, excluded from transfers)    | 90080         |
| administrative events                                   | 609           |
| of which recorded twice in the CSV (NEW_DISTRICT+SPLIT) | 326           |
| participants linked (incl. same-identity)               | 1596          |
| participants total                                      | 1777          |
| events MEASURED (only event in its window)              | 399           |
| events UNIDENTIFIED (shared window, bound only)         | 189           |

## Event classification from geometry

| spatial_class             |   n |
|:--------------------------|----:|
| CARVE_OUT                 | 344 |
| SAME_IDENTITY             | 110 |
| TRANSFER_BETWEEN_EXISTING |  64 |
| CLEAN_SPLIT               |  37 |
| UNLINKED                  |  33 |
| NO_TRANSFER_OBSERVED      |  15 |
| IDENTITY_CHANGED          |   6 |

## Research queue: successor matched only outside the predecessor's footprint

The events CSV names a successor whose territory did not come from the named
parent, according to the maps. Each case needs a documentary check.

|   year | parent                  | successor                   | matched_elsewhere   | state             |
|-------:|:------------------------|:----------------------------|:--------------------|:------------------|
|   1953 | Warangal                | Khammam                     | Khammam             | Telangana         |
|   1954 | Balipara Frontier Tract | Subansiri Frontier Division | Lower Subansiri     | Arunachal Pradesh |
|   1956 | Jammu And Kashmir       | Srinagar                    | Srinagar            | Jammu And Kashmir |
|   1956 | Jammu And Kashmir       | Udhampur                    | Udhampur            | Jammu And Kashmir |
|   1956 | Jammu And Kashmir       | Baramulla                   | Baramula            | Jammu And Kashmir |
|   1956 | Jammu And Kashmir       | Anantnag                    | Anantnag            | Jammu And Kashmir |
|   1956 | Jammu And Kashmir       | Doda                        | Doda                | Jammu And Kashmir |
|   1956 | Jammu And Kashmir       | Kathua                      | Kathua              | Jammu And Kashmir |
|   1956 | Jammu And Kashmir       | Ladakh                      | Leh(Ladakh)         | Jammu And Kashmir |
|   1957 | Tuensang                | Mokokchung                  | Mokokchung          | Nagaland          |
|   1964 | Mehsana                 | Gandhinagar                 | Gandhinagar         | Gujarat           |
|   1966 | Ambala                  | Ropar                       | Rupnagar            | Punjab            |
|   1972 | Simla                   | Simla                       | Shimla              | Himachal Pradesh  |
|   1979 | Srinagar                | Pulwama                     | Pulwama             | Jammu And Kashmir |
|   1982 | Alappuzha               | Pathanamthitta              | Pattanamthitta      | Kerala            |
|   1982 | Idukki                  | Pathanamthitta              | Pattanamthitta      | Kerala            |
|   1989 | Agra                    | Firozabad                   | Firozabad           | Uttar Pradesh     |
|   1989 | Dibrugarh               | Tinsukia                    | Tinsukia            | Assam             |
|   1989 | Goalpara                | Bongaigaon                  | Bongaigaon          | Assam             |
|   1992 | Hoshiarpur              | Fatehgarh Sahib             | Fatehgarh Sahib     | Punjab            |
|   1993 | Baleshwar               | Sonapur                     | Subarnapur          | Odisha            |
|   1995 | Lalitpur                | Mahoba                      | Mahoba              | Uttar Pradesh     |
|   1997 | Nagapattinam            | Tiruvarur                   | Thiruvarur          | Tamil Nadu        |
|   2005 | Faridabad               | Mewat                       | Mewat               | Haryana           |
|   2006 | Pulwama                 | Kulgam                      | Kulgam              | Jammu And Kashmir |
