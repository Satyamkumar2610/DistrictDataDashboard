"""Stage 03 — Transition matrix: the one primitive every product derives from.

For each consecutive vintage pair (ADJACENT) and for every vintage against the
reference vintage (REFERENCE, used by the census crosswalk), compute the planar
overlay. Overlay parts partition the shared footprint, so conservation holds by
construction: for every source polygon,

    sum(parts, all classes) + unmapped == area(source)      (within closure tol)

Every connected part is classified exactly once (config: overlay.*):

  SLIVER                 area < max(abs, rel * smaller polygon)     noise
  CORE                   area >= core_share * smaller polygon        the bulk of one of the two polygons
  BOUNDARY_DISPLACEMENT  non-core and mean width 2A/P < width_km     two editions disagreeing on a line
  TRANSFER               non-core and wide                           territory that changed hands

CORE + TRANSFER is "material" area: the only area lineage and transfers count.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

OV = lib.CFG["overlay"]
CLASSES = ["core", "transfer", "displacement", "sliver"]


def load(year: int) -> gpd.GeoDataFrame:
    return gpd.read_parquet(lib.silver_path(year), columns=["geom_obs_id", "area_km2", "geometry"])


def overlay_parts(year_a: int, year_b: int) -> gpd.GeoDataFrame:
    return classify_parts(load(year_a), load(year_b))


def classify_parts(layer_a: gpd.GeoDataFrame, layer_b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Overlay two layers (geom_obs_id, area_km2, geometry) and classify every connected part."""
    a = layer_a.rename(columns={"geom_obs_id": "obs_a", "area_km2": "area_a"})
    b = layer_b.rename(columns={"geom_obs_id": "obs_b", "area_km2": "area_b"})
    ov = gpd.overlay(a, b, how="intersection", keep_geom_type=True)
    parts = ov.explode(index_parts=False).reset_index(drop=True)
    ap = parts.geometry.apply(lib.geodesic_area_perimeter)
    parts["part_km2"] = [x[0] for x in ap]
    parts["perimeter_km"] = [x[1] for x in ap]
    parts = parts[parts["part_km2"] > 0].copy()
    smaller = np.minimum(parts["area_a"], parts["area_b"])
    width = 2.0 * parts["part_km2"] / parts["perimeter_km"]
    sliver = parts["part_km2"] < np.maximum(OV["sliver_abs_km2"], smaller * OV["sliver_rel_fraction"])
    core = parts["part_km2"] >= OV["core_share"] * smaller
    parts["width_km"] = width
    parts["part_class"] = np.select(
        [sliver, core, width < OV["displacement_width_km"]],
        ["sliver", "core", "displacement"], default="transfer")
    return parts


def flows_and_residuals(parts, year_a, year_b, kind):
    a = load(year_a).drop(columns="geometry")
    b = load(year_b).drop(columns="geometry")
    flow = (parts.pivot_table(index=["obs_a", "obs_b"], columns="part_class",
                              values="part_km2", aggfunc="sum", fill_value=0.0)
            .reindex(columns=CLASSES, fill_value=0.0).add_suffix("_km2").reset_index())
    flow["total_km2"] = flow[[f"{c}_km2" for c in CLASSES]].sum(axis=1)
    flow["material_km2"] = flow["core_km2"] + flow["transfer_km2"]
    flow = flow.rename(columns={"obs_a": "geom_obs_id_a", "obs_b": "geom_obs_id_b"})
    flow.insert(0, "kind", kind)
    flow.insert(1, "year_a", year_a)
    flow.insert(2, "year_b", year_b)
    flow = flow.sort_values(["geom_obs_id_a", "geom_obs_id_b"]).reset_index(drop=True)

    res = []
    for side, layer, key, yr in (("SOURCE", a, "obs_a", year_a), ("TARGET", b, "obs_b", year_b)):
        covered = parts.groupby(key)["part_km2"].sum()
        r = layer[["geom_obs_id", "area_km2"]].copy()
        r["covered_km2"] = r["geom_obs_id"].map(covered).fillna(0.0)
        r["unmapped_km2"] = (r["area_km2"] - r["covered_km2"]).clip(lower=0.0)
        r["closure_error_km2"] = (r["covered_km2"] - r["area_km2"]).clip(lower=0.0)
        r["closure_ok"] = lib.within_closure(r["closure_error_km2"], r["area_km2"])
        r.insert(0, "kind", kind)
        r.insert(1, "side", side)
        r.insert(2, "year_a", year_a)
        r.insert(3, "year_b", year_b)
        res.append(r)
    return flow, pd.concat(res, ignore_index=True)


def summarize(flow, res, kind, year_a, year_b) -> dict:
    src = res[res.side == "SOURCE"]
    tgt = res[res.side == "TARGET"]
    return {
        "kind": kind, "year_a": year_a, "year_b": year_b,
        "source_area_km2": round(src.area_km2.sum(), 1),
        **{f"{c}_km2": round(flow[f"{c}_km2"].sum(), 1) for c in CLASSES},
        "unmapped_source_km2": round(src.unmapped_km2.sum(), 1),
        "unmapped_target_km2": round(tgt.unmapped_km2.sum(), 1),
        "max_closure_error_km2": round(res.closure_error_km2.max(), 4),
        "closure_violations": int((~res.closure_ok).sum()),
    }


def main() -> None:
    pairs = [("ADJACENT", a, b) for a, b in lib.WINDOWS]
    pairs += [("REFERENCE", y, lib.REFERENCE_YEAR) for y in lib.YEARS if y != lib.REFERENCE_YEAR]
    flows, residuals, summary, inspect = [], [], [], []
    cache: dict[tuple[int, int], gpd.GeoDataFrame] = {}
    for kind, ya, yb in pairs:
        if (ya, yb) not in cache:
            cache[(ya, yb)] = overlay_parts(ya, yb)
        parts = cache[(ya, yb)]
        flow, res = flows_and_residuals(parts, ya, yb, kind)
        flows.append(flow)
        residuals.append(res)
        s = summarize(flow, res, kind, ya, yb)
        summary.append(s)
        print(s)
        if kind == "ADJACENT":
            keep = parts[parts.part_class.isin(["transfer", "displacement"])]
            inspect.append(keep.assign(year_a=ya, year_b=yb)[
                ["year_a", "year_b", "obs_a", "obs_b", "part_km2", "width_km", "part_class", "geometry"]])

    lib.write_table(pd.concat(flows, ignore_index=True), lib.GOLD_SPATIAL_DIR / "transition_flow.parquet",
                    "transition_flow")
    lib.write_table(pd.concat(residuals, ignore_index=True), lib.GOLD_SPATIAL_DIR / "transition_residual.parquet",
                    "transition_residual")
    summary = pd.DataFrame(summary)
    summary.to_csv(lib.OUTPUT_DIR / "s03_transition_summary.csv", index=False)
    gpd.GeoDataFrame(pd.concat(inspect, ignore_index=True), geometry="geometry", crs="EPSG:4326").to_file(
        lib.OUTPUT_DIR / "s03_transfer_and_displacement_parts.gpkg", driver="GPKG")

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
