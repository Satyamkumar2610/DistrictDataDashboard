"""Harmonization (WP4): restate district statistics reported on any map onto the 2025 districts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from district_evolution import core

from .indicators import CsvIndicator, MappedAreaIndicator

if TYPE_CHECKING:  # interfaces imports geopandas, which the platform image does not install
    from district_evolution.core.interfaces import WeightMethod

INDICATOR_COLUMNS = ("raw_name", "state", "year", "value")


def _config() -> dict:
    return yaml.safe_load((core.CONFIG_DIR / "indicators.yaml").read_text()) or {}


def registry() -> tuple[list[MappedAreaIndicator | CsvIndicator], list[dict]]:
    """Indicators to harmonize (config/indicators.yaml plus the mapped-area self-check) and ratio specs."""
    cfg = _config()
    specs = cfg.get("indicators") or []
    for spec in specs:
        missing = [c for c in INDICATOR_COLUMNS if c not in (spec.get("columns") or {})]
        if missing:
            raise ValueError(f"config/indicators.yaml: indicator {spec.get('code')!r} maps no column for {missing}")
    indicators: list[MappedAreaIndicator | CsvIndicator] = [MappedAreaIndicator(), *(CsvIndicator(**spec) for spec in specs)]
    codes = [i.code for i in indicators]
    if len(set(codes)) != len(codes):
        raise ValueError(f"config/indicators.yaml: indicator codes must be unique: {sorted(codes)}")
    return indicators, list(cfg.get("ratios") or [])


def cropland_spec():
    """The cropland raster declared under weights.cropland, or None (then only AREA weights exist)."""
    from .cropland import CroplandRaster

    spec = (_config().get("weights") or {}).get("cropland")
    return CroplandRaster(**spec) if spec else None


def weight_methods() -> dict[str, WeightMethod]:
    """Every weight method available to this build: AREA always, CROPLAND when a raster is declared."""
    from .cropland import CroplandWeight
    from .weights import AreaWeight

    spec = cropland_spec()
    methods: list[WeightMethod] = [AreaWeight(), *([CroplandWeight(spec)] if spec else [])]
    return {m.name: m for m in methods}


def methods_for(indicator, available) -> list[str]:
    """The methods an indicator is restated with: those it declares (all when it declares none), if available."""
    wanted = getattr(indicator, "methods", None)
    return sorted(m for m in available if wanted is None or m in wanted)
