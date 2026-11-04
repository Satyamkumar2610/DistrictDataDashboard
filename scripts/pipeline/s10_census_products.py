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
    area_km2_low / area_km2_high bound each weight by the overlay classes:
    low = CORE + TRANSFER only, high = everything that overlaps (adding
    BOUNDARY_DISPLACEMENT and SLIVER). The gap is the measured disagreement
    between the two map editions along that boundary, not a statistical
    confidence interval; area_km2 (low + displacement) is the point value.
crosswalk_adjacent
    The same, between consecutive vintages (from the ADJACENT overlays), for
    panels built on an older geography than the reference map.
ck_district_code
    Every district code the source layers carry (census codes 1951-1981,
    2001, 2011; LGD in 2021; source IDs elsewhere) -> CK, long format. The
    code system label is the one configured in config/sources.yaml; IDs not
    verified as an official code system are labelled source_id_*.
name_gazetteer
    Every name a CK is known by: map names per vintage, documentary aliases,
    and names the events compilation uses that s09 linked with geometric
    support. n_cks_with_name > 1 marks a name that is NOT a safe join key.
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


def adjacent_crosswalk() -> pd.DataFrame:
    f = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "ck_flow.parquet")
    x = pd.DataFrame({"year_a": f.year_a, "year_b": f.year_b, "source_ck": f.from_ck, "target_ck": f.to_ck,
                      "area_km2": f.total_km2 - f.sliver_km2, "area_km2_low": f.material_km2,
                      "area_km2_high": f.total_km2, "source_area": f.from_area, "target_area": f.to_area})
    x = x[x.area_km2 > 0].copy()
    x["share_of_source"] = (x.area_km2 / x.source_area).clip(upper=1.0)
    x["share_of_target"] = (x.area_km2 / x.target_area).clip(upper=1.0)
    x["source_mapped_share"] = x.groupby(["year_a", "source_ck"]).share_of_source.transform("sum").clip(upper=1.0)
    return x.drop(columns=["source_area", "target_area"]).sort_values(
        ["year_a", "target_ck", "area_km2"], ascending=[True, True, False])


