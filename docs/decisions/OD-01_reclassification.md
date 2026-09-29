# OD-01 — Reclassification: does a restored district keep its key?

Status: **decision needed from the project owner.** Nothing is implemented.
Evidence: `outputs/research/od01_reconstitution_candidates.csv` (pipeline 3.1.0 outputs).

## The question

Architecture v0.3 §26: when a district is reclassified (for example to a tehsil or subdivision)
and later restored as a district, does it keep its canonical key or get a new one?

- **A. Same key**, if the territory is substantially the same and the statistical series was
  continuous.
- **B. New key**, with a `RECONSTITUTED_FROM` lineage edge to the old one.

v0.3 marked this BLOCKING before entity matching was coded.

## What the pipeline does today

Identity follows core territory between *adjacent* maps (s04). A district missing from one map
closes; if it reappears later it gets a new key with no edge back, because lineage (s05) only
links consecutive maps. That is option B without the edge.

## What the data shows

Measured on all 62 closed identities. A "return" means a new identity whose first mapped extent
holds at least half of the closed identity's last extent, and is at least half made of it.

| | identities |
|---|---|
| closed identities | 62 |
| land returns as a later new identity | 34 |
| returns on the very next map (a split or rename, not a reclassification) | 32 |
| returns after at least one map without it | 2 |

The two gap cases:

- **Fatehgarh Sahib** (IND-000186, PEPSU, 1951): absent from the 1961–1991 maps, restored as
  IND-000587 (Punjab), first mapped 2001. All of the 1951 district lies inside the restored one
  (share 1.00; it makes up 0.63 of the new district). This is the one real reclassification case
  in 74 years of maps.
- Jammu & Kashmir 1951 → Leh 2021: the 1951 layer maps a coarse unit whose land later falls
  mostly in Leh. Not a reclassification.

So OD-01 changes the identity of one district. It is not blocking.

## Recommendation: B, with the edge

1. Keep a new key on restoration (today's behaviour). During the gap the district had no
   statistics of its own; its figures were reported inside another district. One key across the
   gap would claim a continuous series that does not exist, and harmonization would inherit that
   claim.
2. Add the missing link: in s05, when a closed identity's territory returns after at least one
   missing map with both shares ≥ 0.5, write a `RECONSTITUTED_FROM` edge (the fourth type
   Architecture v0.3 already defines). Threshold goes in `config/pipeline.yaml` with this memo as
   its rationale. Expected result on current data: one edge (Fatehgarh Sahib).
3. Downgrade OD-01 to non-blocking in `ARCHITECTURE.md`.

Keys do not change, so this is a MINOR version. Option A would renumber keys (MAJOR) and, per
v0.3, needs a Census District Handbook showing the series was continuous.

## Side finding: renames the identity rule does not recognise

Among the 32 next-map returns, six look like the same district under a new spelling or name,
combined with a boundary change that took it below the 0.90 "unchanged" band:

| closed | new | name similarity |
|---|---|---|
| Bametara (2021) | Bemetara (2025) | 0.88 |
| Reasi (2021) | Riasi (2025) | 0.88 |
| Nagore (1951) | Nagaur (1961) | 0.84 |
| Dakshin Kannad (1991) | Dakshina Kannada (2001) | 0.94 (blocked by the qualifier rule) |
| East Nimar (2001) | Khandwa (East Nimar) (2011) | 0.87 |
| Phulabani (1991) | Kandhamal (2001) | 0.44 |

If documents confirm each is the same entity, adding them to `data/reference/name_aliases.csv`
would keep their keys continuous. That renumbers keys, so it is a MAJOR version with a migration
map, and it needs its own decision.
