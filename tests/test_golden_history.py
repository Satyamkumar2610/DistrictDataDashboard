"""Golden cases: documented administrative history the built outputs must reproduce.

Runs against the warehouse built by run_all.sh (skipped if it is absent).
Each case is a well-documented reorganisation; a regression here means the
identity or lineage logic changed meaning, not just numbers.
"""

import pytest


def cks_named(con, name):
    return [r[0] for r in con.execute(
        "SELECT DISTINCT canonical_key FROM ck_observation WHERE lower(district_name) = lower(?)", [name]).fetchall()]


def span(con, ck):
    return con.execute("SELECT min(year), max(year) FROM ck_observation WHERE canonical_key = ?", [ck]).fetchone()


def children(con, parent_name, rel_type=None):
    sql = """SELECT lower(c.latest_name) FROM district_relationship r
             JOIN ck_registry p ON p.canonical_key = r.from_ck JOIN ck_registry c ON c.canonical_key = r.to_ck
             WHERE lower(p.display_name) = lower(?)"""
    args = [parent_name]
    if rel_type:
        sql += " AND r.relationship_type = ?"
        args.append(rel_type)
    return {r[0] for r in con.execute(sql, args).fetchall()}


@pytest.mark.parametrize("name", ["Kangra", "Hoshangabad", "Durg", "Jhansi", "Nellore", "Belgaum", "Adilabad"])
def test_continuing_districts_keep_one_identity_1951_2025(warehouse, name):
    cks = cks_named(warehouse, name)
    assert len(cks) == 1, f"{name} fragmented into {cks}"
    assert span(warehouse, cks[0]) == (1951, 2025)


def test_malabar_split_1957(warehouse):
    ck = cks_named(warehouse, "Malabar")[0]
    assert span(warehouse, ck) == (1951, 1951)
    assert {"kozhikode", "kannur", "palakkad"} <= children(warehouse, "Malabar", "SPLIT_FROM")


def test_twenty_four_parganas_bifurcation_1986(warehouse):
    ck = cks_named(warehouse, "Twenty Four Parganas")[0]
    assert span(warehouse, ck)[1] == 1981
    kids = children(warehouse, "Twenty Four Parganas", "SPLIT_FROM")
    assert any("north" in k for k in kids) and any("south" in k for k in kids)


def test_carve_outs_keep_the_parent(warehouse):
    assert "lalitpur" in children(warehouse, "Jhansi", "FORMED_FROM")
    assert {"balod", "bemetara"} & children(warehouse, "Durg", "FORMED_FROM")
    assert {"mancherial", "nirmal"} <= children(warehouse, "Adilabad", "FORMED_FROM")


@pytest.mark.parametrize("name, first", [
    ("Kolkata", 1951),   # Stanford 2021 draws it at half size; must not re-key (v4 rule 4)
    ("Chennai", 1951),   # Stanford 2011 draws it small, 2018 expansion real; one identity
    ("Riasi", 2011),     # spelled Reasi in Stanford 2011/2021
    ("Bemetara", 2021),  # spelled Bametara in Stanford 2021
    ("Nagaur", 1951),    # spelled Nagore in the 1951 layer
])
def test_one_identity_despite_map_defects_and_respellings(warehouse, name, first):
    cks = cks_named(warehouse, name)
    assert len(cks) == 1, f"{name} fragmented into {cks}"
    assert span(warehouse, cks[0]) == (first, 2025)


def test_non_administrative_features_are_not_districts(warehouse):
    assert warehouse.execute(
        "SELECT count(*) FROM ck_observation WHERE lower(district_name) LIKE 'disputed%'").fetchone()[0] == 0


def test_every_closed_district_has_a_fate(warehouse):
    assert warehouse.execute("""SELECT count(*) FROM ck_registry c WHERE NOT is_active AND NOT EXISTS
        (SELECT 1 FROM ck_fate f WHERE f.canonical_key = c.canonical_key)""").fetchone()[0] == 0


def test_mizoram_soi_lag_is_absorption_into_continuing_districts(warehouse):
    # SOI 2025 lacks Khawzawl / Saitual / Hnahthial (known_geometry_gaps.csv). With
    # Champhai keeping its identity, the gap shows as ABSORBED_INTO fates, not merges.
    rows = warehouse.execute("""SELECT lower(a.latest_name), lower(b.latest_name) FROM ck_fate f
        JOIN ck_registry a ON a.canonical_key = f.canonical_key JOIN ck_registry b ON b.canonical_key = f.to_ck
        WHERE f.closed_year = 2025 AND f.fate_type = 'ABSORBED_INTO' AND f.fate_share_rank = 1""").fetchall()
    assert {("khawzawl", "champhai"), ("saitual", "aizawl"), ("hnahthial", "lunglei")} <= set(rows)


def test_ledger_closes_in_both_directions(warehouse):
    bad = warehouse.execute(
        "SELECT count(*) FROM district_ledger WHERE NOT closure_ok OR NOT forward_closure_ok").fetchone()[0]
    assert bad == 0


def test_no_error_level_invariant_fails(warehouse):
    bad = warehouse.execute(
        "SELECT check_id FROM validation_result WHERE severity = 'ERROR' AND n_violations > 0").fetchall()
    assert bad == []
