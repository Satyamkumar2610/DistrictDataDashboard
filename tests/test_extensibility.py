"""A new district statistic needs a config entry and a file, and no code change."""

import pandas as pd
import pytest

from district_evolution import core
from district_evolution.harmonize import engine, registry
from district_evolution.harmonize.weights import WEIGHT_METHODS

pytestmark = pytest.mark.skipif(not (core.PRODUCTS_DIR / "crosswalk_to_reference.parquet").exists(),
                                reason="pipeline not built")


def test_an_indicator_added_by_config_alone_is_harmonized(tmp_path, monkeypatch):
    data = tmp_path / "sample.csv"
    pd.DataFrame({"District": ["Kangra", "Mandi"], "State": ["Himachal Pradesh"] * 2, "Year": [2001, 2001],
                  "Production": [120.0, 80.0]}).to_csv(data, index=False)
    (tmp_path / "indicators.yaml").write_text(f"""
indicators:
  - code: sample_production_t
    unit: tonnes
    kind: extensive
    path: {data}
    source: synthetic test file
    columns: {{raw_name: District, state: State, year: Year, value: Production}}
ratios: []
""")
    monkeypatch.setattr(core, "CONFIG_DIR", tmp_path)
    indicators, _ = registry()
    sample = next(i for i in indicators if i.code == "sample_production_t")
    obs = engine.link(sample.observations())
    assert obs.link_status.tolist() == ["LINKED", "LINKED"]
    h = engine.allocate(obs, WEIGHT_METHODS["AREA"].weights(2001), sample.kind)
    expected = sum(v * WEIGHT_METHODS["AREA"].weights(2001).query("source_ck == @ck").weight.sum()
                   for v, ck in zip(obs.value, obs.canonical_key))
    assert h.value.sum() == pytest.approx(expected)
