"""Stage h04 — Ratio indicators (e.g. yield) from harmonized numerator and denominator (stat_ratio_value)."""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.contracts.schemas import SCHEMAS
from district_evolution.harmonize import engine, registry


def main() -> None:
    h = pd.read_parquet(core.GOLD_HARMONIZE_DIR / "stat_harmonized_value.parquet")
    specs = registry()[1]
    empty = pd.DataFrame({c: pd.Series(dtype=object) for c in SCHEMAS["stat_ratio_value"].columns})
    r = pd.concat([engine.ratios(h, s) for s in specs], ignore_index=True) if specs else empty
    r = r.astype({"year": int, "value": float, "coverage_score": float, "boundary_uncertain": bool}) if len(r) else \
        empty.astype({"indicator": str, "year": int, "method": str, "target_ck": str, "value": float,
                      "coverage_score": float, "boundary_uncertain": bool})
    core.write_table(r, core.GOLD_HARMONIZE_DIR / "stat_ratio_value.parquet", "stat_ratio_value",
                     csv_copy=core.HARMONIZE_OUTPUT_DIR / "h04_stat_ratio_value.csv")
    print(f"ratio indicators: {len(specs)}; rows: {len(r)}")


if __name__ == "__main__":
    main()
