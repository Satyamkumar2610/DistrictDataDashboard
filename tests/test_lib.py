import lib
import pytest


@pytest.mark.parametrize("raw, expected", [
    ("Pashchimi_Singhbhum", "pashchimi singhbhum"),
    ("Jammu & Kashmir", "jammu and kashmir"),
    ("Kangra District", "kangra"),
    ("Travancore - Cochin", "travancore cochin"),
    ("  North  24   Parganas ", "north 24 parganas"),
])
def test_normalize_name(raw, expected):
    assert lib.normalize_name(raw) == expected


def test_canonical_state_handles_underscores_and_renames():
    assert lib.canonical_state("Himachal_Pradesh") == "Himachal Pradesh"
    assert lib.canonical_state("ORISSA") == "Odisha"
    assert lib.canonical_state("Uttaranchal") == "Uttarakhand"


def test_jaro_winkler_textbook_values():
    assert lib.jaro_winkler("martha", "marhta") == pytest.approx(0.9611, abs=1e-4)
    assert lib.jaro_winkler("dixon", "dicksonx") == pytest.approx(0.8133, abs=1e-4)
    assert lib.jaro_winkler("same", "same") == 1.0


def test_state_compatibility_follows_reorganisations():
    assert "himachal pradesh" in lib.compatible_states("punjab")
    assert "andhra pradesh" in lib.compatible_states("tamil nadu")  # siblings via Madras
    assert "gujarat" in lib.compatible_states("bombay")
    assert "kerala" not in lib.compatible_states("punjab")


@pytest.mark.parametrize("a, b, agree", [
    ("trichur", "thrissur", True),              # documentary alias
    ("godavari east", "east godavari", True),   # word order
    ("kangra", "kangra", True),
    ("24 parganas", "south 24 parganas", False),  # qualified derivative = new district
    ("barddhaman", "purba bardhaman", False),
    ("bangalore", "bangalore urban", False),
    ("bilaspur", "balasore", False),
])
def test_names_agree(a, b, agree):
    assert lib.names_agree(a, b)[0] is agree


def test_stable_id_is_deterministic_and_order_sensitive():
    assert lib.stable_id("a", 1) == lib.stable_id("a", 1)
    assert lib.stable_id("a", 1) != lib.stable_id(1, "a")
    assert len(lib.stable_id("x")) == 32


def test_depicted_year_applies_only_confirmed_overrides():
    assert lib.depicted_year("Assam", 1981) == 1989        # CONFIRMED
    assert lib.depicted_year("ASSAM", 1981) == 1989        # case/spelling insensitive
    assert lib.depicted_year("Assam", 1991) == 1991
    assert lib.depicted_year("Manipur", 1971) == 1971      # CANDIDATE only: not applied
    assert lib.depicted_year("Bihar", 1981) == 1981


def test_within_closure_scales_with_area():
    assert lib.within_closure(1.9, 100.0)
    assert not lib.within_closure(2.1, 100.0)
    assert lib.within_closure(20.0, 20000.0)  # 0.1% of a large district
