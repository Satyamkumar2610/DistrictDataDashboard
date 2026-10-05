# Cropland raster (bronze)

The raster declared under `weights.cropland` in `config/indicators.yaml` lives here, as delivered (any
GDAL-readable grid, typically a GeoTIFF). It is never edited; a resampled or reprojected copy is a new
file with its own declaration. Format, units and checks: `docs/operations/cropland_weights.md`. The
source is evaluated in `docs/sources/<source>.md` before it is declared. Stage h02 depends on this
directory, so replacing the raster reruns the CROPLAND weights (`dvc repro`).

No raster yet: the owner supplies it (decision of 2026-09-29).
