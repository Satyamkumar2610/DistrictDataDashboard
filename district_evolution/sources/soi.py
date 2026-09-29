"""Survey of India 2025 district boundaries, published in Lambert Conformal Conic and reprojected here."""

from __future__ import annotations

import geopandas as gpd

from .gpkg import datasets, read_layer


class SoiSource:
    source_id = "soi"

    def vintages(self) -> list[int]:
        return sorted(int(y) for y in datasets(self.source_id))

    def load(self, year: int) -> gpd.GeoDataFrame:
        return read_layer(datasets(self.source_id)[str(year)]).to_crs(epsg=4326)
