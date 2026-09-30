"""Read-only API and web platform over a release (data/release; set DISTRICT_RELEASE_DIR to serve another).

    uvicorn district_evolution.release.api:app

JSON under /api is {"meta": {pipeline_version, config_sha256, ...}, "data": ...}; vector tiles are
under /api/tiles; the web app (web/dist, built with npm) is served at every other path. The API only
reads the release; the batch pipeline is the only writer. OpenAPI: /docs and /openapi.json.
"""

from __future__ import annotations

import functools
import json
import os
import threading
from pathlib import Path

import duckdb
import pandas as pd
from fastapi import APIRouter, FastAPI, HTTPException, Query, Response
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from district_evolution import core
from district_evolution.release import TABLES

RELEASE = Path(os.environ.get("DISTRICT_RELEASE_DIR", core.RELEASE_DIR))
WEB = Path(os.environ.get("DISTRICT_WEB_DIR", core.PROJECT_ROOT / "web" / "dist"))
INFO = json.loads((RELEASE / "release_info.json").read_text())
META = {k: INFO[k] for k in ("pipeline_version", "config_sha256", "events_csv_sha256", "reference_year")}
YEARS = [v["year"] for v in INFO["vintages"]]
CK = r"^IND-\d{6}$"
MATERIAL_KM2 = core.CFG["lineage"]["material_km2"]

_db = duckdb.connect()
_db.execute("INSTALL spatial; LOAD spatial;")
for _t in TABLES:
    _db.execute(f"CREATE VIEW {_t} AS SELECT * FROM read_parquet('{(RELEASE / 'tables' / f'{_t}.parquet').as_posix()}')")
_db.execute(f"""CREATE TABLE district_geometry AS
    SELECT g.*, ST_Transform(g.geometry, 'EPSG:4326', 'EPSG:3857', always_xy := true) AS geom3857
    FROM read_parquet('{(RELEASE / 'geometry').as_posix()}/districts_*.geoparquet') g""")
_db.execute("""CREATE TABLE tile_source AS
    SELECT g.year, g.canonical_key, g.district_name, g.state, g.area_km2, g.geom3857, ST_Extent(g.geom3857) AS box,
           r.established_year = g.year AND r.origin_kind = 'NEW' AS is_new,
           round(100 * (g.area_km2 - p.area_km2) / p.area_km2, 2) AS area_change_pct
    FROM district_geometry g JOIN ck_registry r USING (canonical_key)
    LEFT JOIN district_area_admin p ON p.canonical_key = g.canonical_key
         AND p.year = (SELECT max(v.year) FROM district_area_admin v WHERE v.year < g.year)""")
# Event-level status, the rule s09 uses: MEASURED only if every accounting row is; no row at all is NOT_MEASURABLE.
_db.execute("""CREATE VIEW event_status AS
    SELECT e.event_id, CASE WHEN count(a.event_id) = 0 THEN 'NOT_MEASURABLE'
                            WHEN bool_and(a.measurement_status = 'MEASURED') THEN 'MEASURED'
                            ELSE 'UNIDENTIFIED_MULTI_EVENT_WINDOW' END AS measurement_status
    FROM boundary_event e LEFT JOIN event_accounting a USING (event_id) GROUP BY 1""")
_lock = threading.Lock()


def rows(sql: str, params: list | None = None) -> list[dict]:
    with _lock:
        res = _db.cursor().execute(sql, params or [])
        cols = [d[0] for d in res.description]
        return [dict(zip(cols, r)) for r in res.fetchall()]


def ok(data) -> dict:
    return {"meta": META, "data": data}


def registry_row(ck: str) -> dict:
    found = rows("SELECT * FROM ck_registry WHERE canonical_key = ?", [ck])
    if not found:
        raise HTTPException(404, f"no district identity {ck}")
    return found[0]


def release_file(name: str) -> Path:
    path = RELEASE / name
    if not path.exists():
        raise HTTPException(404, f"{name} is not in this release")
    return path


api = APIRouter(prefix="/api")


@api.get("/meta")
def meta():
    counts = {t: rows(f"SELECT count(*) AS n FROM {t}")[0]["n"] for t in TABLES}
    return ok({**INFO, "row_counts": counts})


