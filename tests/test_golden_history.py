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


def test_no_error_level_invariant_fails(warehouse):
    bad = warehouse.execute(
        "SELECT check_id FROM validation_result WHERE severity = 'ERROR' AND n_violations > 0").fetchall()
    assert bad == []


@pytest.mark.parametrize("name", ["Fatehgarh Sahib", "Barnala"])
def test_restored_district_links_back_across_the_gap(warehouse, name):
    """PEPSU districts absorbed in the 1950s and restored decades later (OD-01): new key, one edge."""
    old, new = sorted(cks_named(warehouse, name), key=lambda ck: span(warehouse, ck))
    assert span(warehouse, old) == (1951, 1951)
    edge = warehouse.execute("SELECT relationship_type FROM district_relationship WHERE from_ck = ? AND to_ck = ?",
                             [old, new]).fetchall()
    assert edge == [("RECONSTITUTED_FROM",)]