def district_codes(obs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source, year in lib.VINTAGES:
        fields = lib.sources_config()[source]["datasets"][str(year)].get("code_fields") or {}
        attrs = lib.bronze_attributes(year, list(fields.values()))
        attrs = attrs.merge(obs[obs.year == year][["geom_obs_id", "canonical_key", "district_name"]], on="geom_obs_id")
        for system, col in sorted(fields.items()):
            v = attrs[col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
            ok = ~v.isin(["", "None", "nan", "NaN"]) & ~v.str.fullmatch(r"0+")
            rows.append(pd.DataFrame({"year": year, "code_system": system, "source_field": col, "code": v[ok],
                                      "canonical_key": attrs.canonical_key[ok],
                                      "district_name": attrs.district_name[ok]}))
    return pd.concat(rows, ignore_index=True).sort_values(["year", "code_system", "code", "canonical_key"])


def gazetteer(obs: pd.DataFrame, reg: pd.DataFrame) -> pd.DataFrame:
    m = obs.assign(name_norm=obs.district_name.map(lib.normalize_name), evidence="MAP")
    rows = [m[["name_norm", "district_name", "canonical_key", "state", "year", "evidence"]].rename(
        columns={"district_name": "name_variant"})]
    a = lib.name_aliases()
    known = m.drop_duplicates(["name_norm", "canonical_key"])
    for alias, canon, raw, st in zip(a.alias_norm, a.canonical_norm, a.alias_name, a.state_norm):
        hit = known[(known.name_norm.isin([canon, alias]))
                    & known.state.map(lambda s: lib.normalize_name(lib.canonical_state(s))).isin(
                        lib.compatible_states(st))]
        rows.append(pd.DataFrame({"name_norm": alias, "name_variant": raw, "canonical_key": hit.canonical_key,
                                  "state": hit.state, "year": hit.year, "evidence": "ALIAS"}))
    lk = pd.read_parquet(lib.GOLD_EVENTS_DIR / "event_linkage.parquet")
    pt = pd.read_parquet(lib.GOLD_EVENTS_DIR / "event_participant.parquet")
    lk = lk[lk.link_status.isin(["LINKED", "RETAINED_SELF"])].merge(
        pt[["participant_id", "district_name_raw", "name_norm"]], on="participant_id")
    rows.append(pd.DataFrame({"name_norm": lk.name_norm, "name_variant": lk.district_name_raw,
                              "canonical_key": lk.canonical_key, "state": lk.canonical_key.map(reg.latest_state),
                              "year": lk.vintage.astype(int), "evidence": "EVENT"}))
    g = pd.concat(rows, ignore_index=True)
    g = g[g.name_norm.str.len() > 0]
    out = (g.groupby(["name_norm", "canonical_key", "evidence"], as_index=False)
           .agg(name_variant=("name_variant", lambda s: "; ".join(sorted(set(map(str, s))))),
                state=("state", lambda s: "; ".join(sorted(set(map(str, s))))),
                first_year=("year", "min"), last_year=("year", "max")))
    out["n_cks_with_name"] = out.groupby("name_norm").canonical_key.transform("nunique").astype(int)
    out["latest_name"] = out.canonical_key.map(reg.latest_name)
    return out.sort_values(["name_norm", "canonical_key", "evidence"]).reset_index(drop=True)


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
                     area_km2=flow.total_km2 - flow.sliver_km2, area_km2_low=flow.material_km2,
                     area_km2_high=flow.total_km2)
    xw = xw.rename(columns={"year_a": "year"}).groupby(["year", "source_ck", "target_ck"], as_index=False)[
        ["area_km2", "area_km2_low", "area_km2_high"]].sum()
    ref = obs[obs.year == REF]
    xw = pd.concat([xw, pd.DataFrame({"year": REF, "source_ck": ref.canonical_key, "target_ck": ref.canonical_key,
                                      "area_km2": ref.area_km2, "area_km2_low": ref.area_km2,
                                      "area_km2_high": ref.area_km2})])
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
    # 2025 territory the year-Y map does not depict at all (claimed territory drawn
    # differently, coastline): it has no year-Y statistics behind it.
    res = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "transition_residual.parquet")
    res = res[(res.kind == "REFERENCE") & (res.side == "TARGET")]
    nd = res.assign(target_ck=res.geom_obs_id.map(ck)).set_index(["target_ck", "year_a"]).unmapped_km2
    ctx["not_depicted_km2"] = [0.0 if y == REF else float(nd.get((t, y), 0.0)) for t, y in zip(ctx.target_ck, ctx.year)]
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

    adj = adjacent_crosswalk()
    lib.write_table(adj, lib.PRODUCTS_DIR / "crosswalk_adjacent.parquet", "crosswalk_adjacent",
                    csv_copy=lib.PRODUCTS_DIR / "crosswalk_adjacent.csv")
    codes = district_codes(obs)
    lib.write_table(codes, lib.PRODUCTS_DIR / "ck_district_code.parquet", "ck_district_code",
                    csv_copy=lib.PRODUCTS_DIR / "ck_district_code.csv")
    gaz = gazetteer(obs, reg)
    lib.write_table(gaz, lib.PRODUCTS_DIR / "name_gazetteer.parquet", "name_gazetteer",
                    csv_copy=lib.PRODUCTS_DIR / "name_gazetteer.csv")

    print(f"admin rows: {len(admin)}  crosswalk rows: {len(xw)}  context rows: {len(ctx)}  "
          f"continuity rows: {len(cont)}  adjacent crosswalk rows: {len(adj)}")
    print(f"district codes: {len(codes)} ({codes.code_system.nunique()} systems; codes mapping to >1 CK in a "
          f"year: {int(codes.duplicated(['year', 'code_system', 'code'], keep=False).sum())})  gazetteer names: "
          f"{gaz.name_norm.nunique()} (ambiguous: {gaz[gaz.n_cks_with_name > 1].name_norm.nunique()})")
    print(f"sources with < 99% mapped into the reference map: {(xw.drop_duplicates(['year', 'source_ck']).source_mapped_share < 0.99).sum()}")
    print(xw.groupby("year").agg(rows=("area_km2", "size"), km2=("area_km2", "sum")).round(0).to_string())


if __name__ == "__main__":
    main()
