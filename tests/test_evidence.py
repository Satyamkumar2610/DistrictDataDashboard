"""Evidence layer: claims from a source, shared verdict rules, and the rule that evidence never feeds core."""

import json

import numpy as np
import pytest
import yaml

from district_evolution import core
from district_evolution.evidence import rules
from district_evolution.evidence.wikidata import WikidataEvidence
from district_evolution.stages.e02_claim_linkage import map_of

WD = "http://www.wikidata.org/entity/"
SNAPSHOT = {"retrieved": "2026-09-23", "results": {
    "items": [
        {"d": WD + "Q1", "label": "Old district", "coord": "Point(77.0 28.0)", "stateLabel": "S",
         "inception": "1950-01-01T00:00:00Z", "dissolved": None},
        {"d": WD + "Q2", "label": "New district", "coord": "Point(77.5 28.5)", "stateLabel": "S",
         "inception": None, "dissolved": None},
    ],
    "areas": [{"d": WD + "Q2", "amount": "100", "unit": WD + "Q232291", "statedInLabel": "Census 2011",
               "pointInTime": None}],
    "lineage": [{"d": WD + "Q1", "prop": "http://www.wikidata.org/prop/direct/P1366", "target": WD + "Q2",
                 "targetLabel": "New district"}],
}}


@pytest.fixture
def claims(tmp_path):
    path = tmp_path / "wikidata_districts_2026-09-23.json"
    path.write_text(json.dumps(SNAPSHOT))
    return WikidataEvidence(path).claims()


def test_every_statement_becomes_a_cited_claim(claims):
    assert sorted(claims.claim_type) == ["AREA", "INCEPTION", "NAME", "NAME", "PARENT"]
    assert claims.citation.str.startswith("https://www.wikidata.org/wiki/Q").all()


def test_replaced_by_points_from_child_to_parent(claims):
    parent = claims[claims.claim_type == "PARENT"].iloc[0]
    assert (parent.source_ref, parent.value, parent.qualifier) == ("Q2", "Q1", "P1366")


def test_area_is_converted_to_km2_and_keeps_its_reference(claims):
    area = claims[claims.claim_type == "AREA"].iloc[0]
    assert area.value_num == pytest.approx(258.9988110336)
    assert "stated in: Census 2011" in area.citation


def test_area_bands():
    assert rules.area_label(0.01, False, np.nan, False) == "AGREE_WITHIN_2PCT"
    assert rules.area_label(0.05, False, np.nan, False) == "MINOR_2_TO_10PCT"
    assert rules.area_label(0.50, True, np.nan, False) == "WIKIDATA_MAGNITUDE_ERROR"
    assert rules.area_label(0.50, False, 2011.0, False) == "WIKIDATA_MATCHES_OUR_EARLIER_AREA"
    assert rules.area_label(0.50, False, np.nan, False) == "UNEXPLAINED_OVER_10PCT"


def test_formation_window():
    assert rules.formation_label(1995, 1991, 2001, 1981) == "CONSISTENT"
    assert rules.formation_label(1985, 1991, 2001, 1981) == "CONSISTENT_WITH_ONE_MAP_LAG"
    assert rules.formation_label(2005, 1991, 2001, 1981) == "OURS_EARLIER_THAN_INCEPTION"


def test_a_dissolved_subject_is_located_on_the_last_map_before_dissolution():
    assert map_of(np.nan) == core.REFERENCE_YEAR
    assert map_of(2016) == 2011
    assert np.isnan(map_of(1950))


def test_evidence_never_feeds_the_core_stages():
    stages = yaml.safe_load((core.PROJECT_ROOT / "dvc.yaml").read_text())["stages"]
    evidence_paths = ("data/gold/evidence", "outputs/evidence")
    for name, stage in stages.items():
        outs = [next(iter(o)) if isinstance(o, dict) else o for o in stage.get("outs", [])]
        if name.startswith("e"):
            assert all(o.startswith(evidence_paths) for o in outs), name
        if name[:3] in {f"s{n:02d}" for n in range(1, 11)}:
            assert not any(d.startswith(evidence_paths) for d in stage["deps"]), name
