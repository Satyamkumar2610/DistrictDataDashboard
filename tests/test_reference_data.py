"""Curated reference files: the rules they must keep (they are source, so no stage validates them)."""

import pandas as pd

from district_evolution import core

REF = core.REFERENCE_DIR


def test_name_aliases_are_unambiguous():
    a = pd.read_csv(REF / "name_aliases.csv")
    alias = a.alias_name.map(core.normalize_name)
    canonical = a.canonical_name.map(core.normalize_name)
    assert alias.is_unique, "a name may have only one canonical form"
    assert not (alias == canonical).any()
    chained = set(alias) & set(canonical)
    assert not chained, f"alias chains (an alias that is also a canonical name): {sorted(chained)}"
    assert set(a.alias_kind) <= {"RENAME", "SPELLING"}
    assert set(a.evidence_type) <= {"DOCUMENTARY", "EVENTS_COMPILATION", "NAME_NORMALIZATION"}
    assert a.note.notna().all()


def test_known_geometry_gaps_are_well_formed():
    g = pd.read_csv(REF / "known_geometry_gaps.csv")
    assert set(g.status) <= {"CONFIRMED", "EVENTS_ONLY"}
    assert set(g.vintage) <= set(core.YEARS)
    assert g.evidence.str.len().min() > 100, "every gap row carries its evidence"


def test_review_outcomes_use_the_verdict_vocabulary():
    r = pd.read_csv(REF / "review_outcomes.csv", dtype=str)
    assert list(r.columns) == ["item_id", "item_type", "verdict", "evidence", "reviewer", "reviewed_on"]
    assert set(r.verdict.dropna()) <= {"CORRECT", "WRONG", "UNSURE"}
    assert r.item_id.is_unique
