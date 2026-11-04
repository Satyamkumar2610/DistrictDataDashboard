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
    source_mapped_share is how much of the source district (year Y) the
    crosswalk places anywhere in the reference map (sum of share_of_source over
    its rows). It is below 1 where the reference map does not cover the old
    territory or the overlap is sliver noise; for a COUNT statistic, restated
    totals undercount by exactly that share, which this column makes visible
    instead of renormalizing it away.
district_reference_context
    For each reference-year district and each year Y: how much of it was
    mapped, how many Y districts it drew on, and its primary Y container
    with that container's administrative area. Replaces v2's backfill, which
    mixed "district extent then" with "today's land then" in one column.
ck_reference_continuity
    For each CK active at the reference year and each year Y it was mapped:
    how much of its year-Y territory lies inside its own reference polygon,
    and how much of the reference polygon that is. A CK is one administrative
    identity, not constant territory (Bastar keeps its CK from 1951 to 2025
    with 14% of its 1951 area); this is the measure a user needs before
    treating a CK's statistics as comparable across years.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

REF = lib.REFERENCE_YEAR
MIN_SOURCE_SHARE = lib.CFG["products"]["min_source_share"]


def main() -> None:
    obs = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")
    reg = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    ck = dict(zip(obs.geom_obs_id, obs.canonical_key))

    admin = obs[["canonical_key", "year", "district_name", "state", "area_km2"]].sort_values(["canonical_key", "year"])
    # the year these boundaries actually depict (differs from the map label for confirmed cases)
    admin.insert(2, "depicted_year", [lib.depicted_year(s, y) for s, y in zip(admin.state, admin.year)])
    lib.write_table(admin, lib.PRODUCTS_DIR / "district_area_admin.parquet", "district_area_admin",
                    csv_copy=lib.PRODUCTS_DIR / "district_area_admin.csv")
    wide = admin.pivot(index="canonical_key", columns="year", values="area_km2").add_prefix("area_km2_")
    wide.insert(0, "latest_name", reg.latest_name)
    wide.insert(1, "latest_state", reg.latest_state)
    wide.insert(2, "established_year", reg.established_year)
    wide.insert(3, "closed_year", reg.closed_year)
    wide.reset_index().to_csv(lib.PRODUCTS_DIR / "district_area_admin_wide.csv", index=False)

    flow = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "transition_flow.parquet")
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
    xw["source_mapped_share"] = xw.groupby(["year", "source_ck"]).share_of_source.transform("sum").clip(upper=1.0)
    depicted = admin.set_index(["canonical_key", "year"]).depicted_year
    xw["source_depicted_year"] = [depicted[(c, y)] for c, y in zip(xw.source_ck, xw.year)]
    xw = xw.sort_values(["year", "target_ck", "area_km2"], ascending=[True, True, False])
    lib.write_table(xw, lib.PRODUCTS_DIR / "crosswalk_to_reference.parquet", "crosswalk_to_reference",
                    csv_copy=lib.PRODUCTS_DIR / "crosswalk_to_reference.csv")

    grp = xw.groupby(["target_ck", "year"])
    primary = xw.drop_duplicates(["target_ck", "year"])  # sorted by area desc within target/year
    ctx = grp.area_km2.sum().rename("mapped_km2").to_frame()
    ctx["n_source_districts"] = grp.share_of_target.apply(lambda s: int((s >= MIN_SOURCE_SHARE).sum()))
    ctx = ctx.join(primary.set_index(["target_ck", "year"])[["source_ck", "share_of_target"]].rename(
        columns={"source_ck": "primary_source_ck", "share_of_target": "primary_share_of_target"}))
    full = pd.MultiIndex.from_product([sorted(ref.canonical_key), lib.YEARS], names=["target_ck", "year"])
    ctx = ctx.reindex(full).reset_index()
    ctx["mapped_km2"] = ctx.mapped_km2.fillna(0.0)
    ctx["n_source_districts"] = ctx.n_source_districts.fillna(0).astype(int)
    ctx["primary_source_area_km2"] = [src_area.get((c, y)) if isinstance(c, str) else None
                                      for c, y in zip(ctx.primary_source_ck, ctx.year)]
    ctx["primary_source_name"] = ctx.primary_source_ck.map(reg.display_name)
    ctx["target_name"] = ctx.target_ck.map(reg.latest_name)
    ctx["target_state"] = ctx.target_ck.map(reg.latest_state)
    lib.write_table(ctx, lib.PRODUCTS_DIR / "district_reference_context.parquet", "district_reference_context",
                    csv_copy=lib.PRODUCTS_DIR / "district_reference_context.csv")

    view = ctx.assign(cell=[f"{n} ({s:.0%})" if isinstance(n, str) else "" for n, s in
                            zip(ctx.primary_source_name, ctx.primary_share_of_target)])
    view = view.pivot(index=["target_ck", "target_name", "target_state"], columns="year", values="cell")
    view.add_prefix("contained_in_").reset_index().to_csv(
        lib.PRODUCTS_DIR / "district_reference_context_wide.csv", index=False)

    active = set(ref.canonical_key)
    cont = admin[admin.canonical_key.isin(active)][["canonical_key", "year", "area_km2"]].rename(
        columns={"area_km2": "area_then_km2"})
    cont["area_reference_km2"] = cont.canonical_key.map(tgt_area)
    diag = xw[xw.source_ck == xw.target_ck].set_index(["source_ck", "year"]).area_km2
    cont["shared_km2"] = [float(diag.get((c, y), 0.0)) for c, y in zip(cont.canonical_key, cont.year)]
    cont["share_of_then_kept"] = (cont.shared_km2 / cont.area_then_km2).clip(upper=1.0)
    cont["share_of_reference_from_then"] = (cont.shared_km2 / cont.area_reference_km2).clip(upper=1.0)
    lib.write_table(cont.sort_values(["canonical_key", "year"]), lib.PRODUCTS_DIR / "ck_reference_continuity.parquet",
                    "ck_reference_continuity", csv_copy=lib.PRODUCTS_DIR / "ck_reference_continuity.csv")

    print(f"admin rows: {len(admin)}  crosswalk rows: {len(xw)}  context rows: {len(ctx)}  "
          f"continuity rows: {len(cont)}")
    print(f"sources with < 99% mapped into the reference map: {(xw.drop_duplicates(['year', 'source_ck']).source_mapped_share < 0.99).sum()}")
    print(xw.groupby("year").agg(rows=("area_km2", "size"), km2=("area_km2", "sum")).round(0).to_string())


if __name__ == "__main__":
    main()
