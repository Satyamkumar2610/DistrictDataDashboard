"""Cropland weights (WeightMethod CROPLAND): share a district's total by where its cropland lies.

A cropland raster declared in config/indicators.yaml (`weights.cropland`) is summed over each source
map overlaid on the 2025 map. A raster cell belongs to the source district its centre lies in, and to
the one 2025 district (or none) its centre lies in, so cropland is partitioned the way land is:

    weight(s -> t) = cropland in s and t / cropland in s

Cropland in s that lies in no 2025 district, or only in a sliver overlap the crosswalk leaves out (as
the AREA method does), stays in the denominator: a source's weights sum to at most 1 and the rest is
reported in cropland_coverage, never redistributed. A source with no cropland in the raster gets no
CROPLAND weights, so its value is not shared by this method; h05 lists it. Nodata cells (and NaN
cells) count as no cropland and their area is reported; so is the area of the cells read, which falls
short of the district's area where the raster does not cover it.

Cell areas come from the one area method (core.geodesic_area_km2) row by row for a geographic raster.
For a projected raster the planar cell area is used: weights are ratios within one district, where the
projection's scale varies by far less than the raster's own accuracy (exact for an equal-area grid).
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import STRtree, box

from district_evolution import core

VALUE_KINDS = ("fraction", "area_km2", "area_ha")
KM2_PER_UNIT = {"area_km2": 1.0, "area_ha": 0.01}
# A fraction above 1, or a cell holding more cropland than its own area, is a unit or scale error in the
# raster's declaration, not data: refuse it. The margin absorbs float32 storage and cell-area rounding.
VALUE_TOL = 1e-3
BLOCK_ROWS = 1024  # rows read at once; bounds memory for large districts on fine rasters


@dataclass(frozen=True)
class CroplandRaster:
    """A cropland raster as declared in config/indicators.yaml under weights.cropland.

    value: fraction  share of each cell that is cropland (0-1 after `scale`; scale 0.01 for percent)
           area_km2  cropland area inside each cell, km2 (after `scale`)
           area_ha   cropland area inside each cell, hectares (after `scale`)
    """
    path: str
    source: str
    value: Literal["fraction", "area_km2", "area_ha"]
    scale: float = 1.0
    band: int = 1

    def __post_init__(self) -> None:
        if self.value not in VALUE_KINDS:
            raise ValueError(f"weights.cropland.value must be one of {VALUE_KINDS}, not {self.value!r}")
        if not (self.scale > 0 and math.isfinite(self.scale)):
            raise ValueError(f"weights.cropland.scale must be a positive number, not {self.scale!r}")
        if not self.source.strip():
            raise ValueError("weights.cropland.source must name the publisher, product, year and resolution")

    @property
    def file(self) -> Path:
        p = Path(self.path)
        return p if p.is_absolute() else core.PROJECT_ROOT / p


@functools.lru_cache(maxsize=65536)
def _row_km2(top: float, bottom: float, width: float) -> float:
    """Area of one cell of a lon/lat grid; every cell in a row has the same area."""
    return core.geodesic_area_km2(box(0.0, min(top, bottom), abs(width), max(top, bottom)))


def _cell_km2(transform, rows: int, geographic: bool) -> np.ndarray:
    """Cell area (km2) for each row of a block: shape (rows, 1), broadcast across columns."""
    if geographic:
        tops = [transform.f + i * transform.e for i in range(rows)]
        return np.array([[_row_km2(t, t + transform.e, transform.a)] for t in tops])
    return np.full((rows, 1), abs(transform.a * transform.e) / 1e6)


def zonal(spec: CroplandRaster, sources: gpd.GeoDataFrame, targets: gpd.GeoDataFrame | None,
          block_rows: int = BLOCK_ROWS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cropland per source district and per (source, target) pair.

    `sources` and `targets` carry a `key` column and polygons in any CRS. With targets None, each source
    is its own target (the reference map against itself). Returns
    pairs:   source_key, target_key (None: in no target), cropland_km2
    sources: source_key, cropland_km2, nodata_km2, cell_km2 (area of the cells read), cells
    """
    import rasterio
    from rasterio import features
    from rasterio.windows import Window

    with rasterio.open(spec.file) as ds:
        if ds.crs is None:
            raise ValueError(f"{spec.path} has no coordinate reference system")
        t = ds.transform
        if t.b != 0 or t.d != 0:
            raise ValueError(f"{spec.path} is rotated; warp it to a north-up grid first")
        geographic = bool(ds.crs.is_geographic)
        src = sources.to_crs(ds.crs).sort_values("key").reset_index(drop=True)
        tgt = None if targets is None else targets.to_crs(ds.crs).sort_values("key").reset_index(drop=True)
        tgt_geoms = None if tgt is None else tgt.geometry.values
        tree = None if tgt is None else STRtree(tgt_geoms)
        inv = ~t

        pair_rows: list[dict] = []
        src_rows: list[dict] = []
        for key, geom in zip(src.key, src.geometry, strict=True):
            minx, miny, maxx, maxy = geom.bounds
            cols, rows = zip(*(inv @ (x, y) for x, y in ((minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy))),
                             strict=True)
            c0, c1 = max(math.floor(min(cols)), 0), min(math.ceil(max(cols)), ds.width)
            r0, r1 = max(math.floor(min(rows)), 0), min(math.ceil(max(rows)), ds.height)
            n_tgt = 0 if tgt is None else len(tgt)
            by_label = np.zeros(n_tgt + 1)  # label 0 = no target; label i+1 = tgt row i
            nodata_km2 = 0.0
            cell_km2 = 0.0
            cells = 0
            cand = [] if tree is None else sorted(int(i) for i in tree.query(geom, predicate="intersects"))
            for r in range(r0, r1, block_rows):
                if c1 <= c0:
                    break
                win = Window(c0, r, c1 - c0, min(block_rows, r1 - r))
                wt = ds.window_transform(win)
                shape = (int(win.height), int(win.width))
                inside = features.rasterize([(geom, 1)], out_shape=shape, transform=wt, fill=0, dtype="uint8") == 1
                if not inside.any():
                    continue
                arr = ds.read(spec.band, window=win, masked=True)
                raw = np.ma.getdata(arr).astype("float64") * spec.scale
                nodata = np.ma.getmaskarray(arr) | np.isnan(raw)
                area = np.broadcast_to(_cell_km2(wt, shape[0], geographic), shape)
                crop = raw * area if spec.value == "fraction" else raw * KM2_PER_UNIT[spec.value]
                valid = inside & ~nodata
                bad = valid & ((raw < -VALUE_TOL) | (crop > area * (1 + VALUE_TOL)) | ~np.isfinite(raw))
                if bad.any():
                    raise ValueError(f"{spec.path}: {int(bad.sum())} cells in {key} hold values outside 0..cell area "
                                     f"(value: {spec.value}, scale: {spec.scale}); check the declared units")
                if tgt_geoms is None:
                    labels = np.zeros(shape, dtype="int32")
                else:
                    bx = box(*rasterio.windows.bounds(win, t))
                    shapes = [(tgt_geoms[i], i + 1) for i in cand if tgt_geoms[i].intersects(bx)]
                    labels = (features.rasterize(shapes, out_shape=shape, transform=wt, fill=0, dtype="int32")
                              if shapes else np.zeros(shape, dtype="int32"))
                by_label += np.bincount(labels[valid], weights=crop[valid], minlength=n_tgt + 1)
                nodata_km2 += float(area[inside & nodata].sum())
                cell_km2 += float(area[inside].sum())
                cells += int(inside.sum())
            total = float(by_label.sum())
            src_rows.append({"source_key": key, "cropland_km2": total, "nodata_km2": nodata_km2, "cell_km2": cell_km2,
                             "cells": cells})
            if tgt is None:
                pair_rows.append({"source_key": key, "target_key": key, "cropland_km2": total})
                continue
            for label in np.flatnonzero(by_label):
                pair_rows.append({"source_key": key, "target_key": None if label == 0 else tgt.key.iloc[label - 1],
                                  "cropland_km2": float(by_label[label])})
    pairs = pd.DataFrame(pair_rows, columns=["source_key", "target_key", "cropland_km2"])
    return pairs, pd.DataFrame(src_rows, columns=["source_key", "cropland_km2", "nodata_km2", "cell_km2", "cells"])


