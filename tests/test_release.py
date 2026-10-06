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
    on_disk = {str(p.relative_to(release)) for p in release.rglob("*")
               if p.is_file() and p.name not in {"MANIFEST.csv", ".DS_Store"}}
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
    lineage = api.get(f"/api/districts/{ck}/lineage?direction=descendants&max_depth=1").json()["data"]
    kids = {r["to_name"] for r in lineage["descendants"]}
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
    assert totals == {"MEASURED": 399, "UNIDENTIFIED_MULTI_EVENT_WINDOW": 189, "NOT_MEASURABLE": 21}


def test_release_states_its_validation(api):
    checks = api.get("/api/validation").json()["data"]["checks"]
    assert not [c for c in checks if c["severity"] == "ERROR" and c["n_violations"] > 0]


def test_states_count_districts_on_every_map(api):
    states = {s["state"]: s for s in api.get("/api/states").json()["data"]}
    assert sum(s["active"] for s in states.values()) == 733
    hp = states["Himachal Pradesh"]
    assert (hp["districts_by_map"]["1951"], hp["districts_by_map"]["2025"]) == (8, 12)


def test_state_history_lists_its_lineage(api):
    d = api.get("/api/states/Himachal Pradesh").json()["data"]
    assert {i["canonical_key"] for i in d["identities"]} >= {"IND-000202", "IND-000416"}
    assert any(e["to_name"] == "Hamirpur" and e["from_name"] == "Kangra" for e in d["changes"])
    assert api.get("/api/states/Atlantis").status_code == 404


def test_genealogy_walks_ancestors_and_descendants(api):
    d = api.get("/api/districts/IND-000148/genealogy").json()["data"]
    names = {n["latest_name"] for n in d["nodes"]}
    assert d["focus"] == "IND-000148" and {"Malabar", "Kozhikode", "Palakkad"} <= names
    keys = {n["canonical_key"] for n in d["nodes"]}
    assert all(e["from_ck"] in keys and e["to_ck"] in keys for e in d["edges"])


def test_release_tables_download(api):
    r = api.get("/api/download/crosswalk_to_reference.csv")
    assert r.status_code == 200 and "share_of_source" in r.text.splitlines()[0]
    assert api.get("/api/download/crosswalk_to_reference.parquet").content[:4] == b"PAR1"
    assert api.get("/api/download/not_a_table.csv").status_code == 404



def test_wikidata_comparison_is_internal(api):
    """The Wikidata tables are built and checked but not released, served or queued in the release."""
    names = {p.stem for p in (core.RELEASE_DIR / "tables").glob("*.parquet")}
    assert not names & {"evidence_claim", "claim_ck_link", "claim_verdict"}
    q = pd.read_parquet(core.RELEASE_DIR / "tables" / "research_queue.parquet")
    assert "CLAIM_CONFLICT" not in set(q.topic) and len(q) > 0
    assert api.get("/api/evidence/summary").status_code == 404
    assert "evidence" not in api.get("/api/overview").json()["data"]
    assert (core.GOLD_EVIDENCE_DIR / "claim_verdict.parquet").exists()  # still built, for the gate


def test_district_research_lists_its_open_questions(api):
    ids = pd.read_parquet(core.RELEASE_DIR / "tables" / "research_queue.parquet")
    items = api.get("/api/districts/IND-000202/research").json()["data"]
    assert all(i["queue_item_id"] in set(ids.queue_item_id) for i in items)


def test_release_provenance_is_content_addressed(release):
    """release_info records a hash of the code that built it, not a git commit (which would make
    every commit invalidate the release's own hash in dvc.lock)."""
    prov = json.loads((core.RELEASE_DIR / "release_info.json").read_text())["provenance"]
    assert "source_commit" not in prov and len(prov["code_sha256"]) == 64
    from district_evolution.core.provenance import code_sha256
    assert prov["code_sha256"] == code_sha256()


def test_health_probe_is_cheap_and_versioned(api):
    r = api.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["pipeline_version"] == core.PIPELINE_VERSION


