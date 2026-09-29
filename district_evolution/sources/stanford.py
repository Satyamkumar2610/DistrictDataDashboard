"""Stanford historical district boundaries, 1951–2021, published in EPSG:4326."""

from __future__ import annotations

import geopandas as gpd

from .gpkg import datasets, read_layer


class StanfordSource:
    source_id = "stanford"

    def vintages(self) -> list[int]:
        return sorted(int(y) for y in datasets(self.source_id))

    def load(self, year: int) -> gpd.GeoDataFrame:
        return read_layer(datasets(self.source_id)[str(year)])
