# External audit — v3 outputs vs Wikidata (snapshot 2026-09-23)

Wikidata is independent of the Stanford/SOI maps and of the events CSV, so
agreement here is external corroboration. It is crowd-maintained: of its district
area claims, only 3 of those matched carry a source reference, and almost none
carry a date. A disagreement is therefore a lead to check, not proof of our error.

## 1. Coverage (reference year 2025)

Current Wikidata district items with coordinates: 779.

| verdict                    |   n |
|:---------------------------|----:|
| GEOMETRY_AND_NAME          | 624 |
| GEOMETRY_ONLY_NAME_DIFFERS | 154 |
| NO_POLYGON                 |   1 |

Our 733 active districts matched to a Wikidata item by geometry and name:
**624** (85.1%).
Not matched: 109. Wikidata items whose point falls in one of our districts but whose
name differs are listed in `wikidata_match.csv`. They are mostly districts formed after the SOI
2025 map, or outdated coordinates.

## 2. Area (our 2025 geodesic area vs Wikidata)

Compared: 565 districts. Median absolute difference: 1.61%.

| verdict                           |   n |
|:----------------------------------|----:|
| AGREE_WITHIN_2PCT                 | 300 |
| MINOR_2_TO_10PCT                  | 124 |
| DISTRICT_REORGANISED_AFTER_2011   |  48 |
| UNEXPLAINED_OVER_10PCT            |  47 |
| WIKIDATA_MATCHES_OUR_EARLIER_AREA |  40 |
| WIKIDATA_MAGNITUDE_ERROR          |   6 |

How to read the verdicts:
- `WIKIDATA_MAGNITUDE_ERROR`: our area is within 2% of Wikidata's figure times a power of ten.
  For example, East Godavari is listed as 10.8 km² for 10,800. This is an entry error in Wikidata.
- `WIKIDATA_MATCHES_OUR_EARLIER_AREA`: Wikidata's figure agrees within 2% with **our own area
  for the same district on an earlier map** (`matches_our_year` in the CSV). It is a stale,
  pre-reorganisation figure. This supports both our geometry and our identity chain: the same
  district, followed through time, had exactly that area before it was divided.
- `DISTRICT_REORGANISED_AFTER_2011`: our lineage records a change to this district after 2011,
  so an undated Wikidata figure may predate it.

Share of compared districts that agree or whose difference is explained:
**91.7%**.

Unexplained differences over 10% (47). These are leads to check against official figures:

