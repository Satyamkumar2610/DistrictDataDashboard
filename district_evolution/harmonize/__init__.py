"""Harmonization (WP4): restate district statistics reported on any map onto the 2025 districts."""

from __future__ import annotations

import yaml

from district_evolution import core

from .indicators import CsvIndicator, MappedAreaIndicator


def registry() -> tuple[list, list[dict]]:
    """Indicators to harmonize (config/indicators.yaml plus the mapped-area self-check) and ratio specs."""
    cfg = yaml.safe_load((core.CONFIG_DIR / "indicators.yaml").read_text()) or {}
    indicators = [MappedAreaIndicator(), *(CsvIndicator(**spec) for spec in cfg.get("indicators") or [])]
    return indicators, list(cfg.get("ratios") or [])
