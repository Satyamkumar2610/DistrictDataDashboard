"""Rules added in pipeline v4: event-name parsing, predecessor grouping, the
skip-vintage identity rule, and enclave-aware overlap logging."""

import pandas as pd
import pytest

import lib
import s04_identity as s04
import s07_events_aggregate as s07

PROTECTED = frozenset({"jammu and kashmir", "andaman and nicobar islands", "daman and diu",
                       "united khasi and jaintia hills"})


@pytest.mark.parametrize("raw, expected", [
    ("Jammu And Kashmir", ["Jammu And Kashmir"]),                      # one entity, never split
    ("Andaman And Nicobar Islands", ["Andaman And Nicobar Islands"]),
    ("United Khasi And Jaintia Hills", ["United Khasi And Jaintia Hills"]),
    ("Daman And Diu", ["Daman And Diu"]),
    ("Kottayam And Trichur", ["Kottayam", "Trichur"]),                  # two parents
    ("East And North-East", ["East", "North-East"]),                    # Delhi: two parents
    ("Nalbari, Barpeta, Kamrup, And Darrang", ["Nalbari", "Barpeta", "Kamrup", "Darrang"]),
    ("Quilon, Alappuzha And Idukki", ["Quilon", "Alappuzha", "Idukki"]),
    ("Parts Of Meerut And Bulandshahr", ["Meerut", "Bulandshahr"]),     # qualifier dropped
    ("Kangra", ["Kangra"]),
    (None, []),
])
def test_parse_multi_name(raw, expected):
    assert lib.parse_multi_name(raw, PROTECTED) == expected


def test_predecessor_key_ignores_order_separator_and_known_spelling():
    k1 = s07.predecessor_key("Quilon And Kottayam", PROTECTED)[1]
    k2 = s07.predecessor_key("Kottayam, Quilon", PROTECTED)[1]
    k3 = s07.predecessor_key("Kottayam And Kollam", PROTECTED)[1]   # Quilon -> Kollam is a documented alias
    assert k1 == k2 == k3


# ---- rule 4: one defective map must not end an identity --------------------

def _layer(rows):
    return pd.DataFrame(rows, columns=["geom_obs_id", "district_name_norm", "area_km2"])


def _flow(kind, ya, yb, rows):
    return pd.DataFrame([{"kind": kind, "year_a": ya, "year_b": yb, "geom_obs_id_a": a, "geom_obs_id_b": b,
                          "total_km2": km2, "sliver_km2": 0.0} for a, b, km2 in rows])


def _kolkata(claimed=False, r=0.93):
    """2011 K11 (196 km2) -> 2021 K21 drawn at 98 km2 (defect) -> 2025 K25 (185 km2)."""
    layers = {2011: _layer([("K11", "kolkata", 196.0)]),
              2021: _layer([("K21", "kolkata", 98.0), ("N21", "north 24 parganas", 4000.0)]),
              2025: _layer([("K25", "kolkata", 185.0), ("N25", "north 24 parganas", 4000.0)])}
    flow = _flow("SKIP", 2011, 2025, [("K11", "K25", 183.0)])
    d = pd.DataFrame([
        {"year_a": 2021, "year_b": 2025, "geom_obs_id_a": "K21", "geom_obs_id_b": "K25", "r_share": r,
         "h_share": 0.49, "name_jw": 1.0, "names_agree": True, "continuity_class": "BREAK_NO_CORE",
         "continues": False, "evidence_year": 2021},
        {"year_a": 2021, "year_b": 2025, "geom_obs_id_a": "N21", "geom_obs_id_b": "K25" if claimed else "N25",
         "r_share": 0.97, "h_share": 0.95, "name_jw": 1.0, "names_agree": True, "continuity_class": "STRONG",
         "continues": True, "evidence_year": 2021}])
    return d, flow, layers


def test_skip_vintage_rescues_identity_broken_by_one_defective_map():
    d, flow, layers = _kolkata()
    out = s04.skip_vintage_rescue(d, 2021, 2025, flow, layers, {"K21": "K11"})
    row = out[out.geom_obs_id_a == "K21"].iloc[0]
    assert row.continuity_class == "SKIP_VINTAGE_CORE" and bool(row.continues) and row.evidence_year == 2011


def test_skip_vintage_never_takes_a_target_another_source_continues_into():
    d, flow, layers = _kolkata(claimed=True)
    out = s04.skip_vintage_rescue(d, 2021, 2025, flow, layers, {"K21": "K11"})
    assert not out[out.geom_obs_id_a == "K21"].iloc[0].continues


def test_skip_vintage_requires_the_broken_district_to_lie_inside_the_target():
    d, flow, layers = _kolkata(r=0.6)   # only 60% of the 2021 polygon is inside 2025 Kolkata
    out = s04.skip_vintage_rescue(d, 2021, 2025, flow, layers, {"K21": "K11"})
    assert not out[out.geom_obs_id_a == "K21"].iloc[0].continues


def test_skip_vintage_needs_an_earlier_observation():
    d, flow, layers = _kolkata()
    out = s04.skip_vintage_rescue(d, 2021, 2025, flow, layers, {})
    assert not out[out.geom_obs_id_a == "K21"].iloc[0].continues
