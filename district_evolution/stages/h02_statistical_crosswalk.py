"""Stage h02 — Statistical weights for every map the linked statistics use (statistical_crosswalk).

Each weight row carries its method and a stated distribution assumption. AREA comes from
crosswalk_to_reference (a direct overlay onto the 2025 map, no chaining). A CROPLAND method is
added as a WeightMethod once a cropland raster is supplied.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.harmonize.weights import WEIGHT_METHODS


def main() -> None:
    obs = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_observation.parquet")
    years = sorted(int(y) for y in obs.loc[obs.link_status == "LINKED", "map_year"].unique())
    w = pd.concat([m.weights(y) for m in WEIGHT_METHODS.values() for y in years], ignore_index=True)
    core.write_table(w.sort_values(["method", "year", "source_ck", "target_ck"]),
                     core.GOLD_HARMONIZE_DIR / "statistical_crosswalk.parquet", "statistical_crosswalk")
    print(w.groupby(["method", "year"]).size().to_string())


if __name__ == "__main__":
    main()
