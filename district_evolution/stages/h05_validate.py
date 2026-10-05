"""Stage h05 — Harmonization checks (harmonization_check), method sensitivity and report.

1. Conservation, per indicator, year and method: the harmonized total equals the sum over linked
   values of value x (sum of its weights). Allocation neither creates nor loses any quantity.
2. Self-check: harmonizing every district's own mapped area reproduces
   district_reference_context.mapped_km2 for every 2025 district and map (an independent s10 path).
3. Method sensitivity (harmonization_method_sensitivity): for an indicator restated with more than
   one weight method, each 2025 district's value under every other method against AREA, flagged
   when they differ by more than harmonize.sensitivity_flag_rel. Reported, never reconciled.
The stage fails if 1 or 2 fails.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from district_evolution import core
from district_evolution.contracts.schemas import SCHEMAS
from district_evolution.harmonize import methods_for, registry

TOL = core.CFG["harmonize"]
BASELINE = "AREA"
MIN_RASTER_COVER = 0.99  # report districts the raster covers less than this share of (cell-centre discretisation aside)


def sensitivity(h: pd.DataFrame) -> pd.DataFrame:
    """Every non-AREA method's value per 2025 district against AREA's, for indicators restated with both."""
    cols = list(SCHEMAS["harmonization_method_sensitivity"].columns)
    keys = ["indicator", "year", "target_ck"]
    base = h[h.method == BASELINE].set_index(keys).value.rename("baseline_value")
    parts = []
    for m in sorted(set(h.method) - {BASELINE}):
        other = h[h.method == m]
        both = base[base.index.get_level_values("indicator").isin(other.indicator.unique())].to_frame().join(
            other.set_index(keys).value, how="outer").reset_index()
        parts.append(both.assign(method=m))
    if not parts:
        return pd.DataFrame({c: pd.Series(dtype={"year": "int64", "flagged": bool}.get(
            c, str if c in ("indicator", "target_ck", "method", "baseline_method") else "float64")) for c in cols})
    s = pd.concat(parts, ignore_index=True).assign(baseline_method=BASELINE)
    s["difference"] = s.value - s.baseline_value
    s["rel_difference"] = (s.difference / s.baseline_value.where(s.baseline_value != 0)).astype(float)
    one_sided = s.value.isna() != s.baseline_value.isna()
    beyond = s.rel_difference.abs() > TOL["sensitivity_flag_rel"]
    from_zero = (s.baseline_value == 0) & (s.value.fillna(0) != 0)
    s["flagged"] = (one_sided | beyond.fillna(False) | from_zero).astype(bool)
    return s[cols].sort_values(["indicator", "method", "year", "target_ck"]).reset_index(drop=True)


def main() -> None:
    indicators = {i.code: i for i in registry()[0]}
    obs = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_observation.parquet")
    w = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "statistical_crosswalk.parquet")
    h = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_harmonized_value.parquet")
    cov = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "cropland_coverage.parquet")
    available = sorted(w.method.unique())
    wsum = w.groupby(["method", "year", "source_ck"]).weight.sum().rename("wsum").reset_index()
    rows = []
    for (ind, year), g in obs.groupby(["indicator", "year"]):
        linked = g[g.link_status == "LINKED"]
        for m in methods_for(indicators[ind], available):
            j = linked.merge(wsum[wsum.method == m], left_on=["map_year", "canonical_key"], right_on=["year", "source_ck"],
                             suffixes=("", "_w"))
            expected = float((j.value * j.wsum).sum())
            got = float(h[(h.indicator == ind) & (h.year == year) & (h.method == m)].value.sum())
            err = abs(got - expected)
            rows.append({"indicator": ind, "year": int(year), "method": m, "n_observations": len(g),
                         "n_linked": len(linked), "reported_total": float(linked.value.sum()),
                         "expected_total": expected, "harmonized_total": got, "conservation_error": err,
                         "passes": err <= TOL["conservation_rel_tol"] * max(abs(expected), 1.0)})
    check = pd.DataFrame(rows)
    core.write_table(check, core.GOLD_HARMONIZE_DIR / "harmonization_check.parquet", "harmonization_check")
    sens = sensitivity(h)
    core.write_table(sens, core.GOLD_HARMONIZE_DIR / "harmonization_method_sensitivity.parquet",
                     "harmonization_method_sensitivity")

    ctx = pd.read_parquet(core.PRODUCTS_DIR / "district_reference_context.parquet")
    self_check = h[(h.indicator == "mapped_area_km2") & (h.method == "AREA")].merge(ctx, on=["target_ck", "year"])
    self_err = float((self_check.value - self_check.mapped_km2).abs().max())
    lines = [f"# Harmonization checks — pipeline v{core.PIPELINE_VERSION}", "",
             f"Conservation: {int(check.passes.sum())} of {len(check)} indicator-year-method totals conserved "
             f"(max error {check.conservation_error.max():.3g}).", "",
             f"Self-check: harmonized mapped area vs `district_reference_context.mapped_km2` over "
             f"{len(self_check)} district-years: max difference {self_err:.3g} km² (tolerance {TOL['self_check_tol_km2']}).", "",
             f"Weight methods available: {', '.join(available)}.", ""]
    lines += report_sensitivity(sens, cov)
    lines += ["## Linking of reported values", "", pd.crosstab(obs.indicator, obs.link_status).to_markdown(), ""]
    (core.HARMONIZE_OUTPUT_DIR / "h05_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:6]))
    if not check.passes.all() or self_err > TOL["self_check_tol_km2"]:
        raise SystemExit("HARMONIZATION CHECK FAILED: see outputs/harmonize/h05_report.md")


def report_sensitivity(sens: pd.DataFrame, cov: pd.DataFrame) -> list[str]:
    if sens.empty:
        return ["## Method sensitivity", "",
                "Not measured: every indicator is restated with AREA weights only. A second method needs a cropland "
                "raster declared under `weights.cropland` in `config/indicators.yaml` "
                "(`docs/operations/cropland_weights.md`).", ""]
    names = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key").latest_name
    summary = sens.groupby(["indicator", "method"]).agg(
        district_years=("target_ck", "size"), flagged=("flagged", "sum"),
        median_abs_rel_difference=("rel_difference", lambda r: float(np.nanmedian(r.abs())) if r.notna().any() else np.nan))
    top = sens.assign(abs_diff=sens.difference.abs()).sort_values(["abs_diff", "target_ck"], ascending=[False, True]).head(15)
    top = top.assign(district=top.target_ck.map(names))[
        ["indicator", "method", "year", "target_ck", "district", "baseline_value", "value", "rel_difference"]]
    out = ["## Method sensitivity", "",
           f"Each 2025 district's value under another method against AREA; flagged beyond "
           f"{TOL['sensitivity_flag_rel']:.0%} relative difference, or when only one method restates a value there "
           "(`harmonization_method_sensitivity`).", "", summary.to_markdown(floatfmt=".3f"), "",
           "Largest absolute differences:", "", top.to_markdown(index=False, floatfmt=".4g"), ""]
    if len(cov):
        area = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet").set_index(["canonical_key", "year"]).area_km2
        district_km2 = [area[(c, y)] for c, y in zip(cov.source_ck, cov.year, strict=True)]
        no_cells = int((cov.cells == 0).sum())
        partial = int(((cov.cells > 0) & (cov.cell_km2 < MIN_RASTER_COVER * pd.Series(district_km2))).sum())
        no_crop = int(((cov.cells > 0) & (cov.cropland_km2 <= 0)).sum())
        out += ["Cropland coverage (`cropland_coverage`), per source district and map: "
                f"{no_cells} have no raster cell (outside the raster or smaller than a cell) and {no_crop} have cells but "
                f"no cropland, so CROPLAND restates nothing from them; {partial} are less than "
                f"{MIN_RASTER_COVER:.0%} covered by the raster; {cov.unallocated_cropland_km2.sum():,.1f} km² of cropland "
                f"lies outside the crosswalk's 2025 districts; {cov.nodata_km2.sum():,.1f} km² of district area is nodata.",
                ""]
    return out


if __name__ == "__main__":
    main()
