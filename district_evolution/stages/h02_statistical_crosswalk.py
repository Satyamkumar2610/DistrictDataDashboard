"""Stage h02 — Statistical weights for every map the linked statistics use (statistical_crosswalk).

Each weight row carries its method and a stated distribution assumption. AREA comes from
crosswalk_to_reference (a direct overlay onto the 2025 map, no chaining). CROPLAND, when a cropland
raster is declared in config/indicators.yaml, shares each source district by where its cropland lies
(harmonize/cropland.py); how much of each district's cropland its weights carry is cropland_coverage.
A method is computed only for the maps used by indicators restated with it.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.contracts.schemas import SCHEMAS
from district_evolution.harmonize import methods_for, registry, weight_methods


def main() -> None:
    obs = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_observation.parquet")
    linked = obs[obs.link_status == "LINKED"]
    methods = weight_methods()
    indicators = registry()[0]
    parts, coverage = [], []
    for name, method in methods.items():
        codes = [i.code for i in indicators if name in methods_for(i, methods)]
        years = sorted(int(y) for y in linked.loc[linked.indicator.isin(codes), "map_year"].unique())
        parts += [method.weights(y) for y in years]
        if hasattr(method, "coverage"):
            coverage += [method.coverage(y) for y in years]
    w = pd.concat(parts, ignore_index=True)
    core.write_table(w.sort_values(["method", "year", "source_ck", "target_ck"]),
                     core.GOLD_HARMONIZE_DIR / "statistical_crosswalk.parquet", "statistical_crosswalk")
    cols = list(SCHEMAS["cropland_coverage"].columns)
    cov = (pd.concat(coverage, ignore_index=True) if coverage else
           pd.DataFrame({c: pd.Series(dtype="int64" if c in ("year", "cells") else
                                      str if c in ("source_ck", "method") else "float64") for c in cols}))
    core.write_table(cov[cols].sort_values(["method", "year", "source_ck"]),
                     core.GOLD_HARMONIZE_DIR / "cropland_coverage.parquet", "cropland_coverage")
    print(w.groupby(["method", "year"]).size().to_string())
    if len(cov):
        print(cov.groupby("year")[["cropland_km2", "unallocated_cropland_km2", "nodata_km2", "cell_km2"]].sum().round(1)
              .to_string())


if __name__ == "__main__":
    main()
