import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "pipeline"))

WAREHOUSE = ROOT / "data" / "gold" / "district_evolution.duckdb"


@pytest.fixture(scope="session")
def warehouse():
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not built; run scripts/pipeline/run_all.sh")
    import duckdb
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield con
    con.close()
