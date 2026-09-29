"""Stage 10 — Census products. One meaning per product (plan section 3.5).

district_area_admin
    Area of the administrative district as it existed at census year Y.
    One row per (CK, year) the district was mapped. Replaces the v2 matrix
    that no script produced.
crosswalk_to_reference
    km2 of district i (year Y) lying inside reference-year district j, from a
    DIRECT overlay of Y onto the reference map (s03 REFERENCE flows), so there
    is no chaining through intermediate vintages and no uniform-distribution
    assumption. Sliver noise is excluded; boundary displacement is kept (it is
    where the older map places that district). This is the area weight that
    statistical harmonization starts from.
district_reference_context
    For each reference-year district and each year Y: how much of it was
    mapped, how many Y districts it drew on, and its primary Y container
    with that container's administrative area. Replaces v2's backfill, which
    mixed "district extent then" with "today's land then" in one column.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core

REF = core.REFERENCE_YEAR
MIN_SOURCE_SHARE = 0.01  # a source counts as "drawn on" if it supplies >= 1% of the target


def main() -> None:
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    ck = dict(zip(obs.geom_obs_id, obs.canonical_key))

    admin = obs[["canonical_key", "year", "district_name", "state", "area_km2"]].sort_values(["canonical_key", "year"])
    # the year these boundaries actually depict (differs from the map label for confirmed cases)
    admin.insert(2, "depicted_year", [core.depicted_year(s, y) for s, y in zip(admin.state, admin.year)])
    core.write_table(admin, core.PRODUCTS_DIR / "district_area_admin.parquet", "district_area_admin",
                    csv_copy=core.PRODUCTS_DIR / "district_area_admin.csv")
    wide = admin.pivot(index="canonical_key", columns="year", values="area_km2").add_prefix("area_km2_")
    wide.insert(0, "latest_name", reg.latest_name)
    wide.insert(1, "latest_state", reg.latest_state)
    wide.insert(2, "established_year", reg.established_year)
    wide.insert(3, "closed_year", reg.closed_year)
    wide.reset_index().to_csv(core.PRODUCTS_DIR / "district_area_admin_wide.csv", index=False)

    flow = pd.read_parquet(core.GOLD_SPATIAL_DIR / "transition_flow.parquet")
    flow = flow[(flow.kind == "REFERENCE") & (flow.year_b == REF)]
    xw = flow.assign(source_ck=flow.geom_obs_id_a.map(ck), target_ck=flow.geom_obs_id_b.map(ck),
                     area_km2=flow.total_km2 - flow.sliver_km2)
    xw = xw.rename(columns={"year_a": "year"}).groupby(["year", "source_ck", "target_ck"], as_index=False).area_km2.sum()
    ref = obs[obs.year == REF]
    xw = pd.concat([xw, pd.DataFrame({"year": REF, "source_ck": ref.canonical_key,
                                      "target_ck": ref.canonical_key, "area_km2": ref.area_km2})])
    xw = xw[xw.area_km2 > 0]
    src_area = obs.set_index(["canonical_key", "year"]).area_km2
    tgt_area = ref.set_index("canonical_key").area_km2
    xw["share_of_source"] = (xw.area_km2 / [src_area[(c, y)] for c, y in zip(xw.source_ck, xw.year)]).clip(upper=1.0)
    xw["share_of_target"] = (xw.area_km2 / xw.target_ck.map(tgt_area)).clip(upper=1.0)
    depicted = admin.set_index(["canonical_key", "year"]).depicted_year
    xw["source_depicted_year"] = [depicted[(c, y)] for c, y in zip(xw.source_ck, xw.year)]
    xw = xw.sort_values(["year", "target_ck", "area_km2"], ascending=[True, True, False])
    core.write_table(xw, core.PRODUCTS_DIR / "crosswalk_to_reference.parquet", "crosswalk_to_reference",
                    csv_copy=core.PRODUCTS_DIR / "crosswalk_to_reference.csv")

    grp = xw.groupby(["target_ck", "year"])
    primary = xw.drop_duplicates(["target_ck", "year"])  # sorted by area desc within target/year
    ctx = grp.area_km2.sum().rename("mapped_km2").to_frame()
    ctx["n_source_districts"] = grp.share_of_target.apply(lambda s: int((s >= MIN_SOURCE_SHARE).sum()))
    ctx = ctx.join(primary.set_index(["target_ck", "year"])[["source_ck", "share_of_target"]].rename(
        columns={"source_ck": "primary_source_ck", "share_of_target": "primary_share_of_target"}))
    full = pd.MultiIndex.from_product([sorted(ref.canonical_key), core.YEARS], names=["target_ck", "year"])
    ctx = ctx.reindex(full).reset_index()
    ctx["mapped_km2"] = ctx.mapped_km2.fillna(0.0)
    ctx["n_source_districts"] = ctx.n_source_districts.fillna(0).astype(int)
    ctx["primary_source_area_km2"] = [src_area.get((c, y)) if isinstance(c, str) else None
                                      for c, y in zip(ctx.primary_source_ck, ctx.year)]
    ctx["primary_source_name"] = ctx.primary_source_ck.map(reg.display_name)
    ctx["target_name"] = ctx.target_ck.map(reg.latest_name)
    ctx["target_state"] = ctx.target_ck.map(reg.latest_state)
    core.write_table(ctx, core.PRODUCTS_DIR / "district_reference_context.parquet", "district_reference_context",
                    csv_copy=core.PRODUCTS_DIR / "district_reference_context.csv")

    view = ctx.assign(cell=[f"{n} ({s:.0%})" if isinstance(n, str) else "" for n, s in
                            zip(ctx.primary_source_name, ctx.primary_share_of_target)])
    view = view.pivot(index=["target_ck", "target_name", "target_state"], columns="year", values="cell")
    view.add_prefix("contained_in_").reset_index().to_csv(
        core.PRODUCTS_DIR / "district_reference_context_wide.csv", index=False)

    print(f"admin rows: {len(admin)}  crosswalk rows: {len(xw)}  context rows: {len(ctx)}")
    print(xw.groupby("year").agg(rows=("area_km2", "size"), km2=("area_km2", "sum")).round(0).to_string())


if __name__ == "__main__":
    main()
