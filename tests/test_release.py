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
    for path in ["/meta", "/districts?q=Kangra", "/research?topic=MAP_DATE"]:
        meta = api.get(path).json()["meta"]
        assert meta["pipeline_version"] == core.PIPELINE_VERSION and len(meta["config_sha256"]) == 64


def test_kangra_one_identity_with_its_carve_outs(api):
    ck = api.get("/districts", params={"q": "Kangra"}).json()["data"][0]["canonical_key"]
    d = api.get(f"/districts/{ck}").json()["data"]
    assert (d["established_year"], d["closed_year"]) == (1951, None)
    kids = {r["to_name"] for r in api.get(f"/districts/{ck}/lineage?direction=descendants&max_depth=1").json()["data"]["descendants"]}
    assert {"Kullu", "Hamirpur"} <= kids
    xw = api.get("/crosswalk", params={"from_year": 1951, "ck": ck}).json()["data"]
    assert sum(r["share_of_source"] for r in xw) == pytest.approx(1.0, abs=0.01)


def test_geometry_is_geojson_with_full_resolution_area(api):
    f = api.get("/districts/IND-000202/geometry", params={"year": 2025}).json()["data"]
    assert f["type"] == "Feature" and f["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    assert f["properties"]["area_km2"] > 0


def test_bad_and_unknown_keys(api):
    assert api.get("/districts/not-a-key").status_code == 422
    assert api.get("/districts/IND-999999").status_code == 404