| label                        | our_name       |   wd_area_km2 |   our_area_2025_km2 |   our_area_2011_km2 |   rel_diff_2025 |
|:-----------------------------|:---------------|--------------:|--------------------:|--------------------:|----------------:|
| Harda district               | Harda          |         26    |            3341.42  |            3316.49  |         127.516 |
| Srinagar district            | Srinagar       |       1979    |             281.804 |             477.218 |          -0.858 |
| Shravasti district           | Shrawasti      |       1126    |            1931.14  |            1953.7   |           0.715 |
| Faridabad district           | Faridabad      |       2151    |             743.339 |             751.944 |          -0.654 |
| Chirang district             | Chirang        |       1169.9  |            1912.79  |            1931.75  |           0.635 |
| Kaimur district              | Kaimur         |       8268    |            3369.55  |            3338.54  |          -0.592 |
| Kota district                | Kota           |      12436    |            5089.69  |            5101.02  |          -0.591 |
| Bongaigaon district          | Bongaigaon     |       2510    |            1118.1   |            1061.85  |          -0.555 |
| Alirajpur district           | Alirajpur      |       2165    |            3332.52  |            3317.19  |           0.539 |
| Bijapur District             | Bijapur        |       6555    |            9248.37  |            8191.76  |           0.411 |
| Sahebganj district           | Sahibganj      |       1599    |            2191.23  |            1915.82  |           0.37  |
| Sri Ganganagar district      | Ganganagar     |       7984    |           10930.9   |           10443.8   |           0.369 |
| Coimbatore district          | Coimbatore     |       7469    |            4720.06  |            4735.16  |          -0.368 |
| Kamrup Metropolitan district | Kamrup Metro   |       1527.84 |             971.979 |             982.752 |          -0.364 |
| Pulwama district             | Pulwama        |       1398    |             897.105 |             896.152 |          -0.358 |
| Tiruchirappalli district     | Tiruchirapalli |       6810    |            4492.87  |            4461.77  |          -0.34  |
| West Kameng district         | West Kameng    |       7422    |            4916.45  |            4961.97  |          -0.338 |
| Tiruvannamalai district      | Tiruvannamalai |       4621    |            6178.5   |            6194.7   |           0.337 |
| Lakhimpur district           | Lakhimpur      |       2277    |            2996.07  |            2868.75  |           0.316 |
| Chittorgarh district         | Chittaurgarh   |      10856    |            7814.95  |            7743.74  |          -0.28  |
| Zunheboto district           | Zunheboto      |       1255    |            1575.2   |            1537.34  |           0.255 |
| Dhemaji district             | Dhemaji        |       3237    |            2478.99  |            2577.94  |          -0.234 |
| Jammu district               | Jammu          |       3097    |            2411.61  |            2253     |          -0.221 |
| Nagpur district              | Nagpur         |       8253    |            9897.32  |            9894.62  |           0.199 |
| Udaipur district             | Udaipur        |      14621    |           11712.2   |           11682.8   |          -0.199 |
| Kulgam district              | Kulgam         |       1067    |            1265.72  |            1165.83  |           0.186 |
| Nuh district                 | Mewat          |       1860    |            1515.06  |            1531.02  |          -0.185 |
| Rudraprayag district         | Rudraprayag    |       2439    |            1987.94  |            1985.48  |          -0.185 |
| Nandurbar district           | Nandurbar      |       5035    |            5955.6   |            5905.83  |           0.183 |
| Ganderbal district           | Ganderbal      |       1979    |            1620.89  |            1286.54  |          -0.181 |

## 3. Formation year (Wikidata inception vs the map where our CK first appears)

Compared: 141 districts with inception ≥ 1947.

| verdict                     |   n |
|:----------------------------|----:|
| CONSISTENT                  | 125 |
| CONSISTENT_WITH_ONE_MAP_LAG |  10 |
| OURS_EARLIER_THAN_INCEPTION |   4 |
| OURS_LATER_THAN_INCEPTION   |   2 |

## 4. Lineage (Wikidata separated-from / replaces / replaced-by)

Wikidata records only 32 such links for Indian districts, so this is a spot check, not
coverage.

| verdict                   |   n |
|:--------------------------|----:|
| NOT_CHECKABLE             |  16 |
| CONFIRMED_BY_LINEAGE_EDGE |  16 |

## 5. Map dates: does a map show a district before it was created?

For each new district we take its creation year from the events compilation. That source is
independent of the maps. Where Wikidata also has an inception year, it is used to corroborate.
Dates confirmed in `data/reference/vintage_depiction.csv` are applied first. Of 390 new
districts with a recorded creation year, **7** still appear on a
map depicting a date before that year.

| state             |   first_map |   new_on_map |   wikidata_confirms |   named_new_districts |
|:------------------|------------:|-------------:|--------------------:|----------------------:|
| Arunachal Pradesh |        1981 |            2 |                   0 |                     6 |
| Arunachal Pradesh |        1961 |            1 |                   0 |                     1 |
| Jammu And Kashmir |        1961 |            1 |                   0 |                     7 |
| Manipur           |        1981 |            1 |                   0 |                     2 |
| Punjab            |        1961 |            1 |                   0 |                     1 |
| Tamil Nadu        |        2001 |            1 |                   0 |                     7 |

When the cases concentrate in one state-map, the map layer is the likely problem, not scattered
event errors. Confirmed case: the Stanford "1981" Assam layer has the same 23 districts as its
1991 layer, and 13 of its 14 new districts were created 1983–1989. Wikidata's inception years
agree with the events compilation there. The pipeline therefore treats that layer as depicting
1989, so the table above no longer shows it. Any remaining concentration is flagged by s12
check V18 until a second source confirms or rejects it.

## Files

`outputs/audit/wikidata_match.csv`, `area_audit.csv`, `formation_audit.csv`, `lineage_audit.csv`,
`map_date_audit.csv`.
