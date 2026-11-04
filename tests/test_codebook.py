"""Every column of every documented table has a stated meaning."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "docs"))
import build_codebook as cb  # noqa: E402

SPEC = cb.load_spec()


@pytest.mark.parametrize("name", sorted(SPEC["tables"]))
def test_every_column_is_documented(name):
    spec = SPEC["tables"][name]
    missing = [c for c in cb.columns(name, spec) if not cb.describe(name, c, spec, SPEC["common"])]
    assert not missing, f"{name}: no description for {missing}"
