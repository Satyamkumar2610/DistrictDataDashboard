"""Stage h01 — Reported statistics, linked to district identities (stat_observation).

Every registered indicator (config/indicators.yaml, plus the mapped-area self-check) is read as
reported and linked by name within its state on the map whose boundaries it uses. Rows that do not
link are kept and counted, never dropped or guessed.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.harmonize import engine, registry


def main() -> None:
    indicators, _ = registry()
    obs = pd.concat([engine.link(i.observations()) for i in indicators], ignore_index=True)
    obs.insert(0, "obs_id", [core.stable_id("OBS", *r) for r in
                             obs[["indicator", "raw_name", "state", "year", "source"]].itertuples(index=False)])
    core.write_table(obs.sort_values("obs_id"), core.GOLD_HARMONIZE_DIR / "stat_observation.parquet", "stat_observation",
                     csv_copy=core.HARMONIZE_OUTPUT_DIR / "h01_stat_observation.csv")
    print(pd.crosstab(obs.indicator, obs.link_status).to_string())


if __name__ == "__main__":
    main()
