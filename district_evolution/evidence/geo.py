"""Locate evidence points (a claim's coordinate) on the map of a given year."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from district_evolution import core


def locate(points: gpd.GeoDataFrame, year: int, obs: pd.DataFrame) -> pd.DataFrame:
    """For each point: the CK whose polygon at `year` contains it (or the nearest within evidence.near_km)."""
    near_km = core.CFG["evidence"]["near_km"]
    layer = gpd.read_parquet(core.silver_path(year), columns=["geom_obs_id", "district_name_norm", "geometry"])
    layer = layer.merge(obs[["geom_obs_id", "canonical_key"]], on="geom_obs_id")
    inside = gpd.sjoin(points, layer, how="left", predicate="within")
    inside = inside[~inside.index.duplicated()]
    res = pd.DataFrame({"canonical_key": inside.canonical_key, "our_name_norm": inside.district_name_norm,
                        "match_geom": np.where(inside.canonical_key.notna(), "INSIDE", None)}, index=points.index)
    miss = res.canonical_key.isna()
    if miss.any():
        pm = points[miss].to_crs(7755)  # WGS 84 / India NSF LCC, metres
        near = gpd.sjoin_nearest(pm, layer.to_crs(7755), how="left", max_distance=near_km * 1000,
                                 distance_col="dist_m")
        near = near[~near.index.duplicated()]
        res.loc[near.index[near.canonical_key.notna()], ["canonical_key", "our_name_norm"]] = \
            near.loc[near.canonical_key.notna(), ["canonical_key", "district_name_norm"]].values
        res.loc[near.index[near.canonical_key.notna()], "match_geom"] = "NEAR"
    return res
