"""Stage 10h — Harmonization: measured uncertainty, comparable units, restated census.

Runs after s10 (it uses the crosswalks) and before the warehouse. Every product
here has one stated meaning:

census_attribute
    The census totals the source layers carry with each district polygon
    (population 1951-2001; census-reported area 1961-2001), keyed to CKs.
    0 in the source means "not enumerated" (Assam 1981, J&K 1991) -> NULL. Area
    units are detected per vintage from the data (1961 is in square miles).
district_area_uncertainty
    Per district observation: relative area uncertainty = sigma * perimeter /
    area, with sigma (km) MEASURED as the median of |map area - census area| /
    perimeter over all districts that have both. Small, long-boundary districts
    (Delhi, Mahe, Yanam) are uncertain; large rural ones are not.
comparable_unit, comparable_unit_member
    For each start year S: the smallest groups of districts whose combined
    territory is the same in every vintage S..2025 (connected components of
    the material-flow graph). Statistics summed to these units are comparable
    WITHOUT any interpolation assumption, up to max_leakage_share.
population_on_reference
    Census population of year Y restated onto 2025 districts by area weights
    (harmonize.restate), with the map-edition envelope and coverage.
population_on_units
    Census population of every year >= S summed exactly to start-year-S units.
harmonization_backtest
    How wrong is area weighting? Population of census Y is restated onto the
    districts of census Y+10 and compared with what Y+10 enumerated, after
    removing state-level growth. Districts whose territory did not change
    measure differential growth alone; restated ones add the area-weighting
    error. The excess is the error attributable to the uniform-density
    assumption, with bootstrap confidence intervals. RMSE is dominated by a
    tail (urban cores carved out of a rural district, e.g. Hyderabad 1971-81
    holding 1% of its parent's area and most of its people; mountain districts
    whose population lives in a few valleys), so the median absolute log error
    and the share of districts off by more than a factor of 1.65 (|log| > 0.5)
    are reported beside it. s10h_backtest_districts.csv lists every district.
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harmonize  # noqa: E402
import lib  # noqa: E402

REF = lib.REFERENCE_YEAR
UNC = lib.CFG["uncertainty"]
BT = lib.CFG["backtest"]


# ---------------------------------------------------------------------------
# census attributes and area calibration
# ---------------------------------------------------------------------------

def census_attributes(obs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, units = [], []
    for source, year in lib.VINTAGES:
        fields = lib.sources_config()[source]["datasets"][str(year)].get("attribute_fields") or {}
        if not fields:
            continue
        a = lib.bronze_attributes(year, list(fields.values())).merge(
            obs[obs.year == year][["geom_obs_id", "canonical_key", "area_km2"]], on="geom_obs_id")
        pop = pd.to_numeric(a[fields["population"]], errors="coerce") if "population" in fields else np.nan
        out = pd.DataFrame({"year": year, "geom_obs_id": a.geom_obs_id, "canonical_key": a.canonical_key,
                            "population": pd.Series(pop).where(pd.Series(pop) > 0) if "population" in fields
                            else np.nan,
                            "census_area_raw": np.nan, "census_area_km2": np.nan, "area_unit": None})
        if "area" in fields:
            raw = pd.to_numeric(a[fields["area"]], errors="coerce").where(lambda s: s > 0)
            ok = raw.notna()
            ratio = a.area_km2[ok].sum() / raw[ok].sum()
            unit, factor = min(UNC["unit_factors"].items(), key=lambda kv: abs(np.log(ratio / kv[1])))
            accepted = abs(np.log(ratio / factor)) < np.log(1.25)
            units.append({"year": year, "field": fields["area"], "n_with_area": int(ok.sum()),
                          "map_over_census_ratio": ratio, "unit": unit if accepted else "UNKNOWN",
                          "factor": factor if accepted else np.nan})
            out["census_area_raw"] = raw.values
            if accepted:
                out["census_area_km2"] = (raw * factor).values
                out["area_unit"] = unit
        rows.append(out)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(units)


def spearman(a: pd.Series, b: pd.Series) -> float:
    """Spearman rank correlation (Pearson on ranks; avoids a scipy dependency)."""
    return float(a.rank().corr(b.rank()))


def calibrate_sigma(attr: pd.DataFrame, geo: pd.DataFrame, obs: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    d = attr.dropna(subset=["census_area_km2"]).merge(geo, on="geom_obs_id").merge(
        obs[["geom_obs_id", "area_km2"]], on="geom_obs_id")
    d["abs_diff_km2"] = (d.area_km2 - d.census_area_km2).abs()
    d["sigma_i_km"] = d.abs_diff_km2 / d.perimeter_km
    d["rel_diff"] = (d.area_km2 - d.census_area_km2) / d.census_area_km2
    rows = [{"scope": str(y), "n": len(g), "median_sigma_km": g.sigma_i_km.median(),
             "median_abs_rel_diff": g.rel_diff.abs().median(),
             "spearman_absrel_vs_perim_over_area": spearman(g.rel_diff.abs(), g.perimeter_km / g.area_km2)}
            for y, g in d.groupby("year")]
    pooled = {"scope": "pooled", "n": len(d), "median_sigma_km": d.sigma_i_km.median(),
              "median_abs_rel_diff": d.rel_diff.abs().median(),
              "spearman_absrel_vs_perim_over_area": spearman(d.rel_diff.abs(), d.perimeter_km / d.area_km2)}
    cal = pd.DataFrame(rows + [pooled])
    sigma = float(pooled["median_sigma_km"]) if len(d) >= UNC["min_calibration_districts"] else UNC["fallback_sigma_km"]
    cal["sigma_used_km"] = sigma
    return sigma, cal


# ---------------------------------------------------------------------------
# comparable units
# ---------------------------------------------------------------------------

def comparable_units(flow: pd.DataFrame, obs: pd.DataFrame, reg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mat, share = lib.CFG["lineage"]["material_km2"], lib.CFG["units"]["min_share"]
    f = flow.assign(s_src=flow.material_km2 / flow.from_area, s_tgt=flow.material_km2 / flow.to_area)
    f["joins"] = (f.from_ck == f.to_ck) | ((f.material_km2 >= mat) & ((f.s_src >= share) | (f.s_tgt >= share)))
    area = obs.set_index(["canonical_key", "year"]).area_km2
    members, units = [], []
    for s in [y for y in lib.YEARS if y < REF]:
        years = [y for y in lib.YEARS if y >= s]
        g = nx.Graph()
        g.add_nodes_from((y, c) for y, c in zip(obs.year, obs.canonical_key) if y >= s)
        w = f[f.year_a >= s]
        j = w[w.joins]
        for a, b, x, y in zip(j.year_a, j.year_b, j.from_ck, j.to_ck):
            g.add_edge((a, x), (b, y))
        comp = {}
        for nodes in nx.connected_components(g):
            key = sorted(f"{y}:{c}" for y, c in nodes)
            uid = f"U{s}-{lib.stable_id('UNIT', s, *key)[:10]}"
            for n in nodes:
                comp[n] = uid
        m = pd.DataFrame([(uid, y, c) for (y, c), uid in comp.items()], columns=["unit_id", "year", "canonical_key"])
        # connected_components iterates sets (hash-seed dependent order): sort before any float sum
        m = m.sort_values(["unit_id", "year", "canonical_key"]).reset_index(drop=True)
        m["area_km2"] = [area[(c, y)] for c, y in zip(m.canonical_key, m.year)]
        m.insert(0, "start_year", s)
        members.append(m)
        # leakage: material that crosses between units (below the join threshold)
        cross = w[[comp.get((a, x)) != comp.get((b, y)) for a, b, x, y in zip(w.year_a, w.year_b, w.from_ck, w.to_ck)]]
        ua = m.groupby(["unit_id", "year"]).area_km2.sum()
        leak = []
        for a, b, x, y, km2 in zip(cross.year_a, cross.year_b, cross.from_ck, cross.to_ck, cross.material_km2):
            leak.append((comp[(a, x)], a, km2))
            leak.append((comp[(b, y)], b, km2))
        lk = pd.DataFrame(leak, columns=["unit_id", "year", "km2"]).groupby(["unit_id", "year"]).km2.sum()
        lshare = (lk / ua.reindex(lk.index)).groupby(level=0).max() if len(lk) else pd.Series(dtype=float)
        ref_m = m[m.year == REF]
        u = m.groupby("unit_id").agg(n_district_observations=("canonical_key", "size")).reset_index()
        u["n_reference_districts"] = u.unit_id.map(ref_m.groupby("unit_id").size()).fillna(0).astype(int)
        u["n_start_year_districts"] = u.unit_id.map(m[m.year == s].groupby("unit_id").size()).fillna(0).astype(int)
        u["area_reference_km2"] = u.unit_id.map(ref_m.groupby("unit_id").area_km2.sum()).fillna(0.0)
        u["max_leakage_share"] = u.unit_id.map(lshare).fillna(0.0).clip(upper=1.0)
        u["reference_districts"] = u.unit_id.map(ref_m.groupby("unit_id").canonical_key.apply(
            lambda c: "; ".join(sorted(reg.latest_name.get(k, k) for k in c))))
        u.insert(0, "start_year", s)
        units.append(u)
        print(f"[units from {s}] {len(u)} units for {len(ref_m)} reference districts over {len(years)} vintages; "
              f"median leakage {u.max_leakage_share.median():.4f}, max {u.max_leakage_share.max():.4f}")
    return (pd.concat(units, ignore_index=True).sort_values(["start_year", "unit_id"]),
            pd.concat(members, ignore_index=True).sort_values(["start_year", "unit_id", "year", "canonical_key"]))


# ---------------------------------------------------------------------------
# back-test of area weighting
# ---------------------------------------------------------------------------

def _rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else np.nan


def _boot(rng, groups: dict[str, np.ndarray], stat) -> tuple[float, float]:
    vals = []
    for _ in range(BT["bootstrap"]):
        vals.append(stat({k: v[rng.integers(0, len(v), len(v))] if len(v) else v for k, v in groups.items()}))
    vals = np.array([v for v in vals if np.isfinite(v)])
    return (float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))) if len(vals) else (np.nan, np.nan)


def backtest(attr: pd.DataFrame, adj: pd.DataFrame, obs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pop_years = sorted(attr.dropna(subset=["population"]).year.unique())
    area = obs.set_index(["canonical_key", "year"]).area_km2
    state = obs.set_index(["canonical_key", "year"]).state
    detail = []
    for a, b in zip(pop_years[:-1], pop_years[1:]):
        if (a, b) not in lib.WINDOWS:
            continue
        x = adj[(adj.year_a == a)]
        pa = attr[attr.year == a][["canonical_key", "population"]].rename(columns={"canonical_key": "source_ck",
                                                                                   "population": "value"})
        pb = attr[attr.year == b].set_index("canonical_key").population
        src_area = pd.Series({c: area[(c, a)] for c in x.source_ck.unique()})
        tgt_area = pd.Series({c: area[(c, b)] for c in x.target_ck.unique()})
        r = harmonize.restate(pa, x, src_area, tgt_area)
        main = x.sort_values("area_km2", ascending=False).drop_duplicates("target_ck").set_index("target_ck")
        r["main_source_share_of_source"] = r.target_ck.map(main.share_of_source)
        r["actual"] = r.target_ck.map(pb)
        r = r[(r.coverage_share >= BT["min_coverage"]) & r.actual.notna() & (r.value > 0)].copy()
        r["state"] = [lib.canonical_state(state[(c, b)]) for c in r.target_ck]
        g = r.groupby("state").actual.sum() / r.groupby("state").value.sum()
        r["predicted"] = r.value * r.state.map(g)
        r["log_error"] = np.log(r.actual / r.predicted)
        u = BT["unchanged_share"]
        unchanged = (r.largest_source_share >= u) & (r.main_source_share_of_source >= u)
        restated = (r.largest_source_share < BT["restated_max_share"]) | (
            r.main_source_share_of_source < BT["restated_max_share"])
        r["group"] = np.select([unchanged, restated], ["UNCHANGED", "RESTATED"], default="INTERMEDIATE")
        r["window"] = f"{a}-{b}"
        r = r[r.state.map(r.groupby("state").size()) >= 2]  # a one-district state has no growth contrast
        detail.append(r)
    det = pd.concat(detail, ignore_index=True)
    rng = np.random.default_rng(BT["seed"])
    rows = []
    for win, d in [*det.groupby("window"), ("pooled", det)]:
        e = {k: d.log_error[d.group == k].to_numpy() for k in ("UNCHANGED", "RESTATED", "INTERMEDIATE")}
        robust = {"rmse_log": _rmse,
                  "median_abs_log": lambda v: float(np.median(np.abs(v))) if len(v) else np.nan,
                  "share_off_by_factor_1_65": lambda v: float(np.mean(np.abs(v) > 0.5)) if len(v) else np.nan}
        for k in ("UNCHANGED", "RESTATED", "INTERMEDIATE"):
            for name, fn in robust.items():
                lo, hi = _boot(rng, {k: e[k]}, lambda s, k=k, fn=fn: fn(s[k]))
                rows.append({"window": win, "measure": f"{name}_{k.lower()}", "n": len(e[k]),
                             "estimate": fn(e[k]), "ci_low": lo, "ci_high": hi})

        def excess(s):
            return float(np.sqrt(max(0.0, np.mean(np.square(s["RESTATED"])) - np.mean(np.square(s["UNCHANGED"])))))
        lo, hi = _boot(rng, {"RESTATED": e["RESTATED"], "UNCHANGED": e["UNCHANGED"]}, excess)
        rows.append({"window": win, "measure": "rmse_log_attributable_to_area_weighting",
                     "n": len(e["RESTATED"]), "estimate": excess(e), "ci_low": lo, "ci_high": hi})
    keep = ["window", "target_ck", "state", "group", "actual", "predicted", "log_error", "coverage_share",
            "largest_source_share", "main_source_share_of_source", "n_sources"]
    return pd.DataFrame(rows), det[keep]


# ---------------------------------------------------------------------------

def main() -> None:
    obs = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")
    reg = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    geo = pd.concat([pd.read_parquet(lib.silver_path(y), columns=["geom_obs_id", "perimeter_km"]) for y in lib.YEARS])

    attr, units_found = census_attributes(obs)
    lib.write_table(attr.sort_values(["year", "canonical_key"]), lib.PRODUCTS_DIR / "census_attribute.parquet",
                    "census_attribute", csv_copy=lib.PRODUCTS_DIR / "census_attribute.csv")
    units_found.to_csv(lib.OUTPUT_DIR / "s10h_census_area_units.csv", index=False)

    sigma, cal = calibrate_sigma(attr, geo, obs)
    cal.to_csv(lib.OUTPUT_DIR / "s10h_area_calibration.csv", index=False)
    unc = obs[["geom_obs_id", "canonical_key", "year", "area_km2"]].merge(geo, on="geom_obs_id").merge(
        attr[["geom_obs_id", "census_area_km2"]], on="geom_obs_id", how="left")
    unc["sigma_km"] = sigma
    unc["area_rel_uncertainty"] = sigma * unc.perimeter_km / unc.area_km2
    unc["area_km2_low"] = (unc.area_km2 * (1 - unc.area_rel_uncertainty)).clip(lower=0.0)
    unc["area_km2_high"] = unc.area_km2 * (1 + unc.area_rel_uncertainty)
    unc["rel_diff_vs_census"] = (unc.area_km2 - unc.census_area_km2) / unc.census_area_km2
    unc["high_uncertainty"] = unc.area_rel_uncertainty > UNC["flag_rel"]
    lib.write_table(unc.drop(columns="geom_obs_id").sort_values(["canonical_key", "year"]),
                    lib.PRODUCTS_DIR / "district_area_uncertainty.parquet", "district_area_uncertainty",
                    csv_copy=lib.PRODUCTS_DIR / "district_area_uncertainty.csv")

    flow = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "ck_flow.parquet")
    units, members = comparable_units(flow, obs, reg)
    lib.write_table(units, lib.PRODUCTS_DIR / "comparable_unit.parquet", "comparable_unit",
                    csv_copy=lib.PRODUCTS_DIR / "comparable_unit.csv")
    lib.write_table(members, lib.PRODUCTS_DIR / "comparable_unit_member.parquet", "comparable_unit_member",
                    csv_copy=lib.PRODUCTS_DIR / "comparable_unit_member.csv")

    xw = pd.read_parquet(lib.PRODUCTS_DIR / "crosswalk_to_reference.parquet")
    area = obs.set_index(["canonical_key", "year"]).area_km2
    tgt_area = obs[obs.year == REF].set_index("canonical_key").area_km2
    pop_years = sorted(attr.dropna(subset=["population"]).year.unique())
    por, pou = [], []
    for y in pop_years:
        vals = attr[attr.year == y][["canonical_key", "population"]].rename(
            columns={"canonical_key": "source_ck", "population": "value"})
        x = xw[xw.year == y]
        r = harmonize.restate(vals, x, pd.Series({c: area[(c, y)] for c in x.source_ck.unique()}), tgt_area)
        por.append(r.rename(columns={"value": "population", "value_low": "population_low",
                                     "value_high": "population_high"}).assign(year=y))
        for s in [s for s in pop_years if s <= y]:
            a = harmonize.aggregate_to_units(vals, members[members.start_year == s], y)
            pou.append(a.rename(columns={"value": "population"}).assign(start_year=s, year=y))
    por = pd.concat(por, ignore_index=True)[["year", "target_ck", "population", "population_low", "population_high",
                                            "coverage_share", "n_sources", "largest_source_share"]]
    lib.write_table(por.sort_values(["year", "target_ck"]), lib.PRODUCTS_DIR / "population_on_reference.parquet",
                    "population_on_reference", csv_copy=lib.PRODUCTS_DIR / "population_on_reference.csv")
    pou = pd.concat(pou, ignore_index=True)[["start_year", "unit_id", "year", "population", "complete", "n_districts"]]
    lib.write_table(pou.sort_values(["start_year", "unit_id", "year"]), lib.PRODUCTS_DIR / "population_on_units.parquet",
                    "population_on_units", csv_copy=lib.PRODUCTS_DIR / "population_on_units.csv")

    adj = pd.read_parquet(lib.PRODUCTS_DIR / "crosswalk_adjacent.parquet")
    bt, det = backtest(attr, adj, obs)
    lib.write_table(bt, lib.PRODUCTS_DIR / "harmonization_backtest.parquet", "harmonization_backtest",
                    csv_copy=lib.PRODUCTS_DIR / "harmonization_backtest.csv")
    det.to_csv(lib.OUTPUT_DIR / "s10h_backtest_districts.csv", index=False)

    print(units_found.to_string(index=False))
    print(cal.round(4).to_string(index=False))
    print(f"area uncertainty: sigma {sigma:.3f} km; high-uncertainty observations "
          f"{int(unc.high_uncertainty.sum())} / {len(unc)}")
    print(f"population on reference: {len(por)} rows; national totals by year (restated vs enumerated):")
    tot = por.groupby("year").population.sum() / attr.groupby("year").population.sum().reindex(pop_years)
    print(tot.round(4).to_string())
    print(bt[bt.window == "pooled"].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
