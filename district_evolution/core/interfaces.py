"""Extension points; each returns a frame that must pass the named contract before a stage reads it."""

from __future__ import annotations

from typing import Literal, Protocol

import geopandas as gpd
import pandas as pd


class BoundarySource(Protocol):
    """A boundary map series; load() returns one vintage in the boundary_layer contract, EPSG:4326."""

    source_id: str

    def vintages(self) -> list[int]: ...

    def load(self, year: int) -> gpd.GeoDataFrame: ...


class EvidenceSource(Protocol):
    """Corroborating evidence; claims() returns the evidence_claim contract (added in WP2)."""

    source_id: str

    def claims(self) -> pd.DataFrame: ...


class Indicator(Protocol):
    """A district statistic; ratio indicators are recomputed after harmonization, never allocated (WP4)."""

    code: str
    unit: str
    kind: Literal["extensive", "ratio"]

    def observations(self) -> pd.DataFrame: ...


class WeightMethod(Protocol):
    """A harmonization weighting with a stated, non-empty distribution assumption (WP4)."""

    name: str
    assumption: str

    def weights(self, year: int) -> pd.DataFrame: ...
