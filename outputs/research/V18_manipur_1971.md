# V18 — Manipur 1971: not a mislabelled map

Status: **resolved (check error), 2026-09-29.** No `vintage_depiction.csv` row is added.

## The flag

Pipeline v3.0.0 raised WARNING V18 for Manipur 1971: 4 of its 5 new districts (Churachandpur,
Senapati, Tamenglong, Ukhrul) appeared on a map dated before their creation year (1981 in the
events compilation). V18 exists to catch map layers that depict later boundaries than their label,
as the Stanford "1981" Assam layer does (confirmed, depicts ~1989).

## Evidence

Silver geometry, Manipur, by map (name as the map writes it, geodesic km²):

| 1961 | 1971 | 1981 | 1991 |
|---|---|---|---|
| Manipur 22,478 | Manipur Central 5,459 | Imphal 2,227 + Chandel 3,232 | Imphal 1,061, Bishnupur 618, Thoubal 547, Chandel 3,232 |
| | Manipur East 4,530 | Ukhrul 4,530 | Ukhrul 4,530 |
| | Manipur North 3,522 | Senapati 3,522 | Senapati 3,522 |
| | Manipur South 4,860 | Churachandpur 4,860 | Churachandpur 4,860 |
| | Manipur West 4,108 | Tamenglong 4,108 | Tamenglong 4,108 |

Events compilation (`data/bronze/events/district_evolution_master.csv`):
- 1969, NEW_DISTRICT and SPLIT: Manipur → Manipur Central, East, North, South, West.
- 1981, **RENAME**: Manipur South → Churachandpur, Manipur North → Senapati, Manipur West →
  Tamenglong, Manipur East → Ukhrul (and Tengnoupal → Chandel).
- 1983: Imphal, Bishnupur, Thoubal split from Manipur Central.

The 1971 layer therefore shows exactly the five districts created in 1969, under their 1969
names. The 1981 layer shows the same four polygons, identical to the km², under their 1981 names.
The map is consistent with its label.

## Cause

`shown_before_creation` (V18 and the external audit) took the earliest year a name appears as
`child_district` in any event row. A RENAME row, or a SPLIT row whose child is the continuing
parent, was read as a creation. The four renamed districts were "created" in 1981 by that rule.

## Fix (pipeline 3.1.0)

Creation years come from creation rows only (not RENAME, not child = parent). A renamed district
inherits the creation year of the name it was renamed from, followed back through the rename
chain. A creation dated at or after an identity's closure is ignored as a later homonym (Siang:
renamed 1961, closed after 1971; a different Siang district was created in 2015).
`tests/test_map_dates.py` pins all three rules.

Effect: districts shown before their creation year fall from 20 to 7, and V18 flags no state-map.
Resolved among the 13: Manipur ×4, Dima Hasao (North Cachar Hills, 1970), Erode, West Singhbhum,
Sri Muktsar Sahib, Amroha, and four with no creation row at all (Baramula, Nagaur, Dhubri,
Bhadohi, whose only rows are renames or continuations).

## Remaining 7 (below the V18 threshold; research queue)

| key | district | state | first map | creation (CSV) |
|---|---|---|---|---|
| IND-000318 | Rupnagar | Punjab | 1961 | 1966 |
| IND-000327 | Punch | Jammu and Kashmir | 1961 | 1968 |
| IND-000342 | Lower Subansiri | Arunachal Pradesh | 1961 | 1987 |
| IND-000376 | East Siang | Arunachal Pradesh | 1981 | 1989 |
| IND-000377 | Upper Subansiri | Arunachal Pradesh | 1981 | 1987 |
| IND-000427 | Imphal | Manipur | 1981 | 1983 |
| IND-000597 | Ariyalur | Tamil Nadu | 2001 | 2007 |

Each needs a documentary check (gazette or Census District Handbook): either the map layer is
early for that state, or the compilation's date or name is wrong. Arunachal Pradesh 1981 has 2 of 6.
