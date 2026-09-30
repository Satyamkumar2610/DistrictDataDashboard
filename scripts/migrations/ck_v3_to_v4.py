"""One-off migration: map every v3 canonical key to its v4 key.

v4.0.0 excludes the nine "Disputed (...)" strips on the SOI 2025 map in s01 (config
`placeholders`). Their keys (IND-000793..800, 802) are retired and the 2025 keys minted after them
shift down: Riasi IND-000801 -> IND-000793, Champhai IND-000803 -> IND-000794, Kolkata
IND-000804 -> IND-000795. Every other key is unchanged. As for v2 -> v3, the map joins on
geom_obs_id, which is the same in both versions.

Usage: python scripts/migrations/ck_v3_to_v4.py <v3 ck_observation.parquet>
Writes data/reference/ck_migration_v3_to_v4.csv (committed).
"""

from __future__ import annotations

import sys

import pandas as pd

from district_evolution import core


def main(v3_path: str) -> None:
    v3 = pd.read_parquet(v3_path)[["geom_obs_id", "canonical_key", "year"]].rename(columns={"canonical_key": "v3_ck"})
    v4 = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")[["geom_obs_id", "canonical_key"]]
    j = v3.merge(v4.rename(columns={"canonical_key": "v4_ck"}), on="geom_obs_id", how="left")
    counts = (j.groupby("v3_ck", dropna=False)
              .agg(v4_ck=("v4_ck", lambda s: "" if s.isna().all() else s.dropna().iloc[0]),
                   n_v4_keys=("v4_ck", "nunique"), observations=("geom_obs_id", "size"),
                   first_year=("year", "min"), last_year=("year", "max")).reset_index())
    if (counts.n_v4_keys > 1).any():
        raise AssertionError("a v3 key maps to more than one v4 key")
    counts["relation"] = "IDENTICAL"
    counts.loc[(counts.v4_ck != "") & (counts.v4_ck != counts.v3_ck), "relation"] = "RENUMBERED"
    counts.loc[counts.v4_ck == "", "relation"] = "RETIRED_NON_ADMINISTRATIVE"
    out = counts.drop(columns="n_v4_keys").sort_values("v3_ck")
    out.to_csv(core.REFERENCE_DIR / "ck_migration_v3_to_v4.csv", index=False)
    print(out.relation.value_counts().to_string())
    print(out[out.relation != "IDENTICAL"].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
