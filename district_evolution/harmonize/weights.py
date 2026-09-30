"""Weight methods: how a district's reported total is shared among 2025 districts (WeightMethod)."""

from __future__ import annotations

import pandas as pd

from district_evolution import core


class AreaWeight:
    """Weight = share of the source district's area inside each 2025 district (crosswalk_to_reference,
    a direct overlay of the source map on the 2025 map, no chaining)."""

    name = "AREA"
    assumption = ("The quantity is spread evenly over the source district's area. Exact for area itself; "
                  "for crops it ignores where cropland lies within the district.")

    def weights(self, year: int) -> pd.DataFrame:
        x = pd.read_parquet(core.PRODUCTS_DIR / "crosswalk_to_reference.parquet")
        x = x[x.year == year]
        return pd.DataFrame({"year": x.year, "source_ck": x.source_ck, "target_ck": x.target_ck,
                             "method": self.name, "assumption": self.assumption,
                             "weight": x.share_of_source, "area_km2": x.area_km2})


WEIGHT_METHODS = {m.name: m for m in (AreaWeight(),)}