def test_responses_carry_security_headers_and_large_ones_are_compressed(api):
    r = api.get("/api/download/crosswalk_to_reference.csv", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip"
    for h in (r, api.get("/api/districts/IND-999999")):
        assert h.headers["x-content-type-options"] == "nosniff" and h.headers["x-frame-options"] == "SAMEORIGIN"


def test_oversized_request_bodies_are_refused_before_parsing(api):
    from district_evolution.release.api import MAX_REQUEST_BYTES
    big = b'{"rows": [' + b" " * (MAX_REQUEST_BYTES + 1) + b"]}"
    r = api.post("/api/harmonize", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.headers["x-content-type-options"] == "nosniff"

    def chunks():  # a streamed body with no declared length is counted as it arrives
        yield b'{"rows": ['
        for _ in range(MAX_REQUEST_BYTES // 1_000_000 + 2):
            yield b" " * 1_000_000
    assert api.post("/api/harmonize", content=chunks(), headers={"content-type": "application/json"}).status_code == 413


def test_harmonized_values_come_with_their_method_sensitivity(api):
    d = api.get("/api/districts/IND-000202/harmonized").json()["data"]
    assert set(d) == {"totals", "ratios", "sensitivity"}
    assert {t["method"] for t in d["totals"]} == {"AREA"}
    released = pd.read_parquet(core.RELEASE_DIR / "tables" / "harmonization_method_sensitivity.parquet")
    assert len(d["sensitivity"]) == int((released.target_ck == "IND-000202").sum())


def test_the_platform_imports_no_pipeline_only_library(release):
    """The container installs requirements-platform.txt only, so the API must not import anything else
    from requirements.txt (geopandas, shapely, rasterio, splink, pandera, dvc, ...)."""
    import os
    import subprocess
    import sys

    def names(f):
        return {ln.split("==")[0].strip().lower() for ln in (core.PROJECT_ROOT / f).read_text().splitlines()
                if "==" in ln and not ln.startswith("#")}
    pipeline_only = names("requirements.txt") - names("requirements-platform.txt") - {"pytest", "httpx"}
    code = "import sys, district_evolution.release.api; print(' '.join(sys.modules))"
    env = {**os.environ, "DISTRICT_RELEASE_DIR": str(release), "PYTHONPATH": str(core.PROJECT_ROOT)}
    loaded = set(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env)
                 .stdout.split())
    assert pipeline_only and not pipeline_only & loaded


def _basic(user: str, password: str) -> dict[str, str]:
    import base64
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def private_client():
    """The app wrapped in the same auth middleware a hosted instance runs, over a trivial inner app."""
    from fastapi.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    from district_evolution.release.api import RequireAuth

    async def ok(request):
        return PlainTextResponse("served")

    inner = Starlette(routes=[Route("/api/health", ok), Route("/api/download/x.parquet", ok),
                              Route("/", ok)])
    inner.add_middleware(RequireAuth, user="district", password="s3cret", open_paths=("/api/health",))
    return TestClient(inner)


def test_a_private_instance_refuses_everything_without_the_password(private_client):
    for path in ("/", "/api/download/x.parquet"):
        r = private_client.get(path)
        assert r.status_code == 401, path
        assert r.headers["www-authenticate"].startswith("Basic ")
        assert "served" not in r.text


def test_a_private_instance_serves_with_the_password(private_client):
    for path in ("/", "/api/download/x.parquet"):
        r = private_client.get(path, headers=_basic("district", "s3cret"))
        assert r.status_code == 200 and r.text == "served", path


def test_a_wrong_user_or_password_is_refused(private_client):
    for user, password in (("district", "wrong"), ("someone", "s3cret"), ("", ""), ("district", "")):
        assert private_client.get("/", headers=_basic(user, password)).status_code == 401


def test_malformed_credentials_do_not_crash_the_middleware(private_client):
    for header in ("Basic !!!notbase64", "Basic", "Bearer s3cret", "", "Basic " + "x" * 5000):
        assert private_client.get("/", headers={"Authorization": header}).status_code == 401


def test_the_health_probe_stays_open_so_the_platform_can_check_it(private_client):
    r = private_client.get("/api/health")
    assert r.status_code == 200 and r.text == "served"


def test_without_a_password_the_app_is_open(api):
    """The localhost case: no DISTRICT_AUTH_PASSWORD, so the app this suite built serves freely."""
    from district_evolution.release.api import AUTH_PASSWORD
    assert AUTH_PASSWORD == ""
    assert api.get("/api/meta").status_code == 200
