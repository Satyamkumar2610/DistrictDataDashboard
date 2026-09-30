"""Restate district statistics reported on an old map onto the 2025 districts.

    python examples/02_restate_statistics.py

Uses the 1971 map's own district areas for Himachal Pradesh as the statistic, so the answer is known:
each 2025 district receives the part of each 1971 district that lies inside it. With your own file,
pass a DataFrame with columns name, state, year, value (or use the CLI, harmonize.cli).
"""

import pandas as pd

from district_evolution import core
from district_evolution.harmonize import restate

tables = core.RELEASE_DIR / "tables"
areas = pd.read_parquet(tables / "district_area_admin.parquet").query("year == 1971 and state == 'Himachal Pradesh'")
stats = pd.DataFrame({"name": areas.district_name, "state": areas.state, "year": 1971, "value": areas.area_km2})

links, result = restate.restate(stats, indicator="area_km2", tables=tables)
print(links[["raw_name", "map_year", "link_status", "canonical_key"]].to_string(index=False))
print()
print(result[["target_name", "target_state", "value", "n_sources", "coverage_score"]]
      .sort_values("value", ascending=False).round(1).to_string(index=False))
print(f"\nreported {stats.value.sum():,.0f} km², restated {result.value.sum():,.0f} km² "
      "(the rest lies outside the 2025 map's districts; weights are never renormalised)")
