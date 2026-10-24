"""Placeholders never hold an identity; the credibility audit reports what the data shows."""

import pandas as pd
import pytest

from district_evolution import core

AUDIT = core.PROJECT_ROOT / "outputs" / "audit"

pytestmark = pytest.mark.skipif(not (core.GOLD_CORE_DIR / "ck_registry.parquet").exists(),
                                reason="pipeline not built; run scripts/run_all.sh")


def test_no_placeholder_holds_an_identity():
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    names = obs.district_name.fillna("").str.lower()
    assert not names.str.contains(core.CFG["placeholders"]["disputed_name_pattern"], regex=True).any()
    assert not names.str.match(core.CFG["placeholders"]["sentinel_name_pattern"]).any()
    excluded = pd.read_csv(core.OUTPUT_DIR / "s01_excluded_non_administrative.csv")
    assert (excluded.reason == "DISPUTED_BOUNDARY_STRIP").sum() == 9


def test_v3_keys_all_resolve():
    m = pd.read_csv(core.REFERENCE_DIR / "ck_migration_v3_to_v4.csv", keep_default_na=False)
    assert len(m) == 804 and m.v3_ck.is_unique
    assert m.relation.value_counts().to_dict() == {"IDENTICAL": 461, "RENUMBERED": 314, "MERGED_INTO_V4_CK": 20,
                                                   "RETIRED_NON_ADMINISTRATIVE": 9}
    una = m.set_index("v3_ck").v4_ck
    assert una["IND-000417"] == una["IND-000468"]  # OD-02: Una 1981 and Una 1991 are one district
    reg = set(pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").canonical_key)
    assert set(m.loc[m.v4_ck != "", "v4_ck"]) == reg


@pytest.fixture(scope="module")
def audit():
    if not (AUDIT / "CREDIBILITY_AUDIT.md").exists():
        pytest.skip("a02 has not run; build the pipeline first")
    return AUDIT


def test_map_lag_found_in_the_events_compilation(audit):
    lag = pd.read_csv(audit / "credibility_map_lag.csv")
    ap = lag[(lag.event_state == "Andhra Pradesh") & (lag.effective_year == 2022)]
    assert len(ap) >= 20  # AP's 2022 reorganisation is on no map


def test_known_artifact_is_listed(audit):
    back = pd.read_csv(audit / "credibility_return_flows.csv")
    kangra_una = back[(back.from_name == "Kangra") & (back.to_name == "Una")]
    assert len(kangra_una) == 1 and kangra_una.returned_km2.iloc[0] > 500
    assert back.groupby(["from_ck", "to_ck", "year_a_back"]).size().max() == 1  # a return is counted once
