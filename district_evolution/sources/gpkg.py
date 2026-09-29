"""Read one GeoPackage layer configured in config/sources.yaml into the boundary_layer shape."""

from __future__ import annotations

import functools

import geopandas as gpd
import yaml

from district_evolution import core


@functools.lru_cache(maxsize=1)
def _sources() -> dict:
    with open(core.CONFIG_DIR / "sources.yaml") as fh:
        return yaml.safe_load(fh)["sources"]


def datasets(source_id: str) -> dict:
    return _sources()[source_id]["datasets"]


def read_layer(cfg: dict) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(core.PROJECT_ROOT / cfg["path"], layer=cfg["primary_layer"])
    if cfg.get("state_field"):
        state = gdf[cfg["state_field"]]
    else:
        codes = gdf[cfg["state_code_field"]].astype(str).str.zfill(2)
        unmapped = sorted(set(codes) - set(core.PC11_STATE_CODES))
        if unmapped:
            raise ValueError(f"unmapped PC11 state codes: {unmapped}")
        state = codes.map(core.PC11_STATE_CODES)
    return gpd.GeoDataFrame({
        "source_pk": gdf[cfg["source_pk"]].astype(str),
        "district_name_original": gdf[cfg["name_field"]].astype(str).str.strip(),
        "state_name_original": state.astype(str).str.strip(),
        "geometry": gdf.geometry,
    }, geometry="geometry", crs=gdf.crs)
