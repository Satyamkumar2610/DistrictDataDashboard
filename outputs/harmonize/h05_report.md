# Harmonization checks — pipeline v4.0.0

Conservation: 9 of 9 indicator-year-method totals conserved (max error 9.31e-10).

Self-check: harmonized mapped area vs `district_reference_context.mapped_km2` over 6597 district-years: max difference 7.28e-12 km² (tolerance 1e-06).

Weight methods available: AREA.

## Method sensitivity

Not measured: every indicator is restated with AREA weights only. A second method needs a cropland raster declared under `weights.cropland` in `config/indicators.yaml` (`docs/operations/cropland_weights.md`).

## Linking of reported values

| indicator       |   LINKED |
|:----------------|---------:|
| mapped_area_km2 |     4605 |
