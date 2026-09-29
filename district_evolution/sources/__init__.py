"""Boundary map sources; every vintage passes the boundary_layer contract before s01 uses it."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from district_evolution.contracts import schemas
from district_evolution.core.interfaces import BoundarySource

from .soi import SoiSource
from .stanford import StanfordSource

SOURCES: dict[str, BoundarySource] = {s.source_id: s for s in (StanfordSource(), SoiSource())}


def load(source_id: str, year: int) -> gpd.GeoDataFrame:
    gdf = SOURCES[source_id].load(year)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        raise ValueError(f"{source_id} {year}: a boundary layer must be EPSG:4326, got {gdf.crs}")
    schemas.validate("boundary_layer", pd.DataFrame(gdf.drop(columns="geometry")))
    return gdf
