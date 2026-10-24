"""Bring-your-own harmonization (restate, CLI, POST /api/harmonize) against the release."""

import pandas as pd
import pytest

from district_evolution import core
from district_evolution.harmonize import engine, restate

TABLES = core.RELEASE_DIR / "tables"

pytestmark = pytest.mark.skipif(not (core.RELEASE_DIR / "MANIFEST.csv").exists(),
                                reason="release not built; run dvc repro")


def kept_share(ck: str, year: int) -> float:
    """Share of a district's land on `year`'s map that lies in 2025 districts (weights are never renormalised)."""
    x = pd.read_parquet(TABLES / "crosswalk_to_reference.parquet")
    return x[(x.source_ck == ck) & (x.year == year)].share_of_source.sum()


@pytest.fixture(scope="module")
def areas_1991():
    a = pd.read_parquet(TABLES / "district_area_admin.parquet").query("year == 1991")
    return pd.DataFrame({"name": a.district_name, "state": a.state, "year": a.year, "value": a.area_km2})


def test_restating_a_maps_own_areas_reproduces_the_pipeline(areas_1991):
    """The 1991 map's areas restated from the release equal h03's mapped-area result for 1991."""
    links, out = restate.restate(areas_1991, tables=TABLES)
    assert (links.link_status == "LINKED").all()
    ref = (pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_harmonized_value.parquet")
           .query("indicator == 'mapped_area_km2' and year == 1991 and method == 'AREA'").set_index("target_ck").value)
    got = out.set_index("target_ck").value
    assert set(got.index) == set(ref.index)
    assert (got - ref.loc[got.index]).abs().max() < 1e-6


def test_rows_that_cannot_be_used_say_why(areas_1991):
    df = pd.DataFrame({"name": ["Kangra", "Khangara", "Kangra", "Nowhere"], "state": ["Himachal Pradesh"] * 4,
                       "year": [1991, 1991, 1940, 1991], "value": ["10", "5", "3", "x"]})
    links, out = restate.restate(df, tables=TABLES)
    assert links.link_status.tolist() == ["LINKED", "UNLINKED", "BEFORE_FIRST_MAP", "UNLINKED"]
    assert [c["district_name"] for c in links.candidates[1]] == ["Kangra"]
    assert out.value.sum() == pytest.approx(10 * kept_share("IND-000202", 1991), rel=1e-12)


def test_a_rate_is_refused():
    df = pd.DataFrame({"name": ["Kangra"], "state": ["Himachal Pradesh"], "year": [1991], "value": [2.1]})
    with pytest.raises(engine.RatioAllocationError):
        restate.restate(df, kind="ratio", tables=TABLES)


def test_cli_writes_result_and_report(tmp_path, areas_1991):
    from district_evolution.harmonize import cli
    src = tmp_path / "in.csv"
    areas_1991.rename(columns={"name": "district"}).to_csv(src, index=False)
    assert cli.main([str(src), "--out", str(tmp_path / "out.csv"), "--indicator", "area_km2"]) == 0
    assert len(pd.read_csv(tmp_path / "out.csv")) > 600
    assert (pd.read_csv(tmp_path / "out_matching_report.csv").link_status == "LINKED").all()


def test_api_harmonize(areas_1991):
    from fastapi.testclient import TestClient

    from district_evolution.release.api import app
    c = TestClient(app)
    body = {"rows": [{"name": "Kangra", "state": "Himachal Pradesh", "year": 1971, "value": "100"},
                     {"name": "Kangra", "state": "", "year": 1971, "value": "1"}], "indicator": "x"}
    # both rows reach the same identity in the same year: allocating both would count Kangra twice
    d = c.post("/api/harmonize", json=body).json()["data"]
    assert (d["summary"]["linked"], d["summary"]["duplicate"]) == (0, 2) and d["summary"]["value_allocated"] == 0
    body = {**body, "rows": body["rows"][:1]}
    d = c.post("/api/harmonize", json=body).json()["data"]
    assert d["summary"]["linked"] == 1
    assert d["summary"]["value_allocated"] == pytest.approx(100 * kept_share("IND-000202", 1971), rel=1e-12)
    # Kangra's 1971 land now lies in several 2025 districts (Kangra, Hamirpur, Una)
    assert len(d["harmonized"]) >= 3
    assert c.post("/api/harmonize", json={**body, "kind": "ratio"}).status_code == 422


def test_unknown_state_is_unlinked_not_an_error():
    """A state with no districts on the map leaves no candidates; the row is UNLINKED (was a crash)."""
    df = pd.DataFrame({"name": ["Kangra"], "state": ["Atlantis"], "year": [1991], "value": ["5"]})
    links, out = restate.restate(df, tables=TABLES)
    assert links.link_status.tolist() == ["UNLINKED"] and out.empty
