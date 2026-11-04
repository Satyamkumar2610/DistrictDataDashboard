"""Stage 06 — District area ledger: where each district's territory went and
where its new territory came from, window by window. One row per CK present at
either end of the window (area_before = 0 for a CK established at year_b,
area_after = 0 for one that closed). Both directions close exactly by
construction from the s03 partition (within closure tolerance):

  OUT  retained + to_new_districts + to_existing_districts + displacement
           + sliver + unmapped                         == area_before
  IN   kept_in + received + received_displacement + received_sliver
           + coverage_gain                             == area_after

unmapped_km2 (coverage loss) is source territory the later map does not cover;
coverage_gain_km2 is target territory the earlier map did not cover (e.g. the
2011 -> 2021 Stanford layers differ by ~123,000 km2 of depicted claimed
territory in the north). Before v4 only the OUT side was recorded, so gained
coverage was invisible.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402


def main() -> None:
    reg = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_registry.parquet")
    established = dict(zip(reg.canonical_key, reg.established_year))
    obs = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")
    f = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "ck_flow.parquet")
    res = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "transition_residual.parquet")
    res = res[res.kind == "ADJACENT"]
    unmapped = res[res.side == "SOURCE"].set_index(["geom_obs_id", "year_a"]).unmapped_km2
    gained = res[res.side == "TARGET"].set_index(["geom_obs_id", "year_b"]).unmapped_km2

    self_ = f.from_ck == f.to_ck
    to_new = ~self_ & (f.to_ck.map(established) == f.year_b)
    f = f.assign(
        retained_km2=np.where(self_, f.total_km2 - f.sliver_km2, 0.0),
        to_new_districts_km2=np.where(to_new, f.material_km2, 0.0),
        to_existing_districts_km2=np.where(~self_ & ~to_new, f.material_km2, 0.0),
        displacement_out_km2=np.where(~self_, f.displacement_km2, 0.0))
    out = f.groupby(["from_ck", "year_a", "year_b"], as_index=False)[
        ["retained_km2", "to_new_districts_km2", "to_existing_districts_km2",
         "displacement_out_km2", "sliver_km2"]].sum()
    inflow = f.assign(kept_in_km2=np.where(self_, f.total_km2, 0.0),
                      received_km2=np.where(self_, 0.0, f.material_km2),
                      received_displacement_km2=np.where(self_, 0.0, f.displacement_km2),
                      received_sliver_km2=np.where(self_, 0.0, f.sliver_km2))
    received = inflow.groupby(["to_ck", "year_b"], as_index=False)[
        ["kept_in_km2", "received_km2", "received_displacement_km2", "received_sliver_km2"]].sum()
    in_parts = ["kept_in_km2", "received_km2", "received_displacement_km2", "received_sliver_km2",
                "coverage_gain_km2"]

    rows = []
    for ya, yb in lib.WINDOWS:
        before = obs[obs.year == ya][["geom_obs_id", "canonical_key", "area_km2"]].rename(
            columns={"geom_obs_id": "obs_a", "area_km2": "area_before_km2"})
        after = obs[obs.year == yb][["geom_obs_id", "canonical_key", "area_km2"]].rename(
            columns={"geom_obs_id": "obs_b", "area_km2": "area_after_km2"})
        o = before.merge(after, on="canonical_key", how="outer")
        o[["area_before_km2", "area_after_km2"]] = o[["area_before_km2", "area_after_km2"]].fillna(0.0)
        o = o.merge(out[out.year_a == ya].drop(columns=["year_a", "year_b"]),
                    left_on="canonical_key", right_on="from_ck", how="left").drop(columns="from_ck")
        o["unmapped_km2"] = [unmapped.get((g, ya), 0.0) if isinstance(g, str) else 0.0 for g in o.obs_a]
        o["coverage_gain_km2"] = [gained.get((g, yb), 0.0) if isinstance(g, str) else 0.0 for g in o.obs_b]
        o = o.merge(received[received.year_b == yb].drop(columns="year_b"),
                    left_on="canonical_key", right_on="to_ck", how="left").drop(columns="to_ck")
        num = [c for c in o.columns if c.endswith("_km2")]
        o[num] = o[num].fillna(0.0)
        o["year_a"], o["year_b"] = ya, yb
        rows.append(o)
    led = pd.concat(rows, ignore_index=True).rename(columns={
        "area_km2": "area_before_km2", "displacement_out_km2": "displacement_km2"})
    parts = ["retained_km2", "to_new_districts_km2", "to_existing_districts_km2",
             "displacement_km2", "sliver_km2", "unmapped_km2"]
    led["closure_error_km2"] = (led[parts].sum(axis=1) - led.area_before_km2).abs()
    led["closure_ok"] = lib.within_closure(led.closure_error_km2, led.area_before_km2)
    led["forward_closure_error_km2"] = (led[in_parts].sum(axis=1) - led.area_after_km2).abs()
    led["forward_closure_ok"] = lib.within_closure(led.forward_closure_error_km2, led.area_after_km2)
    led = led[["canonical_key", "year_a", "year_b", "area_before_km2", *parts, "closure_error_km2", "closure_ok",
               "area_after_km2", *in_parts, "forward_closure_error_km2", "forward_closure_ok"]
              ].sort_values(["year_a", "canonical_key"])
    lib.write_table(led, lib.PRODUCTS_DIR / "district_area_ledger.parquet", "area_ledger",
                    csv_copy=lib.PRODUCTS_DIR / "district_area_ledger.csv")
    print(f"ledger rows: {len(led)}  closure ok: {led.closure_ok.mean():.4%}  "
          f"max error: {led.closure_error_km2.max():.3f} km2  forward closure ok: "
          f"{led.forward_closure_ok.mean():.4%}  max forward error: {led.forward_closure_error_km2.max():.3f} km2")


if __name__ == "__main__":
    main()
