"""Harmonization library, quality estimators and review scoring on synthetic data,
plus property-style checks of the overlay on random grid partitions."""

import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

import harmonize
import lib
import quality
import s03_transition_matrix as s03

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "audit"))
import review_score  # noqa: E402

# A (100 km2) splits 60/40 into T1/T2; B (50 km2) lies wholly in T2.
XW = pd.DataFrame({"source_ck": ["A", "A", "B"], "target_ck": ["T1", "T2", "T2"],
                   "area_km2": [60.0, 40.0, 50.0], "area_km2_low": [58.0, 38.0, 50.0],
                   "area_km2_high": [61.0, 41.0, 50.0]})
SRC = pd.Series({"A": 100.0, "B": 50.0})
TGT = pd.Series({"T1": 60.0, "T2": 90.0})


def test_restate_count_is_area_weighted_and_conserves_totals():
    v = pd.DataFrame({"source_ck": ["A", "B"], "value": [1000.0, 300.0]})
    r = harmonize.restate(v, XW, SRC, TGT).set_index("target_ck")
    assert r.loc["T1", "value"] == pytest.approx(600.0)
    assert r.loc["T2", "value"] == pytest.approx(400.0 + 300.0)
    assert r.value.sum() == pytest.approx(1300.0)
    assert (r.value_low <= r.value).all() and (r.value <= r.value_high).all()
    assert r.loc["T1", "largest_source_share"] == pytest.approx(1.0)
    assert r.loc["T2", "coverage_share"] == pytest.approx(1.0)


def test_missing_source_lowers_coverage_and_never_rescales():
    v = pd.DataFrame({"source_ck": ["A", "B"], "value": [1000.0, np.nan]})
    r = harmonize.restate(v, XW, SRC, TGT).set_index("target_ck")
    assert r.loc["T2", "value"] == pytest.approx(400.0)              # B missing: not filled in
    assert r.loc["T2", "coverage_share"] == pytest.approx(40.0 / 90.0)


def test_rates_are_restated_through_their_denominator():
    # A: rate 0.5 on 1000 people, B: rate 0.9 on 300 people
    v = pd.DataFrame({"source_ck": ["A", "B"], "rate": [0.5, 0.9], "pop": [1000.0, 300.0]})
    r = harmonize.restate(v, XW, SRC, TGT, value_col="rate", kind="rate", denominator_col="pop").set_index("target_ck")
    assert r.loc["T1", "value"] == pytest.approx(0.5)
    assert r.loc["T2", "value"] == pytest.approx((0.5 * 400 + 0.9 * 300) / 700)   # not the area-weighted mean
    with pytest.raises(ValueError, match="denominator"):
        harmonize.restate(v, XW, SRC, TGT, value_col="rate", kind="rate")


def test_aggregate_to_units_is_exact_and_refuses_partial_sums():
    members = pd.DataFrame({"unit_id": ["U1", "U1", "U2"], "year": [1991] * 3, "canonical_key": ["A", "B", "C"]})
    v = pd.DataFrame({"source_ck": ["A", "B", "C"], "value": [10.0, 5.0, np.nan]})
    r = harmonize.aggregate_to_units(v, members, 1991).set_index("unit_id")
    assert r.loc["U1", "value"] == 15.0 and r.loc["U1", "complete"]
    assert math.isnan(r.loc["U2", "value"]) and not r.loc["U2", "complete"]


def test_chapman_estimator():
    r = quality.chapman(100, 80, 60)
    assert r["n_hat"] == pytest.approx(101 * 81 / 61 - 1)
    assert r["observed"] == 120 and r["missed_by_both"] == pytest.approx(r["n_hat"] - 120)
    assert r["ci_low"] >= r["observed"] and r["ci_low"] <= r["n_hat"] <= r["ci_high"]
    with pytest.raises(ValueError):
        quality.chapman(10, 10, 11)


def test_auc_reports_constant_scores_and_ranks_correctly():
    assert quality.auc(np.ones(10), np.r_[np.ones(5), np.zeros(5)].astype(bool))["status"] == "CONSTANT"
    perfect = quality.auc(np.arange(10.0), np.arange(10) >= 5)
    assert perfect["status"] == "TESTED" and perfect["auc"] == pytest.approx(1.0)
    ties = quality.auc(np.array([1, 1, 2, 2.0]), np.array([0, 1, 0, 1], bool))
    assert ties["auc"] == pytest.approx(0.5)


def test_wilson_interval_and_stratified_score():
    lo, hi = review_score.wilson(27, 30)
    assert lo < 0.9 < hi and 0 < lo and hi < 1
    form = pd.DataFrame({"stratum": ["identity:A"] * 4 + ["identity:B"] * 2,
                         "verdict": ["CORRECT", "CORRECT", "INCORRECT", "UNSURE", "CORRECT", ""]})
    strata = pd.DataFrame({"stratum": ["identity:A", "identity:B"], "population": [300, 100]})
    s = review_score.score(form, strata).set_index("stratum")
    assert s.loc["identity:A", "precision"] == pytest.approx(2 / 3)
    assert s.loc["identity:ALL (stratified)", "precision"] == pytest.approx(0.75 * 2 / 3 + 0.25 * 1.0)


# ---- property-style: random grid partitions ---------------------------------

def grid_layer(rng, n, prefix, merge_prob):
    """A partition of the unit square: an n x n grid with random horizontal merges."""
    rows = []
    for i in range(n):
        j = 0
        while j < n:
            k = j + 1
            while k < n and rng.random() < merge_prob:
                k += 1
            rows.append({"geom_obs_id": f"{prefix}{i}_{j}", "geometry": box(j / n, i / n, k / n, (i + 1) / n)})
            j = k
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    g["area_km2"] = g.geometry.apply(lib.geodesic_area_km2)
    return g


@pytest.mark.parametrize("seed", range(6))
def test_overlay_of_random_partitions_conserves_area_both_ways(seed):
    rng = np.random.default_rng(seed)
    a, b = grid_layer(rng, 6, "a", 0.5), grid_layer(rng, 6, "b", 0.3)
    parts = s03.classify_parts(a, b, 1.0)
    for side, layer in (("obs_a", a), ("obs_b", b)):
        got = parts.groupby(side).part_km2.sum()
        want = layer.set_index("geom_obs_id").area_km2
        err = (got.reindex(want.index).fillna(0) - want).to_numpy()
        assert all(lib.within_closure(e, w) for e, w in zip(err, want.to_numpy()))
    assert set(parts.part_class) <= {"core", "transfer", "displacement", "sliver"}
