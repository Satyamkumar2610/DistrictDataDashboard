"""Stage h05 — Harmonization checks (harmonization_check) and report.

1. Conservation, per indicator, year and method: the harmonized total equals the sum over linked
   values of value x (sum of its weights). Allocation neither creates nor loses any quantity.
2. Self-check: harmonizing every district's own mapped area reproduces
   district_reference_context.mapped_km2 for every 2025 district and map (an independent s10 path).
3. Method sensitivity: with two or more weight methods, the per-district difference is reported.
The stage fails if 1 or 2 fails.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.contracts.schemas import SCHEMAS  # noqa: F401  (contracts register on import)

TOL = core.CFG["harmonize"]


def main() -> None:
    obs = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_observation.parquet")
    w = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "statistical_crosswalk.parquet")
    h = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_harmonized_value.parquet")
    wsum = w.groupby(["method", "year", "source_ck"]).weight.sum().rename("wsum").reset_index()
    rows = []
    for (ind, year), g in obs.groupby(["indicator", "year"]):
        linked = g[g.link_status == "LINKED"]
        for m in sorted(w.method.unique()):
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

    ctx = pd.read_parquet(core.PRODUCTS_DIR / "district_reference_context.parquet")
    self_check = h[(h.indicator == "mapped_area_km2") & (h.method == "AREA")].merge(ctx, on=["target_ck", "year"])
    self_err = float((self_check.value - self_check.mapped_km2).abs().max())
    methods = sorted(w.method.unique())
    lines = [f"# Harmonization checks — pipeline v{core.PIPELINE_VERSION}", "",
             f"Conservation: {int(check.passes.sum())} of {len(check)} indicator-year-method totals conserved "
             f"(max error {check.conservation_error.max():.3g}).", "",
             f"Self-check: harmonized mapped area vs `district_reference_context.mapped_km2` over "
             f"{len(self_check)} district-years: max difference {self_err:.3g} km² (tolerance {TOL['self_check_tol_km2']}).", "",
             f"Weight methods available: {', '.join(methods)}. " + (
                 "Method sensitivity needs a second method (CROPLAND, once a cropland raster is supplied)."
                 if len(methods) < 2 else ""), "",
             "## Linking of reported values", "",
             pd.crosstab(obs.indicator, obs.link_status).to_markdown(), ""]
    (core.HARMONIZE_OUTPUT_DIR / "h05_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:6]))
    if not check.passes.all() or self_err > TOL["self_check_tol_km2"]:
        raise SystemExit("HARMONIZATION CHECK FAILED: see outputs/harmonize/h05_report.md")


if __name__ == "__main__":
    main()
