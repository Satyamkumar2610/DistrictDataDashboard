"""Pin canonical-key numbers after a reviewed build.

Usage:
  python scripts/maintenance/pin_ck_registry.py --version 4.0.0 \
      [--core-dir data/gold/core] [--migration data/reference/ck_migration_v3_to_v4.csv]

data/reference/ck_pinned_registry.csv maps an identity's FIRST observation
(geom_obs_id, a hash of source/year/source_pk, so stable while bronze is) to
its CK number. s04 reuses a pinned number whenever an identity starts at a
pinned observation, so a rule change renumbers only the identities it really
changes. This script, run on purpose after reviewing a build:

  1. appends every CK of the build that is not yet pinned (status ACTIVE);
  2. marks pinned CKs the build no longer produces as RETIRED (numbers are
     never reused: s04 numbers new CKs above the highest ever issued);
  3. writes the migration map for the retired CKs: each retired CK's
     observations, looked up in the new build, give the CK(s) that now hold
     them (one row per old->new pair, with the share of observations).

It never edits a CK that is still produced: pinned rows are append-only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "reference" / "ck_pinned_registry.csv"
COLUMNS = ["canonical_key", "first_geom_obs_id", "first_year", "display_name", "state", "status", "pinned_in_version"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="pipeline version that produced the build")
    ap.add_argument("--core-dir", default=str(ROOT / "data" / "gold" / "core"))
    ap.add_argument("--migration", help="write the retired-CK migration map here")
    ap.add_argument("--previous-core-dir", help="core dir of the build the pinned CKs came from "
                    "(needed for the migration map: a retired CK's observations)")
    args = ap.parse_args()

    obs = pd.read_parquet(Path(args.core_dir) / "ck_observation.parquet")
    first = obs.sort_values(["canonical_key", "year"]).drop_duplicates("canonical_key")
    reg = pd.read_csv(REGISTRY) if REGISTRY.exists() else pd.DataFrame(columns=COLUMNS)

    produced = dict(zip(first.geom_obs_id, first.canonical_key))
    clash = [(o, ck, produced[o]) for o, ck in zip(reg.first_geom_obs_id, reg.canonical_key)
             if o in produced and produced[o] != ck]
    if clash:
        raise SystemExit(f"build disagrees with pinned numbers (rebuild s04 first): {clash[:5]}")

    new = first[~first.canonical_key.isin(reg.canonical_key)]
    add = pd.DataFrame({"canonical_key": new.canonical_key, "first_geom_obs_id": new.geom_obs_id,
                        "first_year": new.year, "display_name": new.district_name, "state": new.state,
                        "status": "ACTIVE", "pinned_in_version": args.version})
    gone = ~reg.canonical_key.isin(first.canonical_key) & (reg.status == "ACTIVE")
    retired = reg[gone].canonical_key.tolist()
    reg.loc[gone, "status"] = "RETIRED"
    out = pd.concat([reg, add], ignore_index=True)[COLUMNS].sort_values("canonical_key")
    out.to_csv(REGISTRY, index=False)
    print(f"pinned: +{len(add)} new, {len(retired)} retired, {len(out)} rows total")

    if args.migration and retired:
        if not args.previous_core_dir:
            raise SystemExit("--previous-core-dir is required to map retired CKs")
        old = pd.read_parquet(Path(args.previous_core_dir) / "ck_observation.parquet")
        old = old[old.canonical_key.isin(retired)][["canonical_key", "geom_obs_id"]]
        now = dict(zip(obs.geom_obs_id, obs.canonical_key))
        old["new_ck"] = old.geom_obs_id.map(now)
        m = (old.groupby(["canonical_key", "new_ck"], dropna=False).size().rename("n_obs").reset_index())
        m["share_of_observations"] = m.n_obs / m.groupby("canonical_key").n_obs.transform("sum")
        m = m.rename(columns={"canonical_key": "old_ck"}).sort_values(["old_ck", "new_ck"])
        m.to_csv(args.migration, index=False)
        print(f"migration map: {len(m)} rows -> {args.migration}")


if __name__ == "__main__":
    main()
