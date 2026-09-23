"""The s04 core-continuity rule on synthetic flow tables."""

import pandas as pd
import s04_identity as s04


def targets(rows):
    """rows: (target_obs, r, h); returned largest-area first, as s04 passes them."""
    df = pd.DataFrame(rows, columns=["geom_obs_id_b", "r", "h"])
    return df.sort_values("r", ascending=False).reset_index(drop=True)


NAMES = pd.Series({"KANGRA": "kangra", "PUNE": "pune", "JHANSI": "jhansi", "LALITPUR": "lalitpur",
                   "KOZHIKODE": "kozhikode", "KANNUR": "kannur", "MEDAK": "medak",
                   "SIDDIPET": "siddipet", "BIG": "bigdistrict"})


def test_unchanged_district_is_strong():
    cls, row, _, _ = s04.decide("kangra", targets([("KANGRA", 0.99, 0.98)]), NAMES)
    assert cls == "STRONG" and row.geom_obs_id_b == "KANGRA"


def test_rename_with_intact_territory_continues_regardless_of_name():
    cls, row, agree, _ = s04.decide("poona", targets([("PUNE", 1.0, 1.0)]), NAMES)
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
