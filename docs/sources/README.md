# Source evaluations

Every outside dataset gets one page here **before** it is ingested (WP4 rule). Copy the template,
fill every field from the source's own documentation, and cite where each answer comes from.

```markdown
# <source name>

- Publisher, table, edition:
- Where obtained (URL or delivery), date obtained:
- Licence and terms (quote the clause on reuse and redistribution):
- Coverage: indicators, units, years, states, districts per year:
- Boundaries it reports on: each year's own districts, or apportioned to a fixed year's districts
  (then set `boundary_year` in config/indicators.yaml):
- Agricultural year convention (e.g. 2001-02 recorded as 2001):
- Known gaps and revisions:
- Decision: ingest / do not ingest, and why:
```

For a cropland raster (`docs/operations/cropland_weights.md`) also record: what "cropland" means in it
(net sown area, cropland extent, irrigated area), its reference year(s), resolution and CRS, the
published accuracy, and whether values are a share of each cell or an area (`value`, `scale`).

No source is evaluated yet: the owner will supply the files (decision of 2026-09-29).
