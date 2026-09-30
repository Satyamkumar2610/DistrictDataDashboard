"""Release (r01), data dictionary (r02) and the read-only API (r03)."""

import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq
import pytest

from district_evolution import core
from district_evolution.contracts import schemas
from district_evolution.release import TABLES

RELEASE = core.RELEASE_DIR


def test_every_released_column_has_a_contract_and_a_meaning():
    for table, src in TABLES.items():
        if not src.exists():
            pytest.skip("pipeline not built")
        contract = schemas.SCHEMAS[table].columns
        for col in pq.read_schema(src).names:
            assert col in contract, f"{table}.{col} has no contract"
            assert contract[col].description, f"{table}.{col} has no meaning in contracts/descriptions.py"
    geom = schemas.SCHEMAS["release_geometry"].columns
    assert all(c.description for c in geom.values())


@pytest.fixture(scope="module")
def release():
    if not (RELEASE / "MANIFEST.csv").exists():
        pytest.skip("release not built; run dvc repro")
    return RELEASE


def test_release_manifest_matches_the_files(release):
    man = pd.read_csv(release / "MANIFEST.csv")
    for row in man.itertuples():
        assert hashlib.sha256((release / row.path).read_bytes()).hexdigest() == row.sha256, row.path
    on_disk = {str(p.relative_to(release)) for p in release.rglob("*") if p.is_file() and p.name not in {"MANIFEST.csv", ".DS_Store"}}
    assert on_disk == set(man.path)


def test_release_carries_its_version(release):
    info = json.loads((release / "release_info.json").read_text())
    assert info["pipeline_version"] == core.PIPELINE_VERSION


@pytest.fixture(scope="module")
def api(release):
    from fastapi.testclient import TestClient

    from district_evolution.release.api import app
    return TestClient(app)


def test_every_response_carries_version_and_config_hash(api):
    for path in ["/api/meta", "/api/districts?q=Kangra", "/api/research?topic=MAP_DATE"]:
        meta = api.get(path).json()["meta"]
        assert meta["pipeline_version"] == core.PIPELINE_VERSION and len(meta["config_sha256"]) == 64


def test_kangra_one_identity_with_its_carve_outs(api):
    ck = api.get("/api/districts", params={"q": "Kangra"}).json()["data"][0]["canonical_key"]
    d = api.get(f"/api/districts/{ck}").json()["data"]
    assert (d["established_year"], d["closed_year"]) == (1951, None)
    kids = {r["to_name"] for r in api.get(f"/api/districts/{ck}/lineage?direction=descendants&max_depth=1").json()["data"]["descendants"]}
    assert {"Kullu", "Hamirpur"} <= kids
    xw = api.get("/api/crosswalk", params={"from_year": 1951, "ck": ck}).json()["data"]
    assert sum(r["share_of_source"] for r in xw) == pytest.approx(1.0, abs=0.01)


def test_geometry_is_geojson_with_full_resolution_area(api):
    f = api.get("/api/districts/IND-000202/geometry", params={"year": 2025}).json()["data"]
    assert f["type"] == "Feature" and f["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    assert f["properties"]["area_km2"] > 0


def test_bad_and_unknown_keys(api):
    assert api.get("/api/districts/not-a-key").status_code == 422
    assert api.get("/api/districts/IND-999999").status_code == 404


def test_vector_tiles_are_served_per_map(api):
    r = api.get("/api/tiles/2025/4/11/6.pbf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/vnd.mapbox-vector-tile" and len(r.content) > 1000
    assert api.get("/api/tiles/1999/4/11/6.pbf").status_code == 404


def test_change_parcels_carry_the_measured_figures(api):
    """Kangra between the 1971 and 1981 maps: Hamirpur and Una carved out, km2 from the lineage table."""
    d = api.get("/api/districts/IND-000202/changes", params={"year_b": 1981}).json()["data"]
    got = {f["properties"]["to_name"]: f["properties"] for f in d["features"]}
    assert set(got) == {"Hamirpur", "Una"} and d["year_a"] == 1971
    assert all(p["source_table"] == "district_relationship" and p["direction"] == "out" for p in got.values())
    assert round(got["Hamirpur"]["transfer_km2"]) == 1110


def test_overview_event_status_matches_the_pipeline_rule(api):
    events = api.get("/api/overview").json()["data"]["events"]
    totals = {}
    for e in events:
        totals[e["status"]] = totals.get(e["status"], 0) + e["events"]
    assert totals == {"MEASURED": 401, "UNIDENTIFIED_MULTI_EVENT_WINDOW": 186, "NOT_MEASURABLE": 22}


def test_release_states_its_validation(api):
    checks = api.get("/api/validation").json()["data"]["checks"]
    assert not [c for c in checks if c["severity"] == "ERROR" and c["n_violations"] > 0]
