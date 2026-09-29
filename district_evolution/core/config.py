"""Paths, configuration and map vintages; every threshold is read through CFG."""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
SILVER_GEOM_DIR = PROJECT_ROOT / "data" / "silver" / "geometry"
GOLD_SPATIAL_DIR = PROJECT_ROOT / "data" / "gold" / "spatial"
GOLD_EVENTS_DIR = PROJECT_ROOT / "data" / "gold" / "events"
GOLD_CORE_DIR = PROJECT_ROOT / "data" / "gold" / "core"
PRODUCTS_DIR = PROJECT_ROOT / "data" / "products"
WAREHOUSE_PATH = PROJECT_ROOT / "data" / "gold" / "district_evolution.duckdb"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "pipeline"
EVENTS_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "events"
EVENTS_CSV = PROJECT_ROOT / "data" / "bronze" / "events" / "district_evolution_master.csv"

for _d in (SILVER_GEOM_DIR, GOLD_SPATIAL_DIR, GOLD_EVENTS_DIR, GOLD_CORE_DIR,
           PRODUCTS_DIR, OUTPUT_DIR, EVENTS_OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

with open(CONFIG_DIR / "pipeline.yaml") as _fh:
    CFG: dict = yaml.safe_load(_fh)

PIPELINE_VERSION: str = CFG["pipeline_version"]
VINTAGES: list[tuple[str, int]] = [(s, int(y)) for s, y in CFG["vintages"]]
YEARS: list[int] = [y for _, y in VINTAGES]
SOURCE_BY_YEAR: dict[int, str] = {y: s for s, y in VINTAGES}
REFERENCE_YEAR: int = int(CFG["reference_year"])
WINDOWS: list[tuple[int, int]] = list(zip(YEARS[:-1], YEARS[1:]))


def silver_path(year: int) -> Path:
    return SILVER_GEOM_DIR / f"{SOURCE_BY_YEAR[year]}_{year}.geoparquet"
