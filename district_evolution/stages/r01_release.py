"""Stage r01 — Release: a versioned, byte-reproducible bundle in data/release/.

  tables/<table>.parquet            the released tables, copied byte for byte from the build
  geometry/districts_<year>.geoparquet  every map's polygons, simplified per polygon
                                    (release.simplify_deg), with canonical keys and full-resolution areas
  load.sql                          DuckDB views over the files (a DuckDB database file is not
                                    byte-reproducible; the views give the same queries)
  release_info.json                 version and the sha256 of the inputs that define it
  DATA_DICTIONARY.md, data_dictionary.json   copied from docs/ (r02)
  validation/                       the gate's checks and report (s12), so the release states its own quality
  MANIFEST.csv                      sha256 of every other file

Rebuilding from the same tag yields identical bytes (checked by the determinism CI).
"""

from __future__ import annotations

import hashlib
import json
import shutil

import geopandas as gpd
import pandas as pd
import shapely

from district_evolution import core
from district_evolution.contracts import schemas
from district_evolution.release import TABLES

OUT = core.RELEASE_DIR


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(year: int, ck_of: dict) -> tuple[gpd.GeoDataFrame, int]:
    """Simplified layer, and how many polygons kept full resolution because simplifying made them invalid."""
    g = gpd.read_parquet(core.silver_path(year),
                         columns=["geom_obs_id", "district_name_std", "state_name_std", "area_km2", "geometry"])
    g = g.rename(columns={"district_name_std": "district_name", "state_name_std": "state"})
    g.insert(1, "canonical_key", g.geom_obs_id.map(ck_of))
    g.insert(2, "year", year)
    simple = shapely.simplify(g.geometry.values, core.CFG["release"]["simplify_deg"], preserve_topology=True)
    # parts of a multipolygon can end up nested after simplification (Thrissur 2011): keep those at full resolution
    broken = ~shapely.is_valid(simple) | shapely.is_empty(simple)
    g["geometry"] = [o if b else s for o, s, b in zip(g.geometry.values, simple, broken)]
    schemas.validate("release_geometry", pd.DataFrame(g.drop(columns="geometry")))
    return g.sort_values("geom_obs_id").reset_index(drop=True), int(broken.sum())


def load_sql() -> str:
    views = [f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM 'tables/{t}.parquet';" for t in TABLES]
    return "\n".join([
        f"-- District Evolution release v{core.PIPELINE_VERSION}. From this folder: duckdb, then .read load.sql",
        "INSTALL spatial;", "LOAD spatial;", *views,
        "CREATE OR REPLACE VIEW district_geometry AS SELECT * FROM read_parquet('geometry/districts_*.geoparquet');",
        ""])


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "geometry").mkdir(parents=True, exist_ok=True)
    for table, src in TABLES.items():
        shutil.copyfile(src, OUT / "tables" / f"{table}.parquet")
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    ck_of = dict(zip(obs.geom_obs_id, obs.canonical_key))
    kept_full = {}
    for _, year in core.VINTAGES:
        layer, kept_full[year] = geometry(year, ck_of)
        layer.to_parquet(OUT / "geometry" / f"districts_{year}.geoparquet", index=False)
    (OUT / "load.sql").write_text(load_sql(), encoding="utf-8")
    shutil.copyfile(core.PROJECT_ROOT / "docs" / "data_dictionary.md", OUT / "DATA_DICTIONARY.md")
    shutil.copyfile(core.PROJECT_ROOT / "docs" / "data_dictionary.json", OUT / "data_dictionary.json")
    (OUT / "validation").mkdir(exist_ok=True)
    for name in ("s12_checks.csv", "s12_validation_report.md"):
        shutil.copyfile(core.OUTPUT_DIR / name, OUT / "validation" / name)
    info = {"pipeline_version": core.PIPELINE_VERSION,
            "config_sha256": sha256(core.CONFIG_DIR / "pipeline.yaml"),
            "events_csv_sha256": sha256(core.EVENTS_CSV),
            "reference_year": core.REFERENCE_YEAR,
            "vintages": [{"source": s, "year": y} for s, y in core.VINTAGES],
            "geometry_simplify_deg": core.CFG["release"]["simplify_deg"],
            "polygons_kept_at_full_resolution": {str(y): n for y, n in kept_full.items() if n},
            "citation": "CITATION.cff in the source repository"}
    (OUT / "release_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "MANIFEST.csv" and p.name != ".DS_Store")
    pd.DataFrame({"path": [str(p.relative_to(OUT)) for p in files], "bytes": [p.stat().st_size for p in files],
                  "sha256": [sha256(p) for p in files]}).to_csv(OUT / "MANIFEST.csv", index=False)
    print(f"release v{core.PIPELINE_VERSION}: {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
