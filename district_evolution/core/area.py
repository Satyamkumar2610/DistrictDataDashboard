"""The one area method: geodesic area and perimeter on the WGS84 ellipsoid."""

from __future__ import annotations

import numpy as np
from pyproj import Geod

from .config import CFG

GEOD = Geod(ellps="WGS84")


def geodesic_area_perimeter(geom) -> tuple[float, float]:
    """(area km2, perimeter km) on the WGS84 ellipsoid. The one area method."""
    if geom is None or geom.is_empty:
        return 0.0, 0.0
    area_m2, perim_m = GEOD.geometry_area_perimeter(geom)
    return abs(float(area_m2)) / 1e6, float(perim_m) / 1e3


def geodesic_area_km2(geom) -> float:
    return geodesic_area_perimeter(geom)[0]


def within_closure(error_km2, area_km2):
    tol = np.maximum(CFG["closure"]["tol_km2"], np.asarray(area_km2) * CFG["closure"]["tol_pct"] / 100.0)
    return np.abs(error_km2) <= tol
