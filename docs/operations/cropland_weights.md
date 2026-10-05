# Cropland weights

Area weights share a district's crop total in proportion to land. For 1951 Kangra, that sends 46% of
any crop total to today's Lahaul & Spiti, a high cold desert. The `CROPLAND` weight method shares the
total in proportion to where the district's cropland lies instead. It needs a cropland raster, which
the owner supplies. Until one is declared, the pipeline restates with `AREA` only, and the tables
below stay empty.

## What it computes

For each map that a declared statistic uses, stage h02 overlays the map on the 2025 map and sums the
raster over the result (`district_evolution/harmonize/cropland.py`):

```
weight(s -> t) = cropland in s and t / cropland in s
```

- **Cells:** each raster cell belongs to the source district its centre lies in, and to the one 2025
  district its centre lies in, if any. Cropland is therefore split into non-overlapping pieces, the
  way land is.
- **Leftover cropland:** cropland in `s` that lies in no 2025 district, or only in a sliver overlap
  that the crosswalk leaves out, stays in the denominator. A source's weights sum to at most 1, and the
  rest is reported in `cropland_coverage`. It is never redistributed.
- **No cropland:** a source district with no cropland in the raster gets no `CROPLAND` weights.
  Its value is not restated by this method, and h05 counts it. This includes a district smaller than
  one cell.
- **Nodata:** nodata cells count as no cropland, and their area is reported (`nodata_km2`).
- **Cell area:** for a lon/lat raster, cell area comes from the pipeline's one area method,
  `core.geodesic_area_km2`, row by row. A projected raster uses its planar cell area: weights are
  ratios within one district, and the projection's scale varies little across a district (exact for
  an equal-area grid).
- **Which indicators:** every statistic in `config/indicators.yaml` is restated with every available
  method unless its entry sets `methods: [AREA]`. The mapped-area self-check is always `AREA` only.

## Supplying a raster

1. **Evaluate the raster** in `docs/sources/<source>.md` using the template in `docs/sources/README.md`.
   Add these:
   - the cropland definition (net sown area, cropland extent, or irrigated area);
   - the reference year or years;
   - the resolution;
   - the published accuracy;
   - the licence clause on reuse.
2. **Place the file** under `data/bronze/cropland/` as delivered, in any format GDAL reads (usually
   GeoTIFF), any CRS and north-up. Never edit it. A resampled copy is a new file with its own
   declaration.
3. **Declare it** in `config/indicators.yaml`:

   ```yaml
   weights:
     cropland:
       path: data/bronze/cropland/<file>.tif
       source: "<publisher, product, reference year, resolution>"
       value: fraction    # share of each cell that is cropland (0-1 after scale)
       scale: 0.01        # e.g. a percent raster; 1.0 if already 0-1
       band: 1
   ```

   Set `value: area_ha` or `value: area_km2` if each cell holds cropland area rather than a share.
4. **Rebuild:** run `dvc repro` (or `python -m district_evolution build`). Stage h02 depends on
   `data/bronze/cropland/` and `config/indicators.yaml`, so a new or replaced raster reruns
   harmonization.

Bad declarations are refused rather than guessed:

- a raster with no CRS, or a rotated raster;
- a fraction above 1 after `scale`;
- a cell holding more cropland than its own area;
- a negative value.

The error names the district and the number of bad cells.

**Resolution and run time:** the raster is read in blocks of rows, so memory stays bounded at any
resolution. Run time grows with the number of cells: a 1 km raster takes seconds, a 30 m raster takes
much longer. A resolution finer than the maps' own accuracy (about 1 km at 1:1,000,000) adds run time
without adding accuracy.

## What it produces

| Output | Meaning |
|---|---|
| `statistical_crosswalk` rows with `method = CROPLAND` | The weights, each with the raster named in its `assumption` |
| `cropland_coverage` (released) | Per source district and map: its cropland, how much of it the weights carry, how much they do not, and its nodata area |
| `stat_harmonized_value` rows with `method = CROPLAND` | Each statistic restated by cropland |
| `harmonization_method_sensitivity` (released) | Each 2025 district's value under `CROPLAND` against `AREA`, flagged when they differ by more than `harmonize.sensitivity_flag_rel` or when only one method restates a value there |
| `outputs/harmonize/h05_report.md` | Conservation for both methods, a summary of the differences, the 15 largest differences, and cropland coverage |

The API returns the sensitivity rows with a district's harmonized values
(`/api/districts/{ck}/harmonized`).

## Reading the results

Neither method is "the" answer. Each one states its assumption on every row:

- **AREA** assumes the crop is spread evenly over the land.
- **CROPLAND** assumes the crop is spread evenly over the raster's cropland, and that the raster's
  year applies to the statistic's year.

Where the two methods agree, the restated value does not depend on that choice. Where they differ, the
value does. The flag marks those districts, and nothing is reconciled automatically.

`harmonize.sensitivity_flag_rel` (0.25) has not been measured yet. Measure the distribution of
`rel_difference` on the first raster, then set the threshold in the gap above the bulk of that
distribution (`config/pipeline.yaml`).

## Tests

`tests/test_cropland.py` runs on synthetic rasters and needs no supplied data:

- exact zonal sums against hand-computed geodesic cell areas;
- blocking does not change results;
- units and scale;
- impossible values are refused;
- a projected grid;
- the WP4 test case: with a synthetic raster that has cropland everywhere except Lahaul & Spiti,
  `AREA` sends 46% of a 1951 Kangra total there and `CROPLAND` sends none. Both methods conserve what
  their weights carry.