@api.get("/overview")
def overview():
    """Figures for the landing dashboard, all read from release tables."""
    return ok({
        "maps": rows("""SELECT o.year, count(*) AS districts, round(sum(o.area_km2)) AS mapped_km2,
                               sum((r.established_year = o.year AND r.origin_kind = 'NEW')::INT) AS new_identities
                        FROM ck_observation o JOIN ck_registry r USING (canonical_key) GROUP BY 1 ORDER BY 1"""),
        "lineage": rows("""SELECT year_b AS year, relationship_type, count(*) AS edges, round(sum(transfer_km2)) AS km2
                           FROM district_relationship GROUP BY 1, 2 ORDER BY 1, 2"""),
        "transfers": rows("""SELECT year_b AS year, count(*) AS transfers, round(sum(transfer_km2)) AS km2
                             FROM measured_area_transfer GROUP BY 1 ORDER BY 1"""),
        "events": rows("""SELECT (e.effective_year // 10) * 10 AS decade, s.measurement_status AS status, count(*) AS events
                          FROM boundary_event e JOIN event_status s USING (event_id) GROUP BY 1, 2 ORDER BY 1, 2"""),
        "identities": rows("""SELECT count(*) AS total, sum(is_active::INT) AS active, sum((NOT is_active)::INT) AS closed
                              FROM ck_registry""")[0],
        "evidence": rows("SELECT claim_type, verdict, count(*) AS n FROM claim_verdict GROUP BY 1, 2 ORDER BY 1, 2"),
        "research_open": rows("SELECT topic, count(*) AS n FROM research_queue WHERE status = 'OPEN' GROUP BY 1 ORDER BY 1"),
    })


@api.get("/tiles/{year}/{z}/{x}/{y}.pbf", responses={200: {"content": {"application/vnd.mapbox-vector-tile": {}}}})
def tile(year: int, z: int = PathParam(ge=0, le=14), x: int = PathParam(ge=0), y: int = PathParam(ge=0)):
    if year not in YEARS:
        raise HTTPException(404, f"no map for {year}")
    return Response(content=_tile(year, z, x, y), media_type="application/vnd.mapbox-vector-tile",
                    headers={"Cache-Control": "public, max-age=86400"})


@functools.lru_cache(maxsize=4096)
def _tile(year: int, z: int, x: int, y: int) -> bytes:
    tolerance = 40075016.0 / (4096 * 2 ** z) * 0.5  # half a tile unit, in metres
    with _lock:
        b = _db.cursor().execute(f"""
            WITH env AS (SELECT ST_TileEnvelope({z}, {x}, {y}) AS e)
            SELECT ST_AsMVT({{'geom': ST_AsMVTGeom(ST_Simplify(geom3857, {tolerance}), ST_Extent((SELECT e FROM env)), 4096, 64, true),
                              'ck': canonical_key, 'name': district_name, 'state': state,
                              'area_km2': round(area_km2, 1), 'is_new': is_new, 'area_change_pct': area_change_pct}},
                             'districts')
            FROM tile_source, env WHERE year = ? AND ST_Intersects(box::GEOMETRY, e)""", [year]).fetchone()[0]
    return b or b""


@api.get("/districts")
def districts(q: str | None = Query(None, description="Part of a district name (any map)"),
              state: str | None = None, year: int | None = Query(None, description="Only identities on this map"),
              active: bool | None = None, limit: int = Query(50, le=1000)):
    where, params = ["1=1"], []
    if q:
        where.append("canonical_key IN (SELECT canonical_key FROM ck_observation WHERE district_name ILIKE ?)")
        params.append(f"%{q}%")
    if state:
        where.append("latest_state ILIKE ?")
        params.append(state)
    if year:
        where.append("canonical_key IN (SELECT canonical_key FROM ck_observation WHERE year = ?)")
        params.append(year)
    if active is not None:
        where.append("is_active = ?")
        params.append(active)
    sql = (f"SELECT canonical_key, latest_name, latest_state, established_year, closed_year, is_active "
           f"FROM ck_registry WHERE {' AND '.join(where)} ORDER BY latest_state, latest_name, canonical_key LIMIT ?")
    return ok(rows(sql, [*params, limit]))


@api.get("/districts/{ck}")
def district(ck: str = PathParam(pattern=CK)):
    return ok({**registry_row(ck),
               "observations": rows("SELECT year, district_name, state, area_km2, geom_obs_id FROM ck_observation "
                                    "WHERE canonical_key = ? ORDER BY year", [ck])})


