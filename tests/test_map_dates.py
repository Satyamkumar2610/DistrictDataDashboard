"""The V18 map-date rule: a district's creation year comes from real creation events only."""

import pandas as pd
import pytest

from district_evolution.core import reference

EVENTS = pd.DataFrame([
    # Manipur 1969: five districts created, four renamed in 1981
    ("Manipur", "Manipur", "Manipur South", "NEW_DISTRICT", 1969),
    ("Manipur", "Manipur South", "Churachandpur", "RENAME", 1981),
    # a parent continuing after a carve-out is not a creation of the parent
    ("Manipur", "Churachandpur", "Churachandpur", "SPLIT", 2016),
    # Siang: renamed in 1961, closed after 1971; a different Siang is created in 2015
    ("Arunachal Pradesh", "Siang Frontier Division", "Siang", "RENAME", 1961),
    ("Arunachal Pradesh", "East Siang", "Siang", "NEW_DISTRICT", 2015),
    # a genuine early depiction: created 1989, first map 1981
    ("Assam", "Goalpara", "Bongaigaon", "NEW_DISTRICT", 1989),
], columns=["state", "parent_district", "child_district", "event_type", "effective_year"])

REGISTRY = pd.DataFrame([
    ("IND-000001", "Churachandpur", "Manipur", 1971, None),
    ("IND-000002", "Siang", "Arunachal Pradesh", 1961, 1981),
    ("IND-000003", "Siang", "Arunachal Pradesh", 2021, None),
    ("IND-000004", "Bongaigaon", "Assam", 1981, None),
], columns=["canonical_key", "latest_name", "latest_state", "established_year", "closed_year"]).assign(origin_kind="NEW")


@pytest.fixture
def result(tmp_path, monkeypatch):
    path = tmp_path / "events.csv"
    EVENTS.to_csv(path, index=False)
    monkeypatch.setattr(reference, "EVENTS_CSV", path)
    monkeypatch.setattr(reference, "depicted_year", lambda state, year: year)
    return reference.shown_before_creation(REGISTRY).set_index("canonical_key")


def test_rename_resolves_to_the_original_creation(result):
    assert result.loc["IND-000001", "csv_year"] == 1969
    assert not result.loc["IND-000001", "shown_before_creation"]


def test_creation_after_closure_belongs_to_a_homonym(result):
    assert "IND-000002" not in result.index
    assert result.loc["IND-000003", "csv_year"] == 2015


def test_a_genuinely_early_map_is_still_flagged(result):
    assert result.loc["IND-000004", "shown_before_creation"]