@functools.lru_cache(maxsize=2)  # the reference map and one source map at a time
def _layer(year: int) -> gpd.GeoDataFrame:
    """One map's full-resolution polygons, keyed by canonical key."""
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet", columns=["geom_obs_id", "canonical_key", "year"])
    ck = obs[obs.year == year].set_index("geom_obs_id").canonical_key
    g = gpd.read_parquet(core.silver_path(year), columns=["geom_obs_id", "geometry"])
    g = g[g.geom_obs_id.isin(ck.index)]
    return gpd.GeoDataFrame({"key": g.geom_obs_id.map(ck).values}, geometry=g.geometry.values, crs=g.crs)


class CroplandWeight:
    """Weight = share of the source district's cropland inside each 2025 district."""

    name = "CROPLAND"

    def __init__(self, spec: CroplandRaster):
        self.spec = spec
        self.assumption = (f"The quantity is spread over the source district in proportion to its cropland in "
                           f"{spec.source}: exact if the crop grows on that cropland, evenly within it, and the "
                           "raster's cropland applies to the statistic's year.")
        self._cache: dict[int, tuple[pd.DataFrame, pd.DataFrame]] = {}

    def _zonal(self, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        if year not in self._cache:
            ref = core.REFERENCE_YEAR
            self._cache[year] = zonal(self.spec, _layer(year), None if year == ref else _layer(ref))
        return self._cache[year]

    def weights(self, year: int, tables: Path | None = None) -> pd.DataFrame:
        if tables is not None:
            raise NotImplementedError("CROPLAND weights need the pipeline's full-resolution maps, not a release")
        from district_evolution.harmonize.engine import read

        pairs, per_source = self._zonal(year)
        xw = read("crosswalk_to_reference")
        xw = xw[xw.year == year][["source_ck", "target_ck", "area_km2"]]
        total = per_source.set_index("source_key").cropland_km2
        w = xw.merge(pairs, left_on=["source_ck", "target_ck"], right_on=["source_key", "target_key"], how="left")
        w["cropland_km2"] = w.cropland_km2.fillna(0.0)
        w["source_cropland_km2"] = w.source_ck.map(total).fillna(0.0)
        w = w[w.source_cropland_km2 > 0]
        return pd.DataFrame({"year": year, "source_ck": w.source_ck, "target_ck": w.target_ck, "method": self.name,
                             "assumption": self.assumption, "weight": w.cropland_km2 / w.source_cropland_km2,
                             "area_km2": w.area_km2}).sort_values(["source_ck", "target_ck"]).reset_index(drop=True)

    def coverage(self, year: int) -> pd.DataFrame:
        """Per source district: its cropland, how much of it the CROPLAND weights carry, and nodata area."""
        _, per_source = self._zonal(year)
        carried = self.weights(year).assign(km2=lambda d: d.weight * d.source_ck.map(
            per_source.set_index("source_key").cropland_km2)).groupby("source_ck").km2.sum()
        out = per_source.rename(columns={"source_key": "source_ck"})
        out["allocated_cropland_km2"] = out.source_ck.map(carried).fillna(0.0)
        out["unallocated_cropland_km2"] = (out.cropland_km2 - out.allocated_cropland_km2).clip(lower=0.0)
        return out.assign(year=year, method=self.name)[
            ["year", "source_ck", "method", "cropland_km2", "allocated_cropland_km2", "unallocated_cropland_km2",
             "nodata_km2", "cell_km2", "cells"]].sort_values("source_ck").reset_index(drop=True)