@api.get("/districts/{ck}/timeline")
def timeline(ck: str = PathParam(pattern=CK)):
    registry_row(ck)
    return ok({"maps": rows("SELECT year, depicted_year, district_name, state, area_km2 FROM district_area_admin "
                            "WHERE canonical_key = ? ORDER BY year", [ck]),
               "ledger": rows("SELECT * FROM area_ledger WHERE canonical_key = ? ORDER BY year_a", [ck]),
               "transfers": rows("""SELECT t.*, f.latest_name AS from_name, o.latest_name AS to_name
                                    FROM measured_area_transfer t JOIN ck_registry f ON f.canonical_key = t.from_ck
                                    JOIN ck_registry o ON o.canonical_key = t.to_ck
                                    WHERE ? IN (t.from_ck, t.to_ck) ORDER BY t.year_b, t.transfer_km2 DESC""", [ck])})


@api.get("/districts/{ck}/lineage")
def lineage(ck: str = PathParam(pattern=CK), direction: str = Query("both", pattern="^(ancestors|descendants|both)$"),
            max_depth: int = Query(10, le=32)):
    registry_row(ck)
    walk = {"ancestors": ("to_ck", "from_ck"), "descendants": ("from_ck", "to_ck")}
    out = {}
    for d in (["ancestors", "descendants"] if direction == "both" else [direction]):
        near, far = walk[d]
        out[d] = rows(f"""WITH RECURSIVE w(ck, depth, rel_id) AS (
                SELECT {far}, 1, rel_id FROM district_relationship WHERE {near} = ?
                UNION ALL
                SELECT r.{far}, w.depth + 1, r.rel_id FROM w JOIN district_relationship r ON r.{near} = w.ck
                WHERE w.depth < ?)
            SELECT min(w.depth) AS depth, r.*, f.latest_name AS from_name, t.latest_name AS to_name
            FROM w JOIN district_relationship r USING (rel_id)
            JOIN ck_registry f ON f.canonical_key = r.from_ck JOIN ck_registry t ON t.canonical_key = r.to_ck
            GROUP BY ALL ORDER BY depth, r.year_b, r.rel_id""", [ck, max_depth])
    return ok(out)


@api.get("/districts/{ck}/geometry")
def geometry(year: int, ck: str = PathParam(pattern=CK)):
    found = rows("SELECT canonical_key, year, district_name, state, area_km2, ST_AsGeoJSON(geometry) AS g "
                 "FROM district_geometry WHERE canonical_key = ? AND year = ?", [ck, year])
    if not found:
        raise HTTPException(404, f"{ck} is not on the {year} map")
    f = found[0]
    return ok({"type": "Feature", "geometry": json.loads(f.pop("g")), "properties": f})


@api.get("/districts/{ck}/changes")
def changes(year_b: int, ck: str = PathParam(pattern=CK)):
    """Where the district's land went (out) and came from (in) between the map before year_b and year_b.

    Parcels are drawn from the release's simplified polygons; only moves the pipeline measured as
    real (a lineage edge or a transfer between continuing districts) are drawn, never line jitter.
    km2 comes from those tables, not from the drawn shapes.
    """
    registry_row(ck)
    if year_b not in YEARS or year_b == YEARS[0]:
        raise HTTPException(400, f"year_b must be a map after {YEARS[0]}: {YEARS[1:]}")
    year_a = YEARS[YEARS.index(year_b) - 1]
    moves = rows("""SELECT from_ck, to_ck, transfer_km2, relationship_type AS kind, rel_id AS row_id,
                           'district_relationship' AS source_table
                    FROM district_relationship WHERE year_a = ? AND year_b = ? AND ? IN (from_ck, to_ck)
                    UNION ALL
                    SELECT from_ck, to_ck, transfer_km2, 'TRANSFER' AS kind, transfer_id AS row_id,
                           'measured_area_transfer' AS source_table
                    FROM measured_area_transfer WHERE year_a = ? AND year_b = ? AND ? IN (from_ck, to_ck)
                    ORDER BY transfer_km2 DESC""", [year_a, year_b, ck, year_a, year_b, ck])
    features = []
    for m in moves:
        if m["transfer_km2"] < MATERIAL_KM2:
            continue
        g = rows("""SELECT ST_AsGeoJSON(ST_Intersection(a.geometry, b.geometry)) AS g,
                           fa.latest_name AS from_name, tb.latest_name AS to_name
                    FROM district_geometry a, district_geometry b, ck_registry fa, ck_registry tb
                    WHERE a.canonical_key = ? AND a.year = ? AND b.canonical_key = ? AND b.year = ?
                      AND fa.canonical_key = a.canonical_key AND tb.canonical_key = b.canonical_key""",
                 [m["from_ck"], year_a, m["to_ck"], year_b])
        if not g or not g[0]["g"]:
            continue
        features.append({"type": "Feature", "geometry": json.loads(g[0]["g"]),
                         "properties": {**m, "direction": "out" if m["from_ck"] == ck else "in",
                                        "from_name": g[0]["from_name"], "to_name": g[0]["to_name"]}})
    return ok({"year_a": year_a, "year_b": year_b, "type": "FeatureCollection", "features": features})


