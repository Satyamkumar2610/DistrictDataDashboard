"""Stage 01 — Bronze to Silver.

Reads each source GPKG (config/sources.yaml), standardizes to one schema,
reprojects to EPSG:4326, repairs invalid geometry, computes geodesic area and
perimeter with the one method used everywhere, and writes one GeoParquet per
vintage. Bronze is only read.

Unnamed / sentinel-named features (e.g. the ~80,520 km2 "DATA NOT AVAILABLE"
polygon in J&K) are non-administrative placeholders: a district identity
requires a name. Named features that are still not districts (SOI 2025's
interstate "DISPUTED (A & B)" patches) are listed, with evidence, in
data/reference/non_administrative_features.csv. Both kinds are excluded and
logged, never silently dropped; their area appears downstream as unmapped
(coverage) area, so nothing is lost from the accounting.

Each layer is then made a true partition. Where two polygons overlap (source
digitization; e.g. the 2011 layer never cut the Tamil Nadu districts around
the Puducherry enclaves), the overlap is assigned to the smaller polygon (the
enclave) and removed from the larger one. That rule is only meaningful for
enclaves, so every repair also logs how much of the smaller polygon lies inside
the larger one (`smaller_contained_share`); a repair between two neighbours
that merely overlap (share below topology.enclave_min_contained_share) is a
WARNING in s11 (V22), not silently accepted. Every repair is logged with its
area change in outputs/pipeline/s01_overlap_repairs.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
from shapely import STRtree, make_valid
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

SENTINEL_RE = r"^(nan|none|data not available|not available|n/?a|unknown|no data|unnamed|-+)?$"


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
    for i, j in zip(left, right):
        if i != j and rank[j] < rank[i]:
            smaller_of.setdefault(int(i), []).append(int(j))
    out, log = list(geoms), []
    for i, js in sorted(smaller_of.items()):
        overlap = unary_union([geoms[j] for j in js]).intersection(geoms[i])
        if overlap.is_empty or lib.geodesic_area_km2(overlap) == 0:
            continue
        repaired = to_multipolygon(make_valid(geoms[i].difference(unary_union([geoms[j] for j in js]))))
        if repaired is None or repaired.is_empty:
            continue
        out[i] = repaired
        contained = max(lib.geodesic_area_km2(geoms[j].intersection(geoms[i])) / areas[j] if areas[j] else 0.0
                        for j in js)
        log.append({"geom_obs_id": ids[i], "area_before_km2": areas[i],
                    "area_removed_km2": areas[i] - lib.geodesic_area_km2(repaired),
                    "n_smaller_overlapping": len(js), "smaller_contained_share": contained})
    return out, log


def read_source(source: str, cfg: dict) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(lib.PROJECT_ROOT / cfg["path"], layer=cfg["primary_layer"])
    if cfg.get("state_field"):
        state = gdf[cfg["state_field"]]
    else:
        codes = gdf[cfg["state_code_field"]].astype(str).str.zfill(2)
        unmapped = sorted(set(codes) - set(lib.PC11_STATE_CODES))
        if unmapped:
            raise ValueError(f"unmapped PC11 state codes: {unmapped}")
        state = codes.map(lib.PC11_STATE_CODES)
    out = gpd.GeoDataFrame({
        "source_pk": gdf[cfg["source_pk"]].astype(str),
        "district_name_original": gdf[cfg["name_field"]].astype(str).str.strip(),
        "state_name_original": state.astype(str).str.strip(),
        "geometry": gdf.geometry,
    }, geometry="geometry", crs=gdf.crs)
    if out.crs is None:
        raise ValueError(f"{source} {cfg['path']}: layer has no CRS; refusing to assume EPSG:4326")
    return out if out.crs.to_epsg() == 4326 else out.to_crs(epsg=4326)


def curated_non_administrative() -> dict[tuple[str, int, str], str]:
    """(source, year, source_pk) -> reason, for CONFIRMED rows only."""
    ref = pd.read_csv(lib.REFERENCE_DIR / "non_administrative_features.csv", dtype={"source_pk": str})
    ref = ref[ref.status == "CONFIRMED"]
    return {(s, int(y), pk): r for s, y, pk, r in zip(ref.source_dataset, ref.source_year, ref.source_pk, ref.reason)}


def process_vintage(source: str, year: int, cfg: dict) -> tuple[dict, list[dict]]:
    gdf = read_source(source, cfg)
    n_raw = len(gdf)

    curated = curated_non_administrative()
    reason = pd.Series([curated.get((source, year, pk)) for pk in gdf["source_pk"]], index=gdf.index, dtype=object)
    reason[gdf["district_name_original"].str.lower().str.match(SENTINEL_RE)] = "UNNAMED_NON_ADMINISTRATIVE_FEATURE"
    drop = reason.notna()
    excluded = [{
        "source_dataset": source, "source_year": year, "source_pk": r.source_pk,
        "district_name_original": r.district_name_original,
        "state_name_original": r.state_name_original,
        "area_km2": round(lib.geodesic_area_km2(r.geometry), 2),
        "reason": reason[r.Index],
    } for r in gdf[drop].itertuples()]
    gdf = gdf[~drop]

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
        kept.append((r, lib.stable_id(source, year, r.source_pk), mp, invalid))

    ids = [k[1] for k in kept]
    geoms, overlap_log = resolve_overlaps([k[2] for k in kept], [lib.geodesic_area_km2(k[2]) for k in kept], ids)
    trimmed = {x["geom_obs_id"] for x in overlap_log}

    records = []
    for (r, gid, _, invalid), mp in zip(kept, geoms):
        area, perim = lib.geodesic_area_perimeter(mp)
        state_std = lib.canonical_state(r.state_name_original)
        records.append({
            "geom_obs_id": gid,
            "source_dataset": source, "source_year": year, "source_pk": r.source_pk,
            "district_name_original": r.district_name_original,
            "district_name_std": lib.display_name(r.district_name_original),
            "district_name_norm": lib.normalize_name(r.district_name_original),
            "state_name_original": r.state_name_original,
            "state_name_std": state_std,
            "state_name_norm": lib.normalize_name(state_std),
            "area_km2": area, "perimeter_km": perim,
            "was_repaired": invalid, "overlap_trimmed": gid in trimmed, "n_parts": len(mp.geoms),
            "geometry": mp,
        })

    out = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    out = out.sort_values("source_pk", kind="stable").reset_index(drop=True)
    lib.write_table(out, lib.silver_path(year), "silver_geometry")
    summary = {"source": source, "year": year, "raw": n_raw, "usable": len(out),
               "excluded_non_administrative": len(excluded), "empty_dropped": n_empty,
               "invalid_repaired": n_repaired, "overlap_trimmed": len(overlap_log),
               "overlap_removed_km2": round(sum(x["area_removed_km2"] for x in overlap_log), 3),
               "multipart": int((out["n_parts"] > 1).sum())}
    print(f"[{source} {year}] {summary}")
    for x in overlap_log:
        x.update(source_dataset=source, source_year=year)
    return summary, excluded, overlap_log


def main() -> None:
    with open(lib.CONFIG_DIR / "sources.yaml") as fh:
        sources = yaml.safe_load(fh)["sources"]
    summaries, excluded, repairs = [], [], []
    for source, year in lib.VINTAGES:
        s, e, o = process_vintage(source, year, sources[source]["datasets"][str(year)])
        summaries.append(s)
        excluded.extend(e)
        repairs.extend(o)
    pd.DataFrame(summaries).to_csv(lib.OUTPUT_DIR / "s01_silver_summary.csv", index=False)
    pd.DataFrame(repairs, columns=["geom_obs_id", "area_before_km2", "area_removed_km2", "n_smaller_overlapping",
                                   "smaller_contained_share", "source_dataset", "source_year"]
                 ).to_csv(lib.OUTPUT_DIR / "s01_overlap_repairs.csv", index=False)
    pd.DataFrame(excluded, columns=["source_dataset", "source_year", "source_pk", "district_name_original",
                                    "state_name_original", "area_km2", "reason"]
                 ).to_csv(lib.OUTPUT_DIR / "s01_excluded_non_administrative.csv", index=False)
    print(f"excluded non-administrative features: {len(excluded)}")


if __name__ == "__main__":
    main()
