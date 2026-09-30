"""Stage 01 — Bronze to Silver.

Reads each vintage through its boundary source adapter (district_evolution/sources,
configured in config/sources.yaml; checked against the boundary_layer contract,
EPSG:4326), repairs invalid geometry, computes geodesic area and
perimeter with the one method used everywhere, and writes one GeoParquet per
vintage. Bronze is only read.

Unnamed / sentinel-named features (e.g. the ~80,520 km2 "DATA NOT AVAILABLE"
polygon in J&K) are non-administrative placeholders: a district identity
requires a name. So are strips named as disputed between districts of
different states (SOI 2025: "Disputed (Sahibganj, Maldah & Katihar)" and eight
more; config `placeholders`). Both are excluded and logged, never silently
dropped; their land stays unassigned on that map.

Each layer is then made a true partition. Where two polygons overlap (source
digitization; e.g. the 2011 layer never cut the Tamil Nadu districts around
the Puducherry enclaves), the overlap is assigned to the smaller polygon (the
enclave) and removed from the larger one. Every repair is logged with its area
change in outputs/pipeline/s01_overlap_repairs.csv.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import STRtree, make_valid
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union

from district_evolution import core, sources

SENTINEL_RE = core.CFG["placeholders"]["sentinel_name_pattern"]


def to_multipolygon(geom):
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, GeometryCollection):
        polys = []
        for g in geom.geoms:
            if isinstance(g, Polygon):
                polys.append(g)
            elif isinstance(g, MultiPolygon):
                polys.extend(g.geoms)
        return MultiPolygon(polys) if polys else None
    return None


def resolve_overlaps(geoms: list, areas: list[float], ids: list[str]) -> tuple[list, list[dict]]:
    """Remove from each polygon the parts it shares with smaller polygons."""
    tree = STRtree(geoms)
    left, right = tree.query(geoms, predicate="intersects")
    rank = {i: (areas[i], ids[i]) for i in range(len(geoms))}
    smaller_of: dict[int, list[int]] = {}
    for i, j in zip(left, right, strict=True):
        if i != j and rank[j] < rank[i]:
            smaller_of.setdefault(int(i), []).append(int(j))
    out, log = list(geoms), []
    for i, js in sorted(smaller_of.items()):
        overlap = unary_union([geoms[j] for j in js]).intersection(geoms[i])
        if overlap.is_empty or core.geodesic_area_km2(overlap) == 0:
            continue
        repaired = to_multipolygon(make_valid(geoms[i].difference(unary_union([geoms[j] for j in js]))))
        if repaired is None or repaired.is_empty:
            continue
        out[i] = repaired
        log.append({"geom_obs_id": ids[i], "area_before_km2": areas[i],
                    "area_removed_km2": areas[i] - core.geodesic_area_km2(repaired),
                    "n_smaller_overlapping": len(js)})
    return out, log


def process_vintage(source: str, year: int) -> tuple[dict, list[dict], list[dict]]:
    gdf = sources.load(source, year)
    n_raw = len(gdf)

    names = gdf["district_name_original"].fillna("").astype(str).str.lower()
    unnamed = names.str.match(SENTINEL_RE)
    disputed = ~unnamed & names.str.contains(core.CFG["placeholders"]["disputed_name_pattern"], regex=True)
    excluded = [{
        "source_dataset": source, "source_year": year, "source_pk": r.source_pk,
        "district_name_original": r.district_name_original, "state_name_original": r.state_name_original,
        "area_km2": round(core.geodesic_area_km2(r.geometry), 2),
        "reason": "UNNAMED_NON_ADMINISTRATIVE_FEATURE" if u else "DISPUTED_BOUNDARY_STRIP",
    } for r, u in zip(gdf[unnamed | disputed].itertuples(), unnamed[unnamed | disputed], strict=True)]
    gdf = gdf[~(unnamed | disputed)]

    kept, n_repaired, n_empty = [], 0, 0
    for r in gdf.sort_values("source_pk", kind="stable").itertuples():
        geom = r.geometry
        invalid = geom is not None and not geom.is_empty and not geom.is_valid
        if invalid:
            geom = make_valid(geom)
            n_repaired += 1
        mp = to_multipolygon(geom)
        if mp is None or mp.is_empty:
            n_empty += 1
            continue
        kept.append((r, core.stable_id(source, year, r.source_pk), mp, invalid))

    ids = [k[1] for k in kept]
    geoms, overlap_log = resolve_overlaps([k[2] for k in kept], [core.geodesic_area_km2(k[2]) for k in kept], ids)
    trimmed = {x["geom_obs_id"] for x in overlap_log}

    records = []
    for (r, gid, _, invalid), mp in zip(kept, geoms, strict=True):
        area, perim = core.geodesic_area_perimeter(mp)
        state_std = core.canonical_state(r.state_name_original)
        records.append({
            "geom_obs_id": gid,
            "source_dataset": source, "source_year": year, "source_pk": r.source_pk,
            "district_name_original": r.district_name_original,
            "district_name_std": core.display_name(r.district_name_original),
            "district_name_norm": core.normalize_name(r.district_name_original),
            "state_name_original": r.state_name_original,
            "state_name_std": state_std,
            "state_name_norm": core.normalize_name(state_std),
            "area_km2": area, "perimeter_km": perim,
            "was_repaired": invalid, "overlap_trimmed": gid in trimmed, "n_parts": len(mp.geoms),
            "geometry": mp,
        })

    out = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    out = out.sort_values("source_pk", kind="stable").reset_index(drop=True)
    core.write_table(out, core.silver_path(year), "silver_geometry")
    summary = {"source": source, "year": year, "raw": n_raw, "usable": len(out),
               "excluded_unnamed": len(excluded), "empty_dropped": n_empty,
               "invalid_repaired": n_repaired, "overlap_trimmed": len(overlap_log),
               "overlap_removed_km2": round(sum(x["area_removed_km2"] for x in overlap_log), 3),
               "multipart": int((out["n_parts"] > 1).sum())}
    print(f"[{source} {year}] {summary}")
    for x in overlap_log:
        x.update(source_dataset=source, source_year=year)
    return summary, excluded, overlap_log


def main() -> None:
    summaries, excluded, repairs = [], [], []
    for source, year in core.VINTAGES:
        s, e, o = process_vintage(source, year)
        summaries.append(s)
        excluded.extend(e)
        repairs.extend(o)
    pd.DataFrame(summaries).to_csv(core.OUTPUT_DIR / "s01_silver_summary.csv", index=False)
    pd.DataFrame(repairs).to_csv(core.OUTPUT_DIR / "s01_overlap_repairs.csv", index=False)
    pd.DataFrame(excluded, columns=["source_dataset", "source_year", "source_pk", "district_name_original",
                                    "state_name_original", "area_km2", "reason"]
                 ).to_csv(core.OUTPUT_DIR / "s01_excluded_non_administrative.csv", index=False)
    print(f"excluded non-administrative features: {len(excluded)}")


if __name__ == "__main__":
    main()
