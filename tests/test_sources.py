"""Boundary source adapters and the boundary_layer contract."""

import geopandas as gpd
import pytest
from shapely.geometry import box

from district_evolution import core, sources


def test_every_pipeline_vintage_has_an_adapter():
    registered = {(s, y) for s, src in sources.SOURCES.items() for y in src.vintages()}
    assert set(core.VINTAGES) <= registered


class FakeSource:
    source_id = "fake"

    def __init__(self, keys, crs="EPSG:4326"):
        self.keys, self.crs = keys, crs

    def vintages(self):
        return [2025]

    def load(self, year):
        return gpd.GeoDataFrame({"source_pk": self.keys, "district_name_original": ["A"] * len(self.keys),
                                 "state_name_original": ["S"] * len(self.keys),
                                 "geometry": [box(0, 0, 1, 1)] * len(self.keys)}, crs=self.crs)


def test_contract_accepts_a_clean_layer(monkeypatch):
    monkeypatch.setitem(sources.SOURCES, "fake", FakeSource(["1", "2"]))
    assert len(sources.load("fake", 2025)) == 2


def test_contract_rejects_duplicate_source_keys(monkeypatch):
    monkeypatch.setitem(sources.SOURCES, "fake", FakeSource(["1", "1"]))
    with pytest.raises(RuntimeError, match="boundary_layer"):
        sources.load("fake", 2025)


def test_contract_rejects_a_projected_layer(monkeypatch):
    monkeypatch.setitem(sources.SOURCES, "fake", FakeSource(["1"], crs="EPSG:3857"))
    with pytest.raises(ValueError, match="EPSG:4326"):
        sources.load("fake", 2025)
