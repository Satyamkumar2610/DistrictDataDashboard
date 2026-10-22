"""Linkage keys, compound event names, footprint posterior, reversed transfers, duplicate identities."""

import pandas as pd
import pytest

from district_evolution import core
from district_evolution.harmonize import engine
from district_evolution.stages import s05_lineage, s09_event_reconciliation


@pytest.mark.parametrize(("a", "b"), [
    ("paschim medinipur", "medinipur west"),        # directional word in another language
    ("north twenty four parganas", "north 24 parganas"),  # number words
    ("uttar dinajpur", "north dinajpur"),
])
def test_linkage_key_equates_spellings_of_one_name(a, b):
    assert core.linkage_key(a) == core.linkage_key(b)


def test_qualifiers_separate_districts_and_do_not_carry_similarity():
    east, west = core.linkage_key("east nimar"), core.linkage_key("west nimar")
    assert east[0] == west[0] and east[1] != west[1]
    # the stem, not the shared qualifier, is what similarity is measured on
    assert core.jaro_winkler(core.linkage_key("paschim medinipur")[0], core.linkage_key("paschim bardhaman")[0]) < 0.8


def test_a_state_named_stem_counts_as_empty():
    assert core.linkage_key("east sikkim", "sikkim") == core.linkage_key("east", "sikkim")


def test_alias_resolves_before_fuzzy_comparison():
    stem, _ = core.linkage_key("alleppey")      # documentary alias of Alappuzha
    assert core.jaro_winkler(stem, core.linkage_key("alapuzha")[0]) >= 0.95


KNOWN = {"dadra and nagar haveli", "malabar", "south kanara", "united khasi and jaintia hills",
         "meerut", "bulandshahr", "daman", "diu", "sambhal"}


@pytest.mark.parametrize(("raw", "expected"), [
    ("Dadra And Nagar Haveli", [("Dadra And Nagar Haveli", False)]),
    ("United Khasi And Jaintia Hills", [("United Khasi And Jaintia Hills", False)]),
    ("Malabar And South Kanara", [("Malabar", False), ("South Kanara", False)]),
    ("Parts Of Meerut And Bulandshahr", [("Meerut", True), ("Bulandshahr", True)]),
    ("East Godavari, Visakhapatnam, Vizianagaram.", [("East Godavari", False), ("Visakhapatnam", False),
                                                     ("Vizianagaram", False)]),
    ("Unknownpur And Nowhere", [("Unknownpur And Nowhere", False)]),  # never split blindly
    ("Bhimnagar/Sambhal", [("Bhimnagar/Sambhal", False)]),
])
def test_compound_event_names(raw, expected):
    assert core.parse_participants(raw, KNOWN.__contains__) == expected


def test_slash_names_are_alternatives_of_one_district():
    assert core.split_name_alternatives("Panchsheel Nagar/Hapur") == ["Panchsheel Nagar", "Hapur"]


def test_footprint_posterior_rebases_the_prior():
    lam = 1 / 900
    p_map = pd.Series([0.14])                      # exact name, lineal state, map-wide prior
    bf = (p_map / (1 - p_map)) / (lam / (1 - lam))
    post = s09_event_reconciliation.footprint_posterior(bf, 5)
    assert post.iloc[0] > 0.9
    # a weak name stays weak even in a small footprint
    weak = (pd.Series([0.0005]) / 0.9995) / (lam / (1 - lam))
    assert s09_event_reconciliation.footprint_posterior(weak, 5).iloc[0] < 0.5


def test_reversals_flag_land_that_goes_and_comes_back():
    x = pd.DataFrame({"from_ck": ["A", "B", "A"], "to_ck": ["B", "A", "C"],
                      "year_a": [1961, 1971, 1961], "transfer_km2": [100.0, 95.0, 50.0]})
    out = s05_lineage.reversals(x)
    assert out.is_reversed.tolist() == [True, True, False]
    assert out.reversal_km2.tolist() == [95.0, 100.0, 0.0]


@pytest.mark.skipif(not (core.PRODUCTS_DIR / "crosswalk_to_reference.parquet").exists(), reason="pipeline not built")
def test_two_rows_for_one_identity_are_not_counted_twice():
    obs = pd.DataFrame({"raw_name": ["Kangra", "Kangra"], "state": ["Punjab", "Punjab"], "year": [1951, 1951],
                        "value": [10.0, 10.0], "indicator": ["x", "x"]})
    out = engine.link(obs)
    assert out.link_status.tolist() == ["DUPLICATE_IDENTITY", "DUPLICATE_IDENTITY"]
