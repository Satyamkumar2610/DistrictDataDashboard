"""Regression baselines: warehouse counts and gate results that change only when a PR intends it."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
VERSION = yaml.safe_load((ROOT / "config" / "pipeline.yaml").read_text())["pipeline_version"]
BASE = yaml.safe_load((Path(__file__).parent / "baselines" / f"v{VERSION}.yaml").read_text())
CHECKS = ROOT / "outputs" / "pipeline" / "s12_checks.csv"


@pytest.mark.parametrize("table,expected", sorted(BASE["row_counts"].items()))
def test_row_count(warehouse, table, expected):
    assert warehouse.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] == expected


@pytest.mark.parametrize("spec", BASE["breakdowns"], ids=lambda s: f"{s['table']}.{s['column']}")
def test_breakdown(warehouse, spec):
    rows = warehouse.execute(f'SELECT "{spec["column"]}", count(*) FROM "{spec["table"]}" GROUP BY 1').fetchall()
    assert dict(rows) == spec["counts"]


def test_lineage_event_corroboration(warehouse):
    n = warehouse.execute(
        "SELECT count(*) FROM lineage_corroboration WHERE corroboration = 'EVENT_CORROBORATED'").fetchone()[0]
    assert n == BASE["lineage_event_corroborated"]


@pytest.fixture(scope="module")
def checks():
    if not CHECKS.exists():
        pytest.skip("s12 has not run; build the pipeline first")
    return pd.read_csv(CHECKS)


def test_gate_has_no_error_violations(checks):
    assert int(checks[checks.severity == "ERROR"].n_violations.sum()) == BASE["gate"]["error_violations"]


def test_gate_warnings_with_findings(checks):
    found = sorted(checks[(checks.severity == "WARNING") & (checks.n_violations > 0)].check_id.unique())
    assert found == BASE["gate"]["warnings_with_findings"]


def test_all_contracts_pass(checks):
    v11 = checks[checks.check_id == "V11"]
    assert len(v11) == BASE["gate"]["contracts_passing"]
    assert (v11.n_violations == 0).all()
