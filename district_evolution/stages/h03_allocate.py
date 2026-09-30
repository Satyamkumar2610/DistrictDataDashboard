"""Stage h03 — Extensive statistics restated on the 2025 districts (stat_harmonized_value).

Only extensive indicators pass through allocation; engine.allocate() refuses a ratio.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.harmonize import engine, registry


def main() -> None:
    kinds = {i.code: i.kind for i in registry()[0]}
    obs = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_observation.parquet")
    w = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "statistical_crosswalk.parquet")
    parts = [engine.allocate(g, w[w.method == m], kinds[code])
             for code, g in obs.groupby("indicator") for m in sorted(w.method.unique())]
    h = pd.concat(parts, ignore_index=True)
    core.write_table(h, core.GOLD_HARMONIZE_DIR / "stat_harmonized_value.parquet", "stat_harmonized_value",
                     csv_copy=core.HARMONIZE_OUTPUT_DIR / "h03_stat_harmonized_value.csv")
    print(h.groupby(["indicator", "method"]).agg(rows=("value", "size"), years=("year", "nunique")).to_string())


if __name__ == "__main__":
    main()
