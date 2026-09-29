"""Validated table writer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_table(df: pd.DataFrame, path: Path, schema_name: str | None = None,
                csv_copy: Path | None = None) -> pd.DataFrame:
    """Validate against its pandera schema (if named) and write parquet (+csv)."""
    if schema_name is not None:
        from district_evolution.contracts import schemas  # local import: contracts import core
        if "geometry" in df.columns:
            schemas.validate(schema_name, pd.DataFrame(df.drop(columns="geometry")))
        else:
            df = schemas.validate(schema_name, df)
    df = df.reset_index(drop=True)
    if path.suffix == ".csv":
        df.to_csv(path, index=False)
    else:
        df.to_parquet(path, index=False)
    if csv_copy is not None:
        df.to_csv(csv_copy, index=False)
    return df
