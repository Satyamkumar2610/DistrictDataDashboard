"""Indicators: district statistics as reported, before harmonization (the Indicator interface)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from district_evolution import core

OBS_COLUMNS = ["indicator", "raw_name", "state", "year", "map_year", "value", "unit", "source"]


@dataclass(frozen=True)
class CsvIndicator:
    """A statistic delivered as a CSV with one row per district and year.

    `columns` maps the file's headers to raw_name, state, year and value. `boundary_year` is the map
    whose boundaries the source reports on, when it says so (e.g. a database apportioned to one
    census's districts); otherwise each year maps to the latest map depicting no later than it.
    Every row is kept; rows whose district cannot be linked are reported by h01, never dropped.
    `methods` limits the weight methods it is restated with (default: every available method).
    """
    code: str
    unit: str
    kind: Literal["extensive", "ratio"]
    path: str
    source: str
    columns: dict
    boundary_year: int | None = None
    methods: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("extensive", "ratio"):
            raise ValueError(f"indicator {self.code!r}: kind must be extensive or ratio, not {self.kind!r}")
        if self.methods is not None:
            object.__setattr__(self, "methods", tuple(self.methods))

    def observations(self) -> pd.DataFrame:
        raw = pd.read_csv(core.PROJECT_ROOT / self.path, dtype=str)
        df = pd.DataFrame({k: raw[v] for k, v in self.columns.items()})
        df["year"] = df.year.astype(int)
        df["map_year"] = float(self.boundary_year) if self.boundary_year else float("nan")
        df["value"] = pd.to_numeric(df.value, errors="coerce")
        return df.assign(indicator=self.code, unit=self.unit, source=self.source)[OBS_COLUMNS]


@dataclass(frozen=True)
class MappedAreaIndicator:
    """Each district's own area on each map, as the maps report it (district_area_admin).

    Not agricultural: it is the one statistic every district has on every map, so harmonizing it
    must reproduce the crosswalk exactly. h05 uses it to prove the engine end to end. Area is spread
    by area by definition, so it is restated with the AREA method only.
    """
    code: str = "mapped_area_km2"
    unit: str = "km2"
    kind: Literal["extensive", "ratio"] = "extensive"
    source: str = "data/products/district_area_admin.parquet (s10)"
    methods: tuple[str, ...] = ("AREA",)

    def observations(self) -> pd.DataFrame:
        a = pd.read_parquet(core.PRODUCTS_DIR / "district_area_admin.parquet")
        df = pd.DataFrame({"raw_name": a.district_name, "state": a.state, "year": a.year,
                           "map_year": a.year.astype(float), "value": a.area_km2})
        return df.assign(indicator=self.code, unit=self.unit, source=self.source)[OBS_COLUMNS]
