"""Harmonization engine (WP4): linking, allocation of totals only, ratios recomputed, time mapping."""

import pandas as pd
import pytest
import yaml

from district_evolution import core
from district_evolution.harmonize import engine
from district_evolution.harmonize.indicators import CsvIndicator
from district_evolution.harmonize.weights import AreaWeight

pytestmark = pytest.mark.skipif(not (core.PRODUCTS_DIR / "crosswalk_to_reference.parquet").exists(),
                                reason="pipeline not built")
COLS = {"raw_name": "District", "state": "State", "year": "Year", "value": "Value"}


def indicator(tmp_path, code, unit, rows):
    path = tmp_path / f"{code}.csv"
    pd.DataFrame(rows, columns=["District", "State", "Year", "Value"]).to_csv(path, index=False)
    return CsvIndicator(code=code, unit=unit, kind="extensive", path=str(path), source="synthetic test", columns=COLS)


def harmonize(ind):
    obs = engine.link(ind.observations())
    return obs, engine.allocate(obs, AreaWeight().weights(1951), "extensive")


def test_a_ratio_is_never_allocated(tmp_path):
    obs = engine.link(indicator(tmp_path, "x", "t", [("Kangra", "Punjab", 1951, 1.0)]).observations())
    with pytest.raises(engine.RatioAllocationError):
        engine.allocate(obs, AreaWeight().weights(1951), "ratio")


def test_kangra_1951_production_and_yield(tmp_path):
    """Kangra 1951: 46% of its land is in today's Lahaul & Spiti, so area weighting sends 46% of any
    crop total there. The yield, recomputed from both totals, stays 2.0 everywhere; the assumption
    (crops spread evenly over land) is what a cropland weight will test."""
    prod_obs, prod = harmonize(indicator(tmp_path, "prod_t", "t", [("Kangra", "Punjab", 1951, 100.0)]))
    _, area = harmonize(indicator(tmp_path, "area_ha", "ha", [("Kangra", "Punjab", 1951, 50.0)]))
    assert prod_obs.link_status.tolist() == ["LINKED"] and prod_obs.canonical_key.tolist() == ["IND-000202"]
    names = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key").latest_name
    share = prod.assign(name=prod.target_ck.map(names)).set_index("name").value / 100.0
    assert share["Lahul & Spiti"] == pytest.approx(0.46, abs=0.005)
    assert prod.value.sum() == pytest.approx(100.0 * AreaWeight().weights(1951).query("source_ck == 'IND-000202'").weight.sum())
    y = engine.ratios(pd.concat([prod, area]), {"code": "yield", "numerator": "prod_t", "denominator": "area_ha"})
    assert y.value.round(12).unique().tolist() == [2.0]


def test_unlinked_names_are_kept_not_guessed(tmp_path):
    obs = engine.link(indicator(tmp_path, "x", "t", [("Nowhere District", "Punjab", 1951, 5.0)]).observations())
    assert obs.link_status.tolist() == ["UNLINKED"] and obs.canonical_key.isna().all()


def test_a_value_after_an_unmapped_boundary_change_is_flagged(tmp_path):
    """Kangra lost land in 1972; a 1975 value sits on the 1971 map, so its boundary is not observed."""
    obs = engine.link(indicator(tmp_path, "x", "t", [("Kangra", "Himachal Pradesh", 1971, 1.0),
                                                     ("Kangra", "Himachal Pradesh", 1975, 1.0)]).observations())
    assert obs.map_year.tolist() == [1971.0, 1971.0]
    assert obs.boundary_uncertain.tolist() == [False, True]


def test_harmonization_never_feeds_earlier_stages():
    stages = yaml.safe_load((core.PROJECT_ROOT / "dvc.yaml").read_text())["stages"]
    paths = ("data/gold/harmonize", "outputs/harmonize")
    for name, stage in stages.items():
        outs = [next(iter(o)) if isinstance(o, dict) else o for o in stage.get("outs", [])]
        if name.startswith("h"):
            assert all(o.startswith(paths) for o in outs), name
        elif name[:3] in {f"s{n:02d}" for n in range(1, 11)} or name.startswith("e"):
            assert not any(d.startswith(paths) for d in stage["deps"]), name
