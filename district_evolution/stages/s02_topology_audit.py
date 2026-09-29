"""Stage 02 — Per-layer topology audit (V1). A gate: runs before any
cross-vintage work and exits non-zero if a layer self-overlaps materially,
because a self-overlapping layer is not a partition and every overlay built
from it would double count.

Self-overlap = sum(polygon areas) - area(union): exact for any multiplicity.
The independent area-method check (V4) runs in the warehouse (s11), where a
second implementation (DuckDB ST_Area_Spheroid) makes it a real test.
"""

from __future__ import annotations

import sys

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

from district_evolution import core


def audit_layer(source: str, year: int) -> dict:
    gdf = gpd.read_parquet(core.silver_path(year))
    sum_area = float(gdf["area_km2"].sum())
    union_area = core.geodesic_area_km2(unary_union(gdf.geometry.values))
    overlap = max(0.0, sum_area - union_area)
    frac = overlap / sum_area
    topo = core.CFG["topology"]
    status = ("ERROR" if frac >= topo["self_overlap_error_fraction"]
              else "WARNING" if frac >= topo["self_overlap_warn_fraction"] else "PASS")
    return {"source": source, "year": year, "n_districts": len(gdf),
            "sum_polygon_area_km2": round(sum_area, 2), "union_area_km2": round(union_area, 2),
            "self_overlap_km2": round(overlap, 4), "self_overlap_pct": round(100 * frac, 6),
            "status": status}


def main() -> None:
    report = pd.DataFrame([audit_layer(s, y) for s, y in core.VINTAGES])
    report.to_csv(core.OUTPUT_DIR / "s02_topology_audit.csv", index=False)
    print(report.to_string(index=False))
    if (report["status"] == "ERROR").any():
        sys.exit("V1 FAILED: a vintage layer self-overlaps beyond tolerance; not a partition.")


if __name__ == "__main__":
    main()
