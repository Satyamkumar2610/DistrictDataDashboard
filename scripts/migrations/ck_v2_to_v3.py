"""One-off migration: map every v2 canonical key to its v3 canonical key.

v2 minted 1,376 CKs under the symmetric 90/90 continuity rule; v3 derives 804
under the core-continuity rule (docs/architecture/REVAMP_PLAN_V3.md section 3.3).
Both assign CKs to the same geometry observations (geom_obs_id is identical
across versions), so each v2 CK maps to the v3 CK holding its observations.

Usage: python scripts/migrations/ck_v2_to_v3.py <v2 geom_obs_to_ck.parquet>
Writes data/reference/ck_migration_v2_to_v3.csv (committed; v2 gold is not).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import lib  # noqa: E402


def main(v2_path: str) -> None:
    v2 = pd.read_parquet(v2_path).rename(columns={"canonical_key": "v2_ck"})
    v3 = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")[["geom_obs_id", "canonical_key", "year"]]
    j = v2.merge(v3.rename(columns={"canonical_key": "v3_ck"}), on="geom_obs_id", how="left")

    unmapped = j[j.v3_ck.isna()]
    counts = (j.dropna(subset=["v3_ck"]).groupby(["v2_ck", "v3_ck"])
              .agg(shared_observations=("geom_obs_id", "size"),
                   first_year=("year", "min"), last_year=("year", "max")).reset_index())
    n_targets = counts.groupby("v2_ck")["v3_ck"].transform("nunique")
    n_sources = counts.groupby("v3_ck")["v2_ck"].transform("nunique")
    counts["relation"] = "IDENTICAL"
    counts.loc[n_sources > 1, "relation"] = "MERGED_INTO_V3_CK"
    counts.loc[n_targets > 1, "relation"] = "SPLIT_ACROSS_V3_CKS"
    counts = counts.astype({"first_year": int, "last_year": int})

    retired = unmapped.groupby("v2_ck").size().rename("observations").reset_index()
    retired["v3_ck"] = ""
    retired["relation"] = "RETIRED_NON_ADMINISTRATIVE"

    out = pd.concat([counts, retired.rename(columns={"observations": "shared_observations"})],
                    ignore_index=True).sort_values(["v2_ck", "v3_ck"])
    out.to_csv(lib.REFERENCE_DIR / "ck_migration_v2_to_v3.csv", index=False)
    print(out.relation.value_counts().to_string())
    print(f"v2 CKs: {v2.v2_ck.nunique()}  mapped: {counts.v2_ck.nunique()}  retired: {len(retired)}")


if __name__ == "__main__":
    main(sys.argv[1])