@api.get("/districts/{ck}/evidence")
def evidence(ck: str = PathParam(pattern=CK)):
    registry_row(ck)
    return ok({"claims": rows("""SELECT v.claim_type, v.verdict, v.reason, v.our_value, c.value, c.citation, v.claim_id
                                 FROM claim_verdict v JOIN evidence_claim c USING (claim_id)
                                 WHERE v.canonical_key = ? ORDER BY v.claim_type, v.claim_id""", [ck]),
               "research_queue": rows("""SELECT q.* FROM research_queue q WHERE q.ref = ? OR q.ref IN (
                                          SELECT claim_id FROM claim_verdict WHERE canonical_key = ?)
                                          OR q.ref IN (SELECT participant_id FROM event_linkage WHERE canonical_key = ?)
                                         ORDER BY topic, queue_item_id""", [ck, ck, ck])})


@api.get("/districts/{ck}/harmonized")
def harmonized(ck: str = PathParam(pattern=CK), indicator: str | None = None):
    """Statistics restated on this 2025 district, with method, stated assumption and coverage."""
    registry_row(ck)
    where, params = ["target_ck = ?"], [ck]
    if indicator:
        where.append("indicator = ?")
        params.append(indicator)
    return ok({"totals": rows(f"SELECT * FROM stat_harmonized_value WHERE {' AND '.join(where)} "
                              "ORDER BY indicator, method, year", params),
               "ratios": rows(f"SELECT * FROM stat_ratio_value WHERE {' AND '.join(where)} "
                              "ORDER BY indicator, method, year", params)})


@api.get("/crosswalk")
def crosswalk(from_year: int, ck: str, direction: str = Query("forward", pattern="^(forward|reverse)$")):
    col = "source_ck" if direction == "forward" else "target_ck"
    other = "target_ck" if direction == "forward" else "source_ck"
    label = other.replace("_ck", "")
    return ok(rows(f"""SELECT x.*, n.latest_name AS {label}_name, n.latest_state AS {label}_state
                       FROM crosswalk_to_reference x JOIN ck_registry n ON n.canonical_key = x.{other}
                       WHERE x.year = ? AND x.{col} = ? ORDER BY x.area_km2 DESC""", [from_year, ck]))


@api.get("/events")
def events(ck: str | None = None, year: int | None = None, limit: int = Query(200, le=2000)):
    where, params = ["1=1"], []
    if ck:
        where.append("e.event_id IN (SELECT event_id FROM event_linkage WHERE canonical_key = ?)")
        params.append(ck)
    if year:
        where.append("e.effective_year = ?")
        params.append(year)
    return ok(rows(f"""SELECT e.*, s.measurement_status
                       FROM boundary_event e JOIN event_status s USING (event_id) WHERE {' AND '.join(where)}
                       ORDER BY e.effective_year, e.event_id LIMIT ?""", [*params, limit]))


@api.get("/research")
def research(topic: str | None = None, status: str = "OPEN", state: str | None = None,
             limit: int = Query(500, le=5000)):
    where, params = ["status = ?"], [status]
    if topic:
        where.append("topic = ?")
        params.append(topic)
    if state:
        where.append("state ILIKE ?")
        params.append(state)
    return ok(rows(f"SELECT * FROM research_queue WHERE {' AND '.join(where)} ORDER BY topic, state, subject LIMIT ?",
                   [*params, limit]))


@api.get("/validation")
def validation():
    checks = pd.read_csv(release_file("validation/s12_checks.csv"))
    return ok({"checks": json.loads(checks.to_json(orient="records")),
               "report_markdown": release_file("validation/s12_validation_report.md").read_text(encoding="utf-8")})


@api.get("/dictionary")
def dictionary():
    return ok(json.loads(release_file("data_dictionary.json").read_text(encoding="utf-8")))


app = FastAPI(title="District Evolution", version=INFO["pipeline_version"],
              description="India's district identities, lineage, area crosswalks and harmonized statistics, "
                          "1951-2025. Read-only.")
app.include_router(api)

if (WEB / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        target = (WEB / path).resolve()
        if path and target.is_file() and WEB.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(WEB / "index.html")
else:
    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    def web_missing():
        return ("<p>The web app is not built. Run <code>npm ci && npm run build</code> in <code>web/</code>; "
                "the API is at <a href='/docs'>/docs</a>.</p>")
