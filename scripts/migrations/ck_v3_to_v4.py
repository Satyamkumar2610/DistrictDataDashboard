"""One-off migration: map every v3 canonical key to its v4 key.

v4.0.0 changes keys in two ways. (1) The nine "Disputed (...)" strips on the SOI 2025 map are
excluded in s01 (config `placeholders`): their keys are retired. (2) OD-02: a district that stays
whole, keeps its name and grows keeps its identity (Una 1991, Chennai 2021, ... ten cases), so the
key minted for the grown district in v3 merges into the district's earlier key, and keys minted
after it shift down. As for v2 -> v3, the map joins on geom_obs_id, which is the same in both
versions.

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
    sources = counts[counts.v4_ck != ""].groupby("v4_ck").v3_ck.transform("nunique")
    counts.loc[sources[sources > 1].index, "relation"] = "MERGED_INTO_V4_CK"  # OD-02: two v3 keys, one district
    counts.loc[counts.v4_ck == "", "relation"] = "RETIRED_NON_ADMINISTRATIVE"
    out = counts.drop(columns="n_v4_keys").sort_values("v3_ck")
    out.to_csv(core.REFERENCE_DIR / "ck_migration_v3_to_v4.csv", index=False)
    print(out.relation.value_counts().to_string())
    print(out[out.relation.isin(["MERGED_INTO_V4_CK", "RETIRED_NON_ADMINISTRATIVE"])].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
