"""Read-only API over a release (data/release by default; set DISTRICT_RELEASE_DIR to serve another).

    uvicorn district_evolution.release.api:app

Every response is {"meta": {pipeline_version, config_sha256, ...}, "data": ...}. The API only
reads the release files; the batch pipeline is the only writer. OpenAPI is at /docs and /openapi.json.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import HTMLResponse

from district_evolution import core
from district_evolution.release import TABLES

RELEASE = Path(os.environ.get("DISTRICT_RELEASE_DIR", core.RELEASE_DIR))
INFO = json.loads((RELEASE / "release_info.json").read_text())
META = {k: INFO[k] for k in ("pipeline_version", "config_sha256", "events_csv_sha256", "reference_year")}
CK_PATTERN = r"^IND-\d{6}$"

_db = duckdb.connect()
_db.execute("INSTALL spatial; LOAD spatial;")
for _t in TABLES:
    _db.execute(f"CREATE VIEW {_t} AS SELECT * FROM read_parquet('{(RELEASE / 'tables' / f'{_t}.parquet').as_posix()}')")
_db.execute(f"CREATE VIEW district_geometry AS SELECT * FROM "
            f"read_parquet('{(RELEASE / 'geometry').as_posix()}/districts_*.geoparquet')")
_lock = threading.Lock()

app = FastAPI(title="District Evolution API", version=INFO["pipeline_version"],
              description="India's district identities, lineage and area crosswalks, 1951-2025. Read-only.")


def rows(sql: str, params: list | None = None) -> list[dict]:
    with _lock:
        cur = _db.cursor()
        res = cur.execute(sql, params or [])
        cols = [d[0] for d in res.description]
        return [dict(zip(cols, r)) for r in res.fetchall()]


def ok(data) -> dict:
    return {"meta": META, "data": data}


def registry_row(ck: str) -> dict:
    found = rows("SELECT * FROM ck_registry WHERE canonical_key = ?", [ck])
    if not found:
        raise HTTPException(404, f"no district identity {ck}")
    return found[0]


@app.get("/meta")
def meta():
    counts = {t: rows(f"SELECT count(*) AS n FROM {t}")[0]["n"] for t in TABLES}
    return ok({**INFO, "row_counts": counts})


@app.get("/districts")
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


@app.get("/districts/{ck}")
def district(ck: str = PathParam(pattern=CK_PATTERN)):
    return ok({**registry_row(ck),
               "observations": rows("SELECT year, district_name, state, area_km2, geom_obs_id FROM ck_observation "
                                    "WHERE canonical_key = ? ORDER BY year", [ck])})


@app.get("/districts/{ck}/timeline")
def timeline(ck: str = PathParam(pattern=CK_PATTERN)):
    registry_row(ck)
    return ok({"maps": rows("SELECT year, depicted_year, district_name, state, area_km2 FROM district_area_admin "
                            "WHERE canonical_key = ? ORDER BY year", [ck]),
               "ledger": rows("SELECT * FROM area_ledger WHERE canonical_key = ? ORDER BY year_a", [ck]),
               "transfers": rows("""SELECT t.*, f.latest_name AS from_name, o.latest_name AS to_name
                                    FROM measured_area_transfer t JOIN ck_registry f ON f.canonical_key = t.from_ck
                                    JOIN ck_registry o ON o.canonical_key = t.to_ck
                                    WHERE ? IN (t.from_ck, t.to_ck) ORDER BY t.year_b, t.transfer_km2 DESC""", [ck])})


@app.get("/districts/{ck}/lineage")
def lineage(ck: str = PathParam(pattern=CK_PATTERN), direction: str = Query("both", pattern="^(ancestors|descendants|both)$"),
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
            SELECT w.depth, r.*, f.latest_name AS from_name, t.latest_name AS to_name
            FROM w JOIN district_relationship r USING (rel_id)
            JOIN ck_registry f ON f.canonical_key = r.from_ck JOIN ck_registry t ON t.canonical_key = r.to_ck
            ORDER BY w.depth, r.year_b, r.rel_id""", [ck, max_depth])
    return ok(out)


@app.get("/districts/{ck}/geometry")
def geometry(year: int, ck: str = PathParam(pattern=CK_PATTERN)):
    found = rows("SELECT canonical_key, year, district_name, state, area_km2, ST_AsGeoJSON(geometry) AS g "
                 "FROM district_geometry WHERE canonical_key = ? AND year = ?", [ck, year])
    if not found:
        raise HTTPException(404, f"{ck} is not on the {year} map")
    f = found[0]
    return ok({"type": "Feature", "geometry": json.loads(f.pop("g")), "properties": f})


@app.get("/districts/{ck}/evidence")
def evidence(ck: str = PathParam(pattern=CK_PATTERN)):
    registry_row(ck)
    return ok({"claims": rows("""SELECT v.claim_type, v.verdict, v.reason, v.our_value, c.value, c.citation, v.claim_id
                                 FROM claim_verdict v JOIN evidence_claim c USING (claim_id)
                                 WHERE v.canonical_key = ? ORDER BY v.claim_type, v.claim_id""", [ck]),
               "research_queue": rows("""SELECT q.* FROM research_queue q WHERE q.ref = ? OR q.ref IN (
                                          SELECT claim_id FROM claim_verdict WHERE canonical_key = ?)
                                          OR q.ref IN (SELECT participant_id FROM event_linkage WHERE canonical_key = ?)
                                         ORDER BY topic, queue_item_id""", [ck, ck, ck])})


@app.get("/crosswalk")
def crosswalk(from_year: int, ck: str, direction: str = Query("forward", pattern="^(forward|reverse)$")):
    col = "source_ck" if direction == "forward" else "target_ck"
    other = "target_ck" if direction == "forward" else "source_ck"
    return ok(rows(f"""SELECT x.*, n.latest_name AS {other.replace('_ck', '')}_name
                       FROM crosswalk_to_reference x JOIN ck_registry n ON n.canonical_key = x.{other}
                       WHERE x.year = ? AND x.{col} = ? ORDER BY x.area_km2 DESC""", [from_year, ck]))


@app.get("/events")
def events(ck: str | None = None, year: int | None = None, limit: int = Query(200, le=2000)):
    where, params = ["1=1"], []
    if ck:
        where.append("e.event_id IN (SELECT event_id FROM event_linkage WHERE canonical_key = ?)")
        params.append(ck)
    if year:
        where.append("e.effective_year = ?")
        params.append(year)
    return ok(rows(f"""SELECT e.*, (SELECT list(a.measurement_status) FROM event_accounting a
                                    WHERE a.event_id = e.event_id) AS measurement_status
                       FROM boundary_event e WHERE {' AND '.join(where)}
                       ORDER BY e.effective_year, e.event_id LIMIT ?""", [*params, limit]))


@app.get("/research")
def research(topic: str | None = None, status: str = "OPEN", limit: int = Query(500, le=5000)):
    where, params = ["status = ?"], [status]
    if topic:
        where.append("topic = ?")
        params.append(topic)
    return ok(rows(f"SELECT * FROM research_queue WHERE {' AND '.join(where)} ORDER BY topic, state, subject LIMIT ?",
                   [*params, limit]))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def explorer():
    return (Path(__file__).parent / "explorer.html").read_text(encoding="utf-8")
