"""Stage 06 — District area ledger: where each district's territory went,
window by window. Exact by construction from the s03 partition:

  retained + to_new_districts + to_existing_districts + displacement
      + sliver + unmapped == area_before              (within closure tolerance)

received_km2 is material territory gained from other districts in the window.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from district_evolution import core


def main() -> None:
    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet")
    established = dict(zip(reg.canonical_key, reg.established_year, strict=True))
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    f = pd.read_parquet(core.GOLD_SPATIAL_DIR / "ck_flow.parquet")
    res = pd.read_parquet(core.GOLD_SPATIAL_DIR / "transition_residual.parquet")
    res = res[(res.kind == "ADJACENT") & (res.side == "SOURCE")]
    unmapped = res.set_index(["geom_obs_id", "year_a"]).unmapped_km2

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
    received = (f[~self_].groupby(["to_ck", "year_b"]).material_km2.sum()
                .rename("received_km2").reset_index())

    rows = []
    for ya, yb in core.WINDOWS:
        o = obs[obs.year == ya][["geom_obs_id", "canonical_key", "area_km2"]]
        o = o.merge(out[out.year_a == ya].drop(columns=["year_a", "year_b"]),
                    left_on="canonical_key", right_on="from_ck", how="left").fillna(0.0)
        o["unmapped_km2"] = [unmapped.get((g, ya), 0.0) for g in o.geom_obs_id]
        o = o.merge(received[received.year_b == yb].drop(columns="year_b"),
                    left_on="canonical_key", right_on="to_ck", how="left")
        o["received_km2"] = o["received_km2"].fillna(0.0)
        o["year_a"], o["year_b"] = ya, yb
        rows.append(o)
    led = pd.concat(rows, ignore_index=True).rename(columns={
        "area_km2": "area_before_km2", "displacement_out_km2": "displacement_km2"})
    parts = ["retained_km2", "to_new_districts_km2", "to_existing_districts_km2",
             "displacement_km2", "sliver_km2", "unmapped_km2"]
    led["closure_error_km2"] = (led[parts].sum(axis=1) - led.area_before_km2).abs()
    led["closure_ok"] = core.within_closure(led.closure_error_km2, led.area_before_km2)
    led = led[["canonical_key", "year_a", "year_b", "area_before_km2", *parts, "received_km2",
               "closure_error_km2", "closure_ok"]].sort_values(["year_a", "canonical_key"])
    core.write_table(led, core.PRODUCTS_DIR / "district_area_ledger.parquet", "area_ledger",
                    csv_copy=core.PRODUCTS_DIR / "district_area_ledger.csv")
    print(f"ledger rows: {len(led)}  closure ok: {led.closure_ok.mean():.4%}  "
          f"max error: {led.closure_error_km2.max():.3f} km2")


if __name__ == "__main__":
    main()
