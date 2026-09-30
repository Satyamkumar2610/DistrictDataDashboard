"""The s04 core-continuity rule on synthetic flow tables."""

import pandas as pd

from district_evolution.stages import s04_identity as s04


def targets(rows):
    """rows: (target_obs, r, h); returned largest-area first, as s04 passes them."""
    df = pd.DataFrame(rows, columns=["geom_obs_id_b", "r", "h"])
    return df.sort_values("r", ascending=False).reset_index(drop=True)


NAMES = pd.Series({"KANGRA": "kangra", "PUNE": "pune", "JHANSI": "jhansi", "LALITPUR": "lalitpur",
                   "KOZHIKODE": "kozhikode", "KANNUR": "kannur", "MEDAK": "medak",
                   "SIDDIPET": "siddipet", "BIG": "bigdistrict", "NEWNAME": "freshname"})


def test_unchanged_district_is_strong():
    cls, row, _, _ = s04.decide("kangra", targets([("KANGRA", 0.99, 0.98)]), NAMES)
    assert cls == "STRONG" and row.geom_obs_id_b == "KANGRA"


def test_rename_with_intact_territory_continues_regardless_of_name():
    cls, _row, agree, _ = s04.decide("oldtown", targets([("NEWNAME", 1.0, 1.0)]), NAMES)
    assert cls == "STRONG" and not agree


def test_absorbing_territory_keeps_identity():
    cls, _, _, _ = s04.decide("kangra", targets([("KANGRA", 0.97, 0.7)]), NAMES)
    assert cls == "ABSORPTION_CORE"


def test_even_split_continues_into_the_child_that_keeps_the_name():
    # Jhansi 1971 -> Lalitpur 50.04% (largest) / Jhansi 49.9%
    t = targets([("LALITPUR", 0.5004, 1.0), ("JHANSI", 0.499, 1.0)])
    cls, row, _, _ = s04.decide("jhansi", t, NAMES)
    assert row.geom_obs_id_b == "JHANSI" and cls == "NAME_RETAINED_CORE"


def test_multiway_carve_out_with_small_named_remainder_continues():
    t = targets([("SIDDIPET", 0.40, 1.0), ("MEDAK", 0.28, 0.98)])
    cls, row, _, _ = s04.decide("medak", t, NAMES)
    assert cls == "NAME_RETAINED_CORE" and row.geom_obs_id_b == "MEDAK"


def test_split_where_no_child_keeps_the_name_closes_the_parent():
    # Malabar 1957 -> Kozhikode 51%, Kannur 29%, ...
    t = targets([("KOZHIKODE", 0.51, 1.0), ("KANNUR", 0.29, 0.65)])
    cls, _, _, _ = s04.decide("malabar", t, NAMES)
    assert cls == "BREAK_NAME_DIFFERS"


def test_absorbed_into_larger_district_is_a_break():
    cls, _, _, _ = s04.decide("smalldistrict", targets([("BIG", 1.0, 0.3)]), NAMES)
    assert cls == "BREAK_NO_CORE"


def window(parts, areas_a, areas_b, names_a, names_b):
    """A one-window flow table: parts are (source, target, km2)."""
    flow = pd.DataFrame([{"kind": "ADJACENT", "year_a": 1981, "year_b": 1991, "geom_obs_id_a": a, "geom_obs_id_b": b,
                          "total_km2": km2, "sliver_km2": 0.0} for a, b, km2 in parts])
    a = pd.DataFrame({"geom_obs_id": list(areas_a), "area_km2": list(areas_a.values()),
                      "district_name_norm": [names_a[k] for k in areas_a]})
    b = pd.DataFrame({"geom_obs_id": list(areas_b), "area_km2": list(areas_b.values()),
                      "district_name_norm": [names_b[k] for k in areas_b]})
    return s04.window_decisions(1981, 1991, flow, a, b).set_index("geom_obs_id_a")


def test_intact_district_that_grows_keeps_its_identity():
    """Una 1981 -> 1991: all of Una (945 km2) and 1,169 km2 of Kangra form the new Una; Kangra continues."""
    d = window([("una81", "una91", 945), ("kan81", "kan91", 5177), ("kan81", "una91", 1169)],
               {"una81": 945, "kan81": 6346}, {"una91": 2114, "kan91": 5177},
               {"una81": "una", "kan81": "kangra"}, {"una91": "una", "kan91": "kangra"})
    assert d.loc["una81", "continuity_class"] == "GROWTH_NAME_RETAINED" and d.loc["una81", "continues"]
    assert d.loc["kan81", "continues"] and d.loc["kan81", "geom_obs_id_b"] == "kan91"


def test_growth_never_takes_a_target_another_district_continues_into():
    """A small same-named district inside a target another district continues as: it closes."""
    d = window([("big81", "big91", 900), ("tiny81", "big91", 100)],
               {"big81": 900, "tiny81": 100}, {"big91": 1000},
               {"big81": "bigdistrict", "tiny81": "bigdistrict"}, {"big91": "bigdistrict"})
    assert d.loc["big81", "continues"] and not d.loc["tiny81", "continues"]


def test_growth_needs_the_name():
    d = window([("a81", "b91", 400), ("c81", "b91", 600)], {"a81": 400, "c81": 1000}, {"b91": 1000, "c91": 400},
               {"a81": "alpha", "c81": "gamma"}, {"b91": "beta", "c91": "gamma"})
    assert not d.loc["a81", "continues"]
